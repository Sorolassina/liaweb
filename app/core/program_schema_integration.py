"""
Système de schémas par programme - Tout en un
Gère la création dynamique des schémas, le routage des requêtes et les modèles conscients des schémas
"""
from typing import Optional, Union, Type, Dict, Any, List
from fastapi import FastAPI, Request, Depends, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import SQLModel, Session, create_engine, text, Field
from .database import get_session
from ..models.base import (
    Programme, User, Partenaire, Groupe, PasswordRecoveryCode,
    Candidat, Preinscription, Entreprise, Document, 
    Eligibilite, EtapePipeline,
    AvancementEtape, ActionHandicap, RendezVous, SessionProgramme,
    SessionParticipant, SuiviMensuel,
    ReorientationCandidat, EmargementRDV, ProgrammeUtilisateur, Promotion
)
from ..models.jury import DecisionJuryTable, DecisionJuryCandidat
from ..models.seminaire import (
    Seminaire, SessionSeminaire, InvitationSeminaire, PresenceSeminaire,
    LivrableSeminaire, RenduLivrable
)
from ..models.event import (
    Event, InvitationEvent, PresenceEvent
)
from ..models.elearning import (
    RessourceElearning, ModuleElearning, ProgressionElearning, 
    ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning, 
    ModuleRessource
)
from ..models.codev import (
    SeanceCodev, PresentationCodev, ContributionCodev, ParticipationSeance,
    CycleCodev, GroupeCodev, MembreGroupeCodev
)
import logging

logger = logging.getLogger(__name__)

# ===== SERVICE DE ROUTAGE DES REQUÊTES =====

class SchemaRoutingService:
    """Service pour router les requêtes vers les bons schémas"""
    
    def __init__(self, session: Session):
        self.session = session
        self.current_schema: Optional[str] = None
        self._model_cache: Dict[str, Dict[Type[SQLModel], Type[SQLModel]]] = {}  # Cache des modèles par schéma
    
    def set_schema(self, schema_name: str):
        """Définit le schéma actuel et configure le search_path PostgreSQL"""
        schema_lower = schema_name.lower()
        
        # Ne reconfigurer que si le schéma a changé
        if self.current_schema == schema_lower:
            logger.debug(f"Schéma déjà configuré: {self.current_schema}")
            return
        
        # Si le schéma change, on peut vider le cache des modèles de l'ancien schéma
        # pour forcer la recréation avec le nouveau schéma
        old_schema = self.current_schema
        self.current_schema = schema_lower
        logger.info(f"🔧 Schéma changé: {old_schema} -> {self.current_schema}")
        
        # IMPORTANT: Vérifier et nettoyer le cache du nouveau schéma si les modèles ont le mauvais schéma
        # Cela peut arriver si un modèle a été mis en cache avec un schéma incorrect
        if schema_lower in self._model_cache:
            models_to_remove = []
            for model_class, cached_model in self._model_cache[schema_lower].items():
                if hasattr(cached_model, '__table__') and cached_model.__table__ is not None:
                    cached_schema = getattr(cached_model.__table__, 'schema', None)
                    if cached_schema != schema_lower:
                        logger.warning(f"⚠️ Modèle en cache pour schéma {schema_lower} a le mauvais schéma ({cached_schema}), suppression du cache...")
                        models_to_remove.append(model_class)
            
            # Supprimer les modèles avec le mauvais schéma du cache
            for model_class in models_to_remove:
                del self._model_cache[schema_lower][model_class]
        
        # Nettoyer le cache de l'ancien schéma si nécessaire (optionnel, le cache par schéma devrait suffire)
        # Mais on garde le cache pour éviter de recréer les modèles inutilement
        
        # IMPORTANT: Configurer le search_path PostgreSQL pour que les requêtes
        # cherchent dans le bon schéma par défaut
        # NOTE: Même si les modèles ont un schéma explicite, le search_path peut être utile
        # pour les tables non qualifiées. Cependant, SQLAlchemy utilisera le schéma explicite
        # des modèles s'il est défini, donc le search_path est principalement pour les requêtes SQL brutes.
        try:
            # Utiliser exec() pour SQLModel et commit pour persister le search_path
            self.session.exec(text(f"SET search_path TO {self.current_schema}, public"))
            self.session.commit()  # Commit pour s'assurer que le search_path est appliqué
            
            # Vérifier que le search_path est bien configuré
            verify_result = self.session.exec(text("SHOW search_path")).first()
            logger.info(f"✅ Search_path PostgreSQL configuré à: {self.current_schema}, public (vérifié: {verify_result})")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de configurer le search_path: {e}")
            try:
                self.session.rollback()
            except:
                pass
    
    def get_schema(self) -> Optional[str]:
        """Retourne le schéma actuel"""
        return self.current_schema
    
    def execute_in_schema(self, sql: str, params: Dict[str, Any] = None, schema: str = None) -> Any:
        """Exécute une requête SQL dans un schéma spécifique"""
        target_schema = schema or self.current_schema or "public"
        
        # Configurer le search_path si nécessaire (utilise set_schema pour éviter la duplication)
        if target_schema != self.current_schema:
            self.set_schema(target_schema)
        
        # Remplacer les références de table par des références complètes avec schéma
        sql_with_schema = self._add_schema_to_sql(sql, target_schema)
        
        logger.debug(f"Exécution SQL dans schéma {target_schema}: {sql_with_schema}")
        return self.session.execute(text(sql_with_schema), params or {})
    
    def _add_schema_to_sql(self, sql: str, schema: str) -> str:
        """Ajoute le schéma aux références de tables dans le SQL"""
        # Tables qui restent dans le schéma public
        public_tables = {
            'user', 'programme', 'partenaire', 'groupe', 'password_recovery_code',
            'jury', 'membre_jury'
        }
        
        # Tables qui vont dans le schéma du programme (noms singuliers pour correspondre aux modèles SQLModel)
        program_tables = {
            'candidat', 'preinscription', 'inscription', 'entreprise', 
            'document', 'eligibilite', 'rendez_vous',
            'session_programme', 'session_participant', 'suivi_mensuel',
            'reorientation_candidat', 
            'emargement_rdv', 'programme_utilisateur', 'action_handicap',
            'avancement_etape', 'etape_pipeline',
            'seminaire', 'session_seminaire', 'invitation_seminaire',
            'presence_seminaire', 'livrable_seminaire', 'rendu_livrable',
            'event', 'invitation_event', 'presence_event',
            'ressource_elearning', 'module_elearning', 'progression_elearning',
            'objectif_elearning', 'quiz_elearning', 'reponse_quiz',
            'certificat_elearning', 'module_ressource',
            'seance_codev', 'presentation_codev', 'contribution_codev',
            'participation_seance', 'cycle_codev', 'groupe_codev',
            'membre_groupe_codev', 'decision_jury_table', 'decision_jury_candidat'
        }
        
        # Remplacer les références de tables
        for table in program_tables:
            # Remplacer les références simples (FROM table, JOIN table, etc.)
            sql = sql.replace(f" FROM {table}", f" FROM {schema}.{table}")
            sql = sql.replace(f" JOIN {table}", f" JOIN {schema}.{table}")
            sql = sql.replace(f" LEFT JOIN {table}", f" LEFT JOIN {schema}.{table}")
            sql = sql.replace(f" RIGHT JOIN {table}", f" RIGHT JOIN {schema}.{table}")
            sql = sql.replace(f" INNER JOIN {table}", f" INNER JOIN {schema}.{table}")
            sql = sql.replace(f" OUTER JOIN {table}", f" OUTER JOIN {schema}.{table}")
            sql = sql.replace(f" UPDATE {table}", f" UPDATE {schema}.{table}")
            sql = sql.replace(f" INSERT INTO {table}", f" INSERT INTO {schema}.{table}")
            sql = sql.replace(f" DELETE FROM {table}", f" DELETE FROM {schema}.{table}")
            
            # Remplacer les références avec alias (FROM table t, JOIN table t, etc.)
            sql = sql.replace(f" FROM {table} ", f" FROM {schema}.{table} ")
            sql = sql.replace(f" JOIN {table} ", f" JOIN {schema}.{table} ")
            sql = sql.replace(f" LEFT JOIN {table} ", f" LEFT JOIN {schema}.{table} ")
            sql = sql.replace(f" RIGHT JOIN {table} ", f" RIGHT JOIN {schema}.{table} ")
            sql = sql.replace(f" INNER JOIN {table} ", f" INNER JOIN {schema}.{table} ")
            sql = sql.replace(f" OUTER JOIN {table} ", f" OUTER JOIN {schema}.{table} ")
        
        return sql
    
    def get_model_for_schema(self, model_class: Type[SQLModel], schema: str = None) -> Type[SQLModel]:
        """Retourne une version du modèle configurée pour un schéma spécifique"""
        target_schema = schema or self.current_schema or "public"
        
        # Vérifier le cache pour éviter de recréer les modèles
        if target_schema not in self._model_cache:
            self._model_cache[target_schema] = {}
        
        if model_class in self._model_cache[target_schema]:
            cached_model = self._model_cache[target_schema][model_class]
            # Vérifier que le schéma est toujours correct
            if hasattr(cached_model, '__table__') and cached_model.__table__ is not None:
                cached_schema = getattr(cached_model.__table__, 'schema', None)
                if cached_schema == target_schema:
                    logger.debug(f"✅ Utilisation du modèle en cache: {model_class.__name__} pour schéma {target_schema}")
                    return cached_model
                else:
                    logger.warning(f"⚠️ Modèle en cache a le mauvais schéma ({cached_schema} au lieu de {target_schema}), recréation...")
                    # Retirer du cache pour forcer la recréation
                    del self._model_cache[target_schema][model_class]
        
        # APPROCHE SIMPLE : Créer une classe qui hérite simplement avec le bon schéma dans __table_args__
        # SQLModel/SQLAlchemy gérera automatiquement le schéma dans les requêtes SQL (ex: SELECT * FROM acd.candidat)
        
        # IMPORTANT: Préparer model_config AVANT la création de la classe pour gérer les Relations (Mapped)
        try:
            from pydantic import ConfigDict
            # Configurer model_config pour accepter les types arbitraires (nécessaire pour les Relations)
            model_config_dict = ConfigDict(arbitrary_types_allowed=True)
        except ImportError:
            # Fallback pour Pydantic v1
            model_config_dict = {'arbitrary_types_allowed': True}
        except Exception:
            model_config_dict = {'arbitrary_types_allowed': True}
        
        # Copier la table du modèle parent AVANT de créer la classe pour éviter que SQLModel
        # essaie de recréer les colonnes (et échoue sur les Relations)
        parent_table = None
        if hasattr(model_class, '__table__'):
            parent_table = model_class.__table__
        
        # IMPORTANT: Copier la table AVANT de créer la classe pour éviter que SQLModel
        # essaie de recréer les colonnes avec les Relations
        copied_table = None
        if parent_table is not None:
            try:
                from sqlalchemy import MetaData
                copied_table = parent_table.to_metadata(MetaData(), schema=target_schema, name=parent_table.name)
                # S'assurer que le schéma est bien défini sur la table copiée
                if copied_table.schema != target_schema:
                    copied_table.schema = target_schema
                logger.debug(f"Table {parent_table.name} copiée vers le schéma {target_schema} avant création de classe (schema={copied_table.schema})")
            except Exception as e:
                logger.debug(f"Note lors de la copie préalable de la table pour {model_class.__name__}: {e}")
        
        # APPROCHE FINALE: Utiliser directement le modèle parent avec __table__ assigné
        # après la création. Si SQLModel essaie de traiter les Relations, capturer l'exception
        # et utiliser une approche alternative.
        if copied_table is not None:
            try:
                # Essayer de créer la classe avec héritage normal
                # SQLModel essaiera de traiter les Relations, ce qui échouera probablement
                class SchemaSpecificModel(model_class):
                    __tablename__ = parent_table.name
                    __table_args__ = {"schema": target_schema, "extend_existing": True}
                    model_config = model_config_dict
                
                # Assigner la table immédiatement après la création
                SchemaSpecificModel.__table__ = copied_table
                
                logger.debug(f"Classe {SchemaSpecificModel.__name__} créée avec table assignée après création")
            except (ValueError, TypeError) as e:
                # Si la création échoue à cause des Relations, utiliser le modèle parent directement
                # mais créer une nouvelle classe qui hérite pour éviter de modifier le modèle original
                logger.warning(f"Échec création classe pour {model_class.__name__}: {e}")
                logger.warning(f"Création d'une nouvelle classe qui hérite mais utilise la table copiée")
                
                # IMPORTANT: Créer une nouvelle classe qui hérite du modèle parent
                # mais qui utilise directement la table copiée AVANT que SQLModel ne traite les Relations
                # Pour cela, on va créer la classe avec type() et assigner la table dans le dictionnaire
                
                # Créer le dictionnaire de la classe avec la table déjà assignée
                # Cela devrait forcer SQLAlchemy à utiliser le schéma explicite
                class_dict = {
                    '__tablename__': parent_table.name,
                    '__table_args__': {"schema": target_schema, "extend_existing": True},
                    'model_config': model_config_dict,
                    '__table__': copied_table,  # Assigner la table AVANT la création
                }
                
                # Créer la classe avec type() pour avoir un contrôle total
                # Mais cela échouera probablement encore à cause des Relations
                try:
                    SchemaSpecificModel = type(
                        f"{model_class.__name__}_{target_schema}",
                        (model_class,),
                        class_dict
                    )
                    logger.debug(f"Classe créée avec type() pour {model_class.__name__}")
                except (ValueError, TypeError) as e2:
                    # Si cela échoue, utiliser directement le modèle parent
                    # mais s'assurer que la table a bien le schéma défini
                    logger.warning(f"Échec création classe avec type() pour {model_class.__name__}: {e2}")
                    logger.warning(f"Utilisation du modèle parent directement avec table modifiée")
                    
                    # Utiliser directement le modèle parent mais avec la table modifiée
                    SchemaSpecificModel = model_class
                    # Assigner la table copiée avec le bon schéma
                    SchemaSpecificModel.__table__ = copied_table
                    # S'assurer que le schéma est bien défini sur la table
                    if hasattr(SchemaSpecificModel.__table__, 'schema'):
                        SchemaSpecificModel.__table__.schema = target_schema
                    # Modifier le __table_args__ pour inclure le schéma
                    if not hasattr(SchemaSpecificModel, '__table_args__') or SchemaSpecificModel.__table_args__ is None:
                        SchemaSpecificModel.__table_args__ = {"schema": target_schema, "extend_existing": True}
                    elif isinstance(SchemaSpecificModel.__table_args__, dict):
                        SchemaSpecificModel.__table_args__ = {**SchemaSpecificModel.__table_args__, "schema": target_schema, "extend_existing": True}
                    elif isinstance(SchemaSpecificModel.__table_args__, tuple):
                        # Si c'est un tuple, le convertir en dict
                        SchemaSpecificModel.__table_args__ = {"schema": target_schema, "extend_existing": True}
                    
                    logger.debug(f"Modèle parent {model_class.__name__} utilisé directement avec table modifiée (schema={SchemaSpecificModel.__table__.schema if hasattr(SchemaSpecificModel.__table__, 'schema') else 'N/A'})")
            
            # Copier les métadonnées du modèle original
            SchemaSpecificModel.__name__ = f"{model_class.__name__}_{target_schema}"
            SchemaSpecificModel.__qualname__ = f"{model_class.__qualname__}_{target_schema}"
        else:
            # Si on n'a pas pu copier la table, créer la classe normalement
            # mais cela échouera probablement avec les Relations
            try:
                class SchemaSpecificModel(model_class):
                    __tablename__ = model_class.__tablename__ if hasattr(model_class, '__tablename__') else model_class.__name__.lower()
                    __table_args__ = {
                        "schema": target_schema,
                        "extend_existing": True
                    }
                    model_config = model_config_dict
            except (ValueError, Exception) as e:
                logger.error(f"Impossible de créer la classe pour {model_class.__name__}: {e}")
                raise
            
            # Copier les métadonnées du modèle original
            SchemaSpecificModel.__name__ = f"{model_class.__name__}_{target_schema}"
            SchemaSpecificModel.__qualname__ = f"{model_class.__qualname__}_{target_schema}"
            
            # Essayer de copier la table après la création
            if parent_table is not None:
                try:
                    from sqlalchemy import MetaData
                    new_table = parent_table.to_metadata(MetaData(), schema=target_schema, name=parent_table.name)
                    SchemaSpecificModel.__table__ = new_table
                    logger.debug(f"Table {parent_table.name} copiée vers le schéma {target_schema}")
                except Exception as e:
                    logger.debug(f"Note lors de la copie de la table pour {model_class.__name__}: {e}")
                    # Si la copie échoue, modifier juste le schéma de la table existante
                    try:
                        if hasattr(SchemaSpecificModel, '__table__'):
                            SchemaSpecificModel.__table__.schema = target_schema
                    except Exception:
                        pass
        
        # IMPORTANT: Ne PAS configurer le search_path ici car cela peut faire que SQLAlchemy
        # ignore le schéma explicite de la table et génère FROM candidat au lieu de FROM acd.candidat
        # Le search_path sera configuré dans le code appelant si nécessaire
        try:
            # Vérifier que la table a bien le schéma défini
            if hasattr(SchemaSpecificModel, '__table__') and SchemaSpecificModel.__table__ is not None:
                table_schema = getattr(SchemaSpecificModel.__table__, 'schema', None)
                table_name = SchemaSpecificModel.__table__.name
                logger.debug(f"Table configurée: {table_schema}.{table_name if table_schema else table_name} pour le modèle {SchemaSpecificModel.__name__}")
                
                # Si le schéma n'est pas défini sur la table, le définir explicitement
                if table_schema != target_schema:
                    logger.warning(f"⚠️ Le schéma de la table ({table_schema}) ne correspond pas au schéma cible ({target_schema}), correction...")
                    SchemaSpecificModel.__table__.schema = target_schema
                    # Forcer la mise à jour du mapper SQLAlchemy
                    try:
                        from sqlalchemy import inspect as sa_inspect
                        mapper = sa_inspect(SchemaSpecificModel)
                        if mapper and hasattr(mapper, 'local_table'):
                            mapper.local_table.schema = target_schema
                            logger.debug(f"✅ Schéma corrigé sur la table ET le mapper: {SchemaSpecificModel.__table__.schema}")
                    except Exception as e:
                        logger.debug(f"Note lors de la mise à jour du mapper: {e}")
                    logger.debug(f"✅ Schéma corrigé: {SchemaSpecificModel.__table__.schema}")
                
                # IMPORTANT: Vérifier que SQLAlchemy va utiliser le schéma explicite
                # en vérifiant le mapper SQLAlchemy
                try:
                    from sqlalchemy import inspect as sa_inspect
                    mapper = sa_inspect(SchemaSpecificModel)
                    if mapper and hasattr(mapper, 'local_table'):
                        mapper_schema = getattr(mapper.local_table, 'schema', None)
                        logger.debug(f"Mapper local_table.schema = {mapper_schema}")
                        if mapper_schema != target_schema:
                            logger.warning(f"Le schéma du mapper ({mapper_schema}) ne correspond pas au schéma cible ({target_schema}), correction...")
                            # Essayer de forcer le schéma sur le mapper
                            mapper.local_table.schema = target_schema
                            logger.debug(f"Schéma du mapper corrigé: {mapper.local_table.schema}")
                except Exception as e:
                    logger.debug(f"Note lors de l'inspection du mapper: {e}")
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification de la table pour {target_schema}: {e}")
        
        # Mettre en cache le modèle pour éviter de le recréer
        if target_schema not in self._model_cache:
            self._model_cache[target_schema] = {}
        self._model_cache[target_schema][model_class] = SchemaSpecificModel
        
        logger.debug(f"✅ Modèle {model_class.__name__} créé pour schéma {target_schema} (table schema: {getattr(SchemaSpecificModel.__table__, 'schema', None) if hasattr(SchemaSpecificModel, '__table__') else 'N/A'})")
        
        return SchemaSpecificModel


def table_exists_anywhere(table_name: str, session=None, schema: str = None) -> bool:
    """Vérifie si une table existe dans un schéma spécifique ou dans tous les schémas de programme"""
    try:
        if session is None:
            session = next(get_session())
            should_close = True
        else:
            should_close = False
            
        if schema:
            # Chercher dans un schéma spécifique
            result = session.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = :table_name 
                    AND table_schema = :schema_name
                )
            """).bindparams(table_name=table_name, schema_name=schema))
        else:
            # Chercher dans tous les schémas (public + schémas de programme)
            # D'abord, récupérer tous les schémas de programme
            schemas_query = text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                AND schema_name NOT LIKE 'pg_%'
            """)
            all_schemas_result = session.execute(schemas_query)
            all_schemas = [row[0] for row in all_schemas_result.fetchall()]
            
            # Chercher dans tous les schémas en utilisant une requête avec OR
            if not all_schemas:
                # Aucun schéma trouvé, chercher seulement dans public
                result = session.execute(text("""
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = :table_name 
                        AND table_schema = 'public'
                    )
                """).bindparams(table_name=table_name))
            else:
                # Construire une requête avec OR pour chaque schéma (sécurisé car les noms de schémas sont validés)
                schema_conditions = " OR ".join([f"table_schema = '{s}'" for s in all_schemas + ['public']])
                result = session.execute(text(f"""
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = :table_name 
                        AND ({schema_conditions})
                    )
                """).bindparams(table_name=table_name))
        
        exists = result.fetchone()[0]
        
        if should_close:
            session.close()
            
        return exists
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de l'existence de la table {table_name} dans le schéma {schema or 'all'}: {e}")
        if should_close and 'session' in locals():
            session.close()
        return False


def safe_count_query(session, model_class, **filters) -> int:
    """Effectue un comptage sécurisé d'une table (retourne 0 si la table n'existe pas)"""
    try:
        # Vérifier si la table existe dans n'importe quel schéma
        if not table_exists_anywhere(model_class.__tablename__, session):
            logger.info(f"Table {model_class.__tablename__} n'existe pas - retour 0")
            return 0
        
        # Effectuer le comptage
        from sqlmodel import select
        from sqlalchemy import func
        
        query = select(func.count(model_class.id))
        if filters:
            for key, value in filters.items():
                if hasattr(model_class, key):
                    query = query.where(getattr(model_class, key) == value)
        
        result = session.exec(query).one() or 0
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors du comptage de {model_class.__tablename__}: {e}")
        return 0


# ===== SERVICE DE GESTION DES SCHÉMAS =====

class ProgramSchemaService:
    """Service pour gérer les schémas de base de données par programme"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_program_schema(self, program_code: str) -> bool:
        """Crée un schéma complet pour un programme (utilise ProgramSchemaManager)"""
        try:
            manager = ProgramSchemaManager(session=self.session)  # Passer la session existante
            
            schema_name = program_code.lower()
            
            # Vérifier si le schéma existe déjà
            if manager.schema_exists(program_code):
                logger.info(f"Le schéma {schema_name} existe déjà")
                return True
            
            # Créer le schéma
            self.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            self.session.commit()
            
            # Créer les tables en utilisant ProgramSchemaManager
            manager._create_tables_in_schema(schema_name)
            
            logger.info(f"Schéma {schema_name} créé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du schéma {program_code}: {e}")
            self.session.rollback()
            return False
    
    def schema_exists(self, program_code: str) -> bool:
        """Vérifie si un schéma existe pour un programme"""
        schema_name = program_code.lower()
        return self._schema_exists(schema_name)
    
    def get_schema_tables(self, program_code: str) -> List[str]:
        """Retourne la liste des tables dans un schéma"""
        try:
            schema_name = program_code.lower()
            result = self.session.execute(text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = :schema_name
                ORDER BY tablename
            """).bindparams(schema_name=schema_name))
            
            return [row[0] for row in result.fetchall()]
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tables du schéma {program_code}: {e}")
            return []
    
    def _schema_exists(self, schema_name: str) -> bool:
        """Vérifie si un schéma existe"""
        result = self.session.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = :schema_name
            )
        """).bindparams(schema_name=schema_name))
        
        return result.fetchone()[0]

# ===== GESTIONNAIRE PRINCIPAL DES SCHÉMAS =====

class ProgramSchemaManager:
    """Gestionnaire centralisé des schémas par programme"""
    
    def __init__(self, session: Session = None):
        # Si une session est fournie, l'utiliser, sinon créer une nouvelle
        if session is None:
            self.session = next(get_session())
            self._session_owner = True  # Marquer que cette session doit être fermée
        else:
            self.session = session
            self._session_owner = False  # La session est gérée ailleurs
        
        # Tables qui restent dans le schéma public
        self.public_tables = {
            'user', 'programme', 'partenaire', 'groupe', 'password_recovery_code',
            'jury', 'membre_jury'
        }
        
        # Tous les modèles SQLModel (sauf ceux du public)
        self.program_models = [
            # Base models
            Candidat, Preinscription, Entreprise, Document,
            Eligibilite, EtapePipeline,
            AvancementEtape, ActionHandicap, RendezVous, SessionProgramme,
            SessionParticipant, SuiviMensuel,
            ReorientationCandidat, EmargementRDV, ProgrammeUtilisateur, Promotion,
            
            # Seminaire models
            Seminaire, SessionSeminaire, InvitationSeminaire, PresenceSeminaire,
            LivrableSeminaire, RenduLivrable,
            
            # Event models
            Event, InvitationEvent, PresenceEvent,
            
            # E-learning models
            RessourceElearning, ModuleElearning, ProgressionElearning,
            ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning,
            ModuleRessource,
            
            # Codev models
            SeanceCodev, PresentationCodev, ContributionCodev, ParticipationSeance,
            CycleCodev, GroupeCodev, MembreGroupeCodev,

            # Jury décision models (dépendent d'inscriptions → schéma programme)
            DecisionJuryTable, DecisionJuryCandidat,
        ]
    
    def schema_exists(self, program_code: str) -> bool:
        """Vérifie si un schéma existe"""
        schema_name = program_code.lower()
        # Utiliser une requête directe avec paramètres
        query = text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema_name")
        result = self.session.execute(query.bindparams(schema_name=schema_name)).fetchone()
        return result is not None
    
    
    
    def _create_tables_in_schema(self, schema_name: str):
        """Crée toutes les tables dans un schéma avec transactions individuelles"""
        
        print(f"🔨 Création des tables pour le schéma {schema_name}")
        print(f"📋 Modèles à traiter: {len(self.program_models)}")
        
        success_count = 0
        error_count = 0
        
        # Créer chaque table avec sa propre transaction
        for model in self.program_models:
            table_name = model.__tablename__
            
            try:
                # Transaction individuelle pour chaque table
                self._create_single_table(model, schema_name)
                success_count += 1
                print(f"✅ Table {schema_name}.{table_name} créée")
                
            except Exception as e:
                error_count += 1
                print(f"❌ Erreur création table {schema_name}.{table_name}: {e}")
                # Continue avec la table suivante même en cas d'erreur
        
        print(f"📊 Résumé: {success_count} tables créées, {error_count} erreurs")
    
    def _create_single_table(self, model, schema_name: str):
        """Crée une seule table avec sa propre transaction"""
        table_name = model.__tablename__
        
        try:
            # Générer le SQL de création de table
            table_sql = self._generate_create_table_sql(model, schema_name)
            print(f"🔧 SQL généré pour {table_name}: {table_sql[:100]}...")
            
            # Exécuter dans une transaction individuelle
            self.session.exec(text(table_sql))
            self.session.commit()
            
        except Exception as e:
            # Rollback en cas d'erreur pour cette table uniquement
            self.session.rollback()
            raise e
    
    def _generate_create_table_sql(self, model, schema_name: str) -> str:
        """Génère le SQL CREATE TABLE pour un modèle SQLModel"""
        table_name = model.__tablename__
        
        # Obtenir les colonnes du modèle
        columns = []
        for field_name, field_info in model.__fields__.items():
            if field_name == 'id' and field_info.default is None:
                columns.append("id SERIAL PRIMARY KEY")
            else:
                column_def = self._get_column_definition(field_name, field_info)
                if column_def:
                    columns.append(column_def)
        
        # Obtenir les clés étrangères
        foreign_keys = self._get_foreign_keys(model, schema_name)
        
        # Assembler le SQL
        sql_parts = [f"CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} ("]
        
        # Ajouter les colonnes avec virgules
        all_items = columns + foreign_keys
        for i, item in enumerate(all_items):
            if i == len(all_items) - 1:
                sql_parts.append(f"    {item}")  # Dernier élément sans virgule
            else:
                sql_parts.append(f"    {item},")  # Autres éléments avec virgule
        
        sql_parts.append(")")
        
        return "\n".join(sql_parts)
    
    def _get_column_definition(self, field_name: str, field_info) -> str:
        """Génère la définition d'une colonne"""
        field_type = field_info.annotation
        
        # Gérer les types Optional (Union[Type, None])
        if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
            # Extraire le type réel de Optional[Type]
            args = field_type.__args__
            if len(args) == 2 and type(None) in args:
                # C'est un Optional[Type]
                real_type = args[0] if args[1] is type(None) else args[1]
                nullable = "NULL"
            else:
                real_type = field_type
                nullable = "NOT NULL"
        else:
            real_type = field_type
            nullable = "NULL" if field_info.default is not None else "NOT NULL"
        
        # Types de base
        if real_type == str or (hasattr(real_type, '__origin__') and real_type.__origin__ is str):
            max_length = getattr(field_info, 'max_length', 255)
            return f"{field_name} VARCHAR({max_length}) {nullable}"
        
        elif real_type == int or (hasattr(real_type, '__origin__') and real_type.__origin__ is int):
            return f"{field_name} INTEGER {nullable}"
        
        elif real_type == float or (hasattr(real_type, '__origin__') and real_type.__origin__ is float):
            return f"{field_name} DECIMAL(15,2) {nullable}"
        
        elif real_type == bool or (hasattr(real_type, '__origin__') and real_type.__origin__ is bool):
            default = "DEFAULT TRUE" if field_info.default is True else "DEFAULT FALSE" if field_info.default is False else ""
            return f"{field_name} BOOLEAN {default}"
        
        # Types spéciaux
        elif hasattr(real_type, '__name__'):
            if real_type.__name__ == 'datetime':
                default = "DEFAULT CURRENT_TIMESTAMP" if field_info.default_factory else ""
                return f"{field_name} TIMESTAMP WITH TIME ZONE {default}"
            elif real_type.__name__ == 'date':
                return f"{field_name} DATE"
        
        return None
    
    def _get_foreign_keys(self, model, schema_name: str) -> list:
        """Génère les définitions de clés étrangères"""
        foreign_keys = []
        
        for field_name, field_info in model.__fields__.items():
            # Vérifier que foreign_key existe et n'est pas PydanticUndefinedType
            if (hasattr(field_info, 'foreign_key') and 
                field_info.foreign_key is not None and 
                str(field_info.foreign_key) != 'PydanticUndefined'):
                
                try:
                    fk_table = field_info.foreign_key.split('.')[0]
                    if fk_table in self.public_tables:
                        fk_ref = f"public.{fk_table}(id)"
                    else:
                        fk_ref = f"{schema_name}.{fk_table}(id)"
                    
                    foreign_keys.append(f"FOREIGN KEY ({field_name}) REFERENCES {fk_ref}")
                except (AttributeError, TypeError) as e:
                    print(f"⚠️ Erreur clé étrangère pour {field_name}: {e}")
                    continue
        
        return foreign_keys
    
    def drop_program_schema(self, program_code: str, backup_data: bool = True) -> bool:
        """Supprime un schéma de programme"""
        try:
            schema_name = program_code.lower()
            
            if backup_data:
                # TODO: Implémenter la sauvegarde des données
                pass
            
            self.session.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
            self.session.commit()
            
            return True
            
        except Exception as e:
            self.session.rollback()
            return False

# ===== UTILITAIRES POUR LES ROUTES =====

def get_schema_from_request(request: Request, programme: Optional[str] = None) -> Optional[str]:
    """
    Extrait le schéma depuis la requête (fonction principale).
    
    Ordre de priorité :
    1. Paramètre programme fourni explicitement
    2. request.state.program_schema (ajouté par le middleware)
    3. Query param 'programme'
    4. Form data 'programme' ou 'programme_code' (pour les requêtes POST)
    5. Header Referer (extraction du paramètre programme de l'URL précédente)
    """
    # 1. Paramètre programme fourni explicitement (priorité la plus haute)
    if programme:
        return programme.lower()
    
    # 2. Vérifier si le schéma est dans l'état de la requête (ajouté par le middleware)
    if hasattr(request.state, 'program_schema'):
        return request.state.program_schema
    
    # 3. Vérifier les paramètres de query
    programme = request.query_params.get('programme')
    if programme:
        return programme.lower()
    
    # 4. Vérifier les données de formulaire pour les requêtes POST
    # NOTE: request.form() est async, donc on ne peut pas l'utiliser ici de manière synchrone
    # On se fie au Referer qui contient souvent le paramètre programme de l'URL précédente
    # Les routes qui ont besoin du formulaire le liront elles-mêmes avec await request.form()
    
    # 5. Vérifier le header Referer (fallback supplémentaire)
    referer = request.headers.get("referer", "")
    if "programme=" in referer:
        import re
        match = re.search(r'programme=([^&]+)', referer)
        if match:
            return match.group(1).lower()
    
    return None

def get_schema_routing_service(
    request: Request, 
    session: Session = Depends(get_session),
    programme: Optional[str] = None
) -> SchemaRoutingService:
    """
    Dependency pour obtenir le service de routage des schémas.
    
    Args:
        request: La requête FastAPI
        session: La session de base de données
        programme: Paramètre programme optionnel (priorité la plus haute)
    
    Returns:
        SchemaRoutingService configuré avec le bon schéma
    """
    routing_service = SchemaRoutingService(session)
    
    # Définir le schéma depuis la requête (avec priorité au paramètre programme si fourni)
    schema = get_schema_from_request(request, programme=programme)
    
    # Si aucun schéma trouvé, utiliser 'acd' par défaut
    if not schema:
        schema = 'acd'
    
    # Configurer le schéma dans le service (qui configure aussi le search_path)
    routing_service.set_schema(schema)
    
    return routing_service

def get_current_program_schema(request: Request) -> str:
    """Récupère le schéma du programme actuel depuis request.state (alias de get_schema_from_request)"""
    schema = get_schema_from_request(request)
    return schema if schema else "public"

def get_current_programme_from_session(request: Request) -> Optional[str]:
    """Récupère le programme actuel depuis request.state (alias pour compatibilité)"""
    return getattr(request.state, 'current_programme', None)


# ===== INSTANCE GLOBALE ET CONFIGURATION =====

# Instance globale
schema_manager = ProgramSchemaManager()

# NOTE: ProgramSchemaMiddleware et setup_program_schemas ont été déplacés vers core/middleware.py
# pour une meilleure organisation. Le middleware est maintenant configuré via setup_all_middlewares().


# ===== EXPORTS PRINCIPAUX =====
__all__ = [
    'SchemaRoutingService', 
    'ProgramSchemaService',
    'ProgramSchemaManager',
    'get_schema_from_request',
    'get_schema_routing_service',
    'get_current_program_schema',
    'get_current_programme_from_session',
    'table_exists_anywhere',
    'safe_count_query',
]

