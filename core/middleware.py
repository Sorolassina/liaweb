"""
Middleware personnalisé pour la gestion des sessions partagées
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import Session, text
from app_lia_web.core.database import engine
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


def setup_all_middlewares(app, allowed_hosts=None, secret_key=None):
    """
    Configure tous les middlewares personnalisés de l'application.
    
    Args:
        app: Instance de l'application FastAPI
        allowed_hosts: Liste des hôtes autorisés (optionnel)
        secret_key: Clé secrète pour les sessions (optionnel)
    """
    # Le middleware de session partagée est déjà ajouté dans main.py
    logger.info("✅ Middlewares personnalisés configurés")
    
    # Ici on peut ajouter d'autres middlewares si nécessaire
    # app.add_middleware(OtherMiddleware)