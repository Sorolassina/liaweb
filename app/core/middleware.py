"""
Middleware personnalisé pour la gestion des sessions partagées et le routage des schémas
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import Session, text, select
from .database import engine, get_session
from .program_schema_integration import ProgramSchemaManager, ProgramSchemaService, SchemaRoutingService
from ..models.base import Programme
import logging

logger = logging.getLogger(__name__)


class SharedSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware qui injecte une session partagée dans request.state
    pour toutes les dépendances de la requête.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Créer une session partagée pour cette requête
        session = Session(engine)
        
        # La session est maintenant propre car ProgramSchemaMiddleware utilise la session partagée
        
        try:
            # Injecter la session dans request.state
            request.state.shared_session = session
            print(f"🚀 MIDDLEWARE: Session partagée créée: {id(session)} pour {request.url}")
            logger.info(f"🔗 Session partagée créée: {id(session)} pour {request.url}")
            
            # Traiter la requête
            response = await call_next(request)
            
            # S'assurer que la session est toujours valide après le traitement
            try:
                session.commit()  # Commit les changements s'il y en a
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors du commit de session: {e}")
                try:
                    session.rollback()
                except Exception:
                    pass
            
            return response

        except Exception as e:
            logger.error(f"❌ Erreur dans le middleware de session: {e}")
            # En cas d'erreur, rollback de la session
            try:
                session.rollback()
            except Exception:
                pass
            raise

        finally:
            # Fermer la session à la fin de la requête
            try:
                session.close()
                logger.debug(f"🔒 Session partagée fermée: {id(session)}")
            except Exception as e:
                logger.error(f"❌ Erreur lors de la fermeture de session: {e}")


class ProgramCreationMiddleware(BaseHTTPMiddleware):
    """Middleware pour surveiller la création de programmes et créer automatiquement les schémas"""
    
    async def dispatch(self, request: Request, call_next):
        # Traiter la requête
        response = await call_next(request)
        
        # Vérifier si c'est une création de programme (POST sur /programmes ou similar)
        if (request.method == "POST" and 
            ("programme" in request.url.path.lower() or 
             "program" in request.url.path.lower()) and
            response.status_code in [200, 201]):
            
            try:
                # Extraire les données de la réponse si possible
                # Pour l'instant, on va juste logger et laisser le système principal gérer
                logger.info(f"Programme potentiellement créé via {request.url.path}")
                
                # Déclencher une vérification des programmes pour créer les schémas manquants
                self._check_and_create_missing_schemas()
                
            except Exception as e:
                logger.error(f"Erreur dans ProgramCreationMiddleware: {e}")
        
        return response
    
    def _check_and_create_missing_schemas(self):
        """Vérifie et crée les schémas manquants pour les programmes existants"""
        try:
            session = next(get_session())
            manager = ProgramSchemaManager()
            manager.session = session
            
            programmes = session.exec(
                select(Programme).where(Programme.actif == True)
            ).all()
            
            for programme in programmes:
                if not manager.schema_exists(programme.code):
                    logger.info(f"Création automatique du schéma pour le programme {programme.code}")
                    manager.create_program_schema(programme.code)
                    
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des schémas: {e}")
        finally:
            if 'session' in locals():
                session.close()


def get_shared_session(request: Request) -> Session:
    """
    Dependency pour récupérer la session partagée injectée par le middleware.
    À utiliser dans les routes au lieu de Depends(get_session).
    """
    if not hasattr(request.state, 'shared_session'):
        logger.error(f"❌ SharedSessionMiddleware non configuré pour {request.url}")
        raise RuntimeError("SharedSessionMiddleware non configuré ou session non disponible")
    
    session = request.state.shared_session
    logger.info(f"🔍 Session partagée récupérée: {id(session)} pour {request.url}")
    return session


class ProgramSchemaMiddleware(BaseHTTPMiddleware):
    """Middleware pour router automatiquement vers le bon schéma selon le programme"""
    
    async def dispatch(self, request: Request, call_next):
        # Log pour debug
        if 'livrables' in str(request.url.path) and 'modifier' in str(request.url.path):
            logger.info(f"🔍 MIDDLEWARE: Requête POST vers {request.url.path} - Méthode: {request.method}")
        
        # Extraire le programme de l'URL ou des paramètres
        programme_code = await self._extract_program_from_request(request)
        
        # Si aucun programme détecté, récupérer depuis request.state
        if not programme_code:
            programme_code = getattr(request.state, 'current_programme', None)
        
        if programme_code:
            # Stocker le programme dans request.state pour la persistance
            request.state.current_programme = programme_code
            logger.info(f"Programme {programme_code} stocké dans request.state")
            
            # Utiliser la session partagée si disponible, sinon créer une session temporaire
            if hasattr(request.state, 'shared_session'):
                session = request.state.shared_session
                logger.info(f"Utilisation de la session partagée pour {programme_code}")
            else:
                session = next(get_session())
                logger.info(f"Création d'une session temporaire pour {programme_code}")
            
            try:
                schema_service = ProgramSchemaService(session)
                
                if not schema_service.schema_exists(programme_code):
                    logger.warning(f"Schéma {programme_code} n'existe pas, création automatique")
                    schema_service.create_program_schema(programme_code)
                
                # Créer un service de routage pour cette requête
                routing_service = SchemaRoutingService(session)
                routing_service.set_schema(programme_code.lower())
                
                # Ajouter le schéma au contexte de la requête
                request.state.program_schema = programme_code.lower()
                
                logger.info(f"Requête routée vers le schéma: {programme_code.lower()}")
                
            except Exception as e:
                logger.error(f"Erreur lors de la gestion du schéma {programme_code}: {e}")
            finally:
                # Ne fermer la session que si c'est une session temporaire
                if not hasattr(request.state, 'shared_session'):
                    session.close()
        else:
            # Aucun programme en session, utiliser le schéma public par défaut
            request.state.program_schema = 'public'
            logger.info("Aucun programme détecté, utilisation du schéma public")
        
        response = await call_next(request)
        return response
    
    async def _extract_program_from_request(self, request: Request) -> str:
        """Extrait le code du programme de la requête"""
        
        # PRIORITÉ 1: Depuis les données de formulaire (pour les requêtes POST)
        # NOTE: On ne peut pas lire request.form() ici car cela consomme le body
        # et empêche les routes de le lire. On utilise plutôt le Referer ou les query params.
        # Les routes liront elles-mêmes le formulaire si nécessaire.
        # if request.method == 'POST':
        #     try:
        #         form_data = await request.form()
        #         programme = form_data.get('programme') or form_data.get('programme_code')
        #         if programme and self._is_valid_program_code(programme.upper()):
        #             return programme.upper()
        #     except:
        #         pass
        
        # PRIORITÉ 2: Depuis les paramètres de query
        programme = request.query_params.get('programme')
        if programme and self._is_valid_program_code(programme.upper()):
            return programme.upper()
        
        # PRIORITÉ 3: Depuis les headers
        programme = request.headers.get('X-Programme')
        if programme and self._is_valid_program_code(programme.upper()):
            return programme.upper()

        # PRIORITÉ 4: Depuis le header Referer (extraction du paramètre programme de l'URL précédente)
        referer = request.headers.get("referer", "")
        if referer and "programme=" in referer:
            import re
            match = re.search(r'programme=([^&]+)', referer)
            if match:
                programme = match.group(1).upper()
                if self._is_valid_program_code(programme):
                    return programme

        # PRIORITÉ 5: Depuis l'URL (ex: /ACD/candidats, /CODEV/sessions)
        path_parts = request.url.path.strip('/').split('/')
        if len(path_parts) > 0:
            potential_program = path_parts[0].upper()
            # Vérifier si c'est un code de programme valide dans la base
            if self._is_valid_program_code(potential_program):
                return potential_program
        
        return "PUBLIC"
    
    def _is_valid_program_code(self, code: str) -> bool:
        """Vérifie si un code de programme existe dans la base de données"""
        try:
            # Créer une session temporaire
            session = next(get_session())
            try:
                # Chercher le programme par code avec une requête SQL brute
                # pour éviter les problèmes de colonnes manquantes dans le modèle
                programme_query = text("""
                    SELECT code 
                    FROM programme 
                    WHERE code = :code AND actif = true
                """).bindparams(code=code.upper())
                programme = session.exec(programme_query).first()
                return programme is not None
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification du programme {code}: {e}")
            return False


def setup_all_middlewares(app, allowed_hosts=None, secret_key=None):
    """
    Configure tous les middlewares personnalisés de l'application.
    
    Args:
        app: Instance de l'application FastAPI
        allowed_hosts: Liste des hôtes autorisés (optionnel)
        secret_key: Clé secrète pour les sessions (optionnel)
    """
    # Ordre important : ProgramSchemaMiddleware doit être ajouté AVANT ProgramCreationMiddleware
    # pour détecter le programme dès le début de la requête
    app.add_middleware(ProgramSchemaMiddleware)
    # Ajouter le middleware de création de schémas pour les programmes
    app.add_middleware(ProgramCreationMiddleware)

    app.add_middleware(SharedSessionMiddleware)
    
    logger.info("✅ Middlewares personnalisés configurés")
    
    # Ici on peut ajouter d'autres middlewares si nécessaire
    # app.add_middleware(OtherMiddleware)