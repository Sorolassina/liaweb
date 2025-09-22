"""
Système de schémas par programme - Tout en un
Gère la création dynamique des schémas, le routage des requêtes et les modèles conscients des schémas
"""
from typing import Optional, Union, Type, Dict, Any, List
from fastapi import FastAPI, Request, Depends, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import SQLModel, Session, create_engine, text, Field
from app_lia_web.core.database import get_session
from app_lia_web.app.models.base import (
    Programme, User, Partenaire, Groupe, PasswordRecoveryCode,
    Candidat, Preinscription, Inscription, Entreprise, Document, 
    Eligibilite, Jury, MembreJury, DecisionJuryTable, EtapePipeline,
    AvancementEtape, ActionHandicap, RendezVous, SessionProgramme,
    SessionParticipant, SuiviMensuel, DecisionJuryCandidat,
    ReorientationCandidat, EmargementRDV, ProgrammeUtilisateur, Promotion
)
from app_lia_web.app.models.seminaire import (
    Seminaire, SessionSeminaire, InvitationSeminaire, PresenceSeminaire,
    LivrableSeminaire, RenduLivrable
)
from app_lia_web.app.models.event import (
    Event, InvitationEvent, PresenceEvent
)
from app_lia_web.app.models.elearning import (
    RessourceElearning, ModuleElearning, ProgressionElearning, 
    ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning, 
    ModuleRessource
)
from app_lia_web.app.models.codev import (
    SeanceCodev, PresentationCodev, ContributionCodev, ParticipationSeance,
    CycleCodev, GroupeCodev, MembreGroupeCodev
)
import logging

logger = logging.getLogger(__name__)

# ===== CLASSES DE BASE POUR LES MODÈLES CONSCIENTS DES SCHÉMAS =====

class SchemaAwareModel(SQLModel):
    """Classe de base pour les modèles conscients des schémas"""
    
    @classmethod
    def get_table_name(cls) -> str:
        """Retourne le nom de la table"""
        return cls.__tablename__ if hasattr(cls, '__tablename__') else cls.__name__.lower()
    
    @classmethod
    def get_schema_name(cls, program_code: str = None) -> str:
        """Retourne le nom du schéma selon le programme"""
        if program_code:
            return program_code.lower()
        return "public"
    
    @classmethod
    def get_full_table_name(cls, program_code: str = None) -> str:
        """Retourne le nom complet de la table avec schéma"""
        schema = cls.get_schema_name(program_code)
        table = cls.get_table_name()
        return f"{schema}.{table}"
    
    @classmethod
    def configure_for_schema(cls, program_code: str) -> Dict[str, Any]:
        """Configure le modèle pour un schéma spécifique"""
        return {
            "__tablename__": cls.get_table_name(),
            "__table_args__": {
                "schema": cls.get_schema_name(program_code)
            }
        }

def create_schema_aware_model(base_model: SQLModel, program_code: str) -> SQLModel:
    """Crée une version du modèle configurée pour un schéma spécifique"""
    
    class SchemaSpecificModel(base_model):
        __tablename__ = base_model.__tablename__ if hasattr(base_model, '__tablename__') else base_model.__name__.lower()
        __table_args__ = {
            "schema": program_code.lower()
        }
    
    # Copier tous les attributs du modèle de base
    for attr_name in dir(base_model):
        if not attr_name.startswith('_') and not callable(getattr(base_model, attr_name)):
            setattr(SchemaSpecificModel, attr_name, getattr(base_model, attr_name))
    
    return SchemaSpecificModel

# ===== SERVICE DE ROUTAGE DES REQUÊTES =====

class SchemaRoutingService:
    """Service pour router les requêtes vers les bons schémas"""
    
    def __init__(self, session: Session):
        self.session = session
        self.current_schema: Optional[str] = None
    
    def set_schema(self, schema_name: str):
        """Définit le schéma actuel"""
        self.current_schema = schema_name.lower()
        logger.info(f"Schéma défini: {self.current_schema}")
    
    def get_schema(self) -> Optional[str]:
        """Retourne le schéma actuel"""
        return self.current_schema
    
    def execute_in_schema(self, sql: str, params: Dict[str, Any] = None, schema: str = None) -> Any:
        """Exécute une requête SQL dans un schéma spécifique"""
        target_schema = schema or self.current_schema or "public"
        
        # Remplacer les références de table par des références complètes avec schéma
        sql_with_schema = self._add_schema_to_sql(sql, target_schema)
        
        logger.debug(f"Exécution SQL dans schéma {target_schema}: {sql_with_schema}")
        return self.session.execute(text(sql_with_schema), params or {})
    
    def _add_schema_to_sql(self, sql: str, schema: str) -> str:
        """Ajoute le schéma aux références de tables dans le SQL"""
        # Tables qui restent dans le schéma public
        public_tables = {
            'user', 'programme', 'partenaire', 'groupe', 'password_recovery_code',
            'jurys', 'promotions', 'groupes'
        }
        
        # Tables qui vont dans le schéma du programme
        program_tables = {
            'candidats', 'preinscriptions', 'inscriptions', 'entreprises', 
            'documents', 'eligibilites', 'jury_decisions', 'rendez_vous',
            'session_programmes', 'session_participants', 'suivi_mensuels',
            'decision_jury_candidats', 'reorientation_candidats', 
            'emargement_rdvs', 'programme_utilisateurs', 'action_handicaps',
            'avancement_etapes', 'etape_pipelines', 'membre_jurys',
            'seminaires', 'session_seminaires', 'invitation_seminaires',
            'presence_seminaires', 'livrable_seminaires', 'rendu_livrables',
            'events', 'invitation_events', 'presence_events',
            'ressource_elearnings', 'module_elearnings', 'progression_elearnings',
            'objectif_elearnings', 'quiz_elearnings', 'reponse_quizs',
            'certificat_elearnings', 'module_ressources',
            'seance_codevs', 'presentation_codevs', 'contribution_codevs',
            'participation_seances', 'cycle_codevs', 'groupe_codevs',
            'membre_groupe_codevs'
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
        
        # Créer une nouvelle classe qui hérite du modèle original
        class SchemaSpecificModel(model_class):
            __tablename__ = model_class.__tablename__ if hasattr(model_class, '__tablename__') else model_class.__name__.lower()
            __table_args__ = {
                "schema": target_schema
            }
        
        # Copier les métadonnées du modèle original
        SchemaSpecificModel.__name__ = f"{model_class.__name__}_{target_schema}"
        SchemaSpecificModel.__qualname__ = f"{model_class.__qualname__}_{target_schema}"
        
        return SchemaSpecificModel

# ===== MIDDLEWARE POUR LE ROUTAGE DES SCHÉMAS =====

class ProgramSchemaMiddleware(BaseHTTPMiddleware):
    """Middleware pour router automatiquement vers le bon schéma selon le programme"""
    
    async def dispatch(self, request: Request, call_next):
        # Extraire le programme de l'URL ou des paramètres
        programme_code = self._extract_program_from_request(request)
        
        if programme_code:
            # Stocker le programme en session pour la persistance
            if not hasattr(request, 'session'):
                # Initialiser la session si elle n'existe pas
                request.session = {}
            
            request.session['current_programme'] = programme_code
            logger.info(f"Programme {programme_code} stocké en session")
            
            # Vérifier si le schéma existe
            session = next(get_session())
            try:
                schema_service = ProgramSchemaService(session)
                
                if not schema_service.schema_exists(programme_code):
                    logger.warning(f"Schéma {programme_code} n'existe pas, création automatique")
                    schema_service.create_program_schema(programme_code)
                
                # Ajouter le schéma au contexte de la requête
                request.state.program_schema = programme_code.lower()
                
                # Créer un service de routage pour cette requête
                routing_service = SchemaRoutingService(session)
                routing_service.set_schema(programme_code.lower())
                request.state.schema_routing_service = routing_service
                
                logger.info(f"Requête routée vers le schéma: {programme_code.lower()}")
                
            except Exception as e:
                logger.error(f"Erreur lors de la gestion du schéma {programme_code}: {e}")
            finally:
                session.close()
        else:
            # Si aucun programme détecté, récupérer depuis la session
            programme_code = None
            
            # Vérifier si la session est disponible
            try:
                # Cette ligne peut lever une exception si SessionMiddleware n'est pas installé
                session_available = hasattr(request, 'session')
                if session_available and 'current_programme' in request.session:
                    programme_code = request.session['current_programme']
                    logger.info(f"Programme {programme_code} récupéré depuis la session")
            except Exception as e:
                logger.warning(f"Session non disponible: {e}")
                session_available = False
            
            if programme_code:
                # Configurer le schéma depuis la session
                session = next(get_session())
                try:
                    schema_service = ProgramSchemaService(session)
                    
                    if not schema_service.schema_exists(programme_code):
                        logger.warning(f"Schéma {programme_code} n'existe pas, création automatique")
                        schema_service.create_program_schema(programme_code)
                    
                    # Ajouter le schéma au contexte de la requête
                    request.state.program_schema = programme_code.lower()
                    
                    # Créer un service de routage pour cette requête
                    routing_service = SchemaRoutingService(session)
                    routing_service.set_schema(programme_code.lower())
                    request.state.schema_routing_service = routing_service
                    
                    logger.info(f"Requête routée vers le schéma depuis session: {programme_code.lower()}")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de la gestion du schéma {programme_code}: {e}")
                finally:
                    session.close()
            else:
                # Aucun programme en session, utiliser le schéma public par défaut
                request.state.program_schema = 'public'
                logger.info("Aucun programme en session, utilisation du schéma public")
        
        response = await call_next(request)
        return response
    
    def _extract_program_from_request(self, request: Request) -> str:
        """Extrait le code du programme de la requête"""
        
        # Méthode 2: Depuis les paramètres de query
        programme = request.query_params.get('programme')
        if programme and self._is_valid_program_code(programme.upper()):
            return programme.upper()
        
        # Méthode 3: Depuis les données de formulaire (pour les requêtes POST)
        if request.method == 'POST':
            try:
                form_data = request.form()
                programme = form_data.get('programme')
                if programme and self._is_valid_program_code(programme.upper()):
                    return programme.upper()
            except:
                pass
        
        # Méthode 4: Depuis les headers
        programme = request.headers.get('X-Programme')
        if programme and self._is_valid_program_code(programme.upper()):
            return programme.upper()

        # Méthode 1: Depuis l'URL (ex: /ACD/candidats, /CODEV/sessions)
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
            from app_lia_web.app.models.base import Programme
            from sqlmodel import Session, select
            
            # Créer une session temporaire
            session = next(get_session())
            try:
                # Chercher le programme par code
                programme = session.exec(
                    select(Programme).where(
                        Programme.code == code,
                        Programme.actif == True
                    )
                ).first()
                return programme is not None
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification du programme {code}: {e}")
            return False

# ===== SERVICE DE GESTION DES SCHÉMAS =====

class ProgramSchemaService:
    """Service pour gérer les schémas de base de données par programme"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_program_schema(self, program_code: str) -> bool:
        """Crée un schéma complet pour un programme"""
        try:
            schema_name = program_code.lower()
            
            # Vérifier si le schéma existe déjà
            if self._schema_exists(schema_name):
                logger.info(f"Le schéma {schema_name} existe déjà")
                return True
            
            # Créer le schéma
            self.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            
            # Créer les tables (copie des tables existantes)
            self._create_tables_in_schema(schema_name)
            
            # Créer les index
            self._create_indexes_in_schema(schema_name)
            
            self.session.commit()
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
            """), {"schema_name": schema_name})
            
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
        """), {"schema_name": schema_name})
        
        return result.fetchone()[0]
    
    def _create_tables_in_schema(self, schema_name: str):
        """Crée toutes les tables dans un schéma (toutes sauf user, programme, partenaire, groupe)"""
        tables_sql = {
            'candidats': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.candidats (
                    id SERIAL PRIMARY KEY,
                    civilite VARCHAR(10),
                    nom VARCHAR(100) NOT NULL,
                    prenom VARCHAR(100) NOT NULL,
                    date_naissance DATE,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    telephone VARCHAR(20),
                    adresse_personnelle TEXT,
                    niveau_etudes VARCHAR(100),
                    secteur_activite VARCHAR(100),
                    photo_profil VARCHAR(255),
                    statut VARCHAR(20) DEFAULT 'EN_ATTENTE',
                    lat DECIMAL(10,8),
                    lng DECIMAL(11,8),
                    handicap BOOLEAN DEFAULT FALSE,
                    type_handicap VARCHAR(50),
                    besoins_accommodation TEXT,
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'preinscriptions': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.preinscriptions (
                    id SERIAL PRIMARY KEY,
                    programme_id INTEGER REFERENCES public.programmes(id),
                    candidat_id INTEGER REFERENCES {schema_name}.candidats(id),
                    source VARCHAR(50),
                    donnees_brutes_json TEXT,
                    statut VARCHAR(20) DEFAULT 'SOUMIS',
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'inscriptions': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.inscriptions (
                    id SERIAL PRIMARY KEY,
                    programme_id INTEGER REFERENCES public.programmes(id),
                    candidat_id INTEGER REFERENCES {schema_name}.candidats(id),
                    promotion_id INTEGER REFERENCES public.promotions(id),
                    groupe_id INTEGER REFERENCES public.groupes(id),
                    conseiller_id INTEGER REFERENCES public.user(id),
                    referent_id INTEGER REFERENCES public.user(id),
                    statut VARCHAR(20) DEFAULT 'EN_COURS',
                    date_decision TIMESTAMP WITH TIME ZONE,
                    email_confirmation_envoye BOOLEAN DEFAULT FALSE,
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'entreprises': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.entreprises (
                    id SERIAL PRIMARY KEY,
                    candidat_id INTEGER REFERENCES {schema_name}.candidats(id),
                    nom_entreprise VARCHAR(255),
                    siret VARCHAR(14),
                    adresse TEXT,
                    chiffre_affaires DECIMAL(15,2),
                    date_creation DATE,
                    secteur_activite VARCHAR(100),
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'documents': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.documents (
                    id SERIAL PRIMARY KEY,
                    candidat_id INTEGER REFERENCES {schema_name}.candidats(id),
                    type_document VARCHAR(50),
                    nom_fichier VARCHAR(255),
                    chemin_fichier TEXT,
                    taille_fichier INTEGER,
                    depose_par INTEGER REFERENCES public.user(id),
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'eligibilites': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.eligibilites (
                    id SERIAL PRIMARY KEY,
                    preinscription_id INTEGER REFERENCES {schema_name}.preinscriptions(id),
                    ca_seuil_ok BOOLEAN,
                    ca_score DECIMAL(5,2),
                    qpv_ok BOOLEAN,
                    anciennete_ok BOOLEAN,
                    anciennete_annees INTEGER,
                    verdict VARCHAR(20),
                    details_json TEXT,
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'jury_decisions': f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.jury_decisions (
                    id SERIAL PRIMARY KEY,
                    candidat_id INTEGER REFERENCES {schema_name}.candidats(id),
                    jury_id INTEGER REFERENCES public.jurys(id),
                    decision VARCHAR(20),
                    commentaires TEXT,
                    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """
        }
        
        for table_name, sql in tables_sql.items():
            self.session.execute(text(sql))
    
    def _create_indexes_in_schema(self, schema_name: str):
        """Crée les index dans un schéma"""
        indexes = [
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_candidats_email ON {schema_name}.candidats(email)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_candidats_nom ON {schema_name}.candidats(nom)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_preinscriptions_programme ON {schema_name}.preinscriptions(programme_id)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_inscriptions_programme ON {schema_name}.inscriptions(programme_id)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_entreprises_siret ON {schema_name}.entreprises(siret)",
        ]
        
        for index_sql in indexes:
            self.session.execute(text(index_sql))

# ===== GESTIONNAIRE PRINCIPAL DES SCHÉMAS =====

class ProgramSchemaManager:
    """Gestionnaire centralisé des schémas par programme"""
    
    def __init__(self):
        self.session = next(get_session())
        
        # Tables qui restent dans le schéma public
        self.public_tables = {
            'user', 'programme', 'partenaire', 'groupe', 'password_recovery_code'
        }
        
        # Tous les modèles SQLModel (sauf ceux du public)
        self.program_models = [
            # Base models
            Candidat, Preinscription, Inscription, Entreprise, Document,
            Eligibilite, Jury, MembreJury, DecisionJuryTable, EtapePipeline,
            AvancementEtape, ActionHandicap, RendezVous, SessionProgramme,
            SessionParticipant, SuiviMensuel, DecisionJuryCandidat,
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
            CycleCodev, GroupeCodev, MembreGroupeCodev
        ]
    
    def schema_exists(self, program_code: str) -> bool:
        """Vérifie si un schéma existe"""
        schema_name = program_code.lower()
        # Utiliser une requête directe avec paramètres
        query = text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema_name")
        result = self.session.execute(query, {"schema_name": schema_name}).fetchone()
        return result is not None
    
    def create_program_schema(self, program_code: str) -> bool:
        """Crée un schéma complet pour un programme"""
        try:
            schema_name = program_code.lower()
            
            # ÉTAPE 1: Créer le schéma (séparé)
            self._create_schema_if_not_exists(schema_name)
            
            # ÉTAPE 2: Créer toutes les tables (avec transactions individuelles)
            self._create_tables_in_schema(schema_name)
            
            print(f"✅ Schéma {schema_name} créé avec succès")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la création du schéma {program_code}: {e}")
            return False
    
    def _create_schema_if_not_exists(self, schema_name: str):
        """Crée le schéma s'il n'existe pas"""
        try:
            self.session.exec(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            self.session.commit()
            print(f"✅ Schéma {schema_name} créé/vérifié")
        except Exception as e:
            print(f"❌ Erreur création schéma {schema_name}: {e}")
            self.session.rollback()
            raise
    
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
            
            self.session.exec(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
            self.session.commit()
            
            return True
            
        except Exception as e:
            self.session.rollback()
            return False
    
    def get_all_program_schemas(self) -> list:
        """Retourne la liste de tous les schémas de programmes"""
        result = self.session.exec(
            text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
                ORDER BY schema_name
            """)
        ).all()
        return [row[0] for row in result]

# ===== UTILITAIRES POUR LES ROUTES =====

def get_schema_from_request(request: Request) -> Optional[str]:
    """Extrait le schéma depuis la requête"""
    # Vérifier si le schéma est dans l'état de la requête (ajouté par le middleware)
    if hasattr(request.state, 'program_schema'):
        return request.state.program_schema
    
    # Vérifier les paramètres de query
    programme = request.query_params.get('programme')
    if programme:
        return programme.lower()
    
    # Vérifier les données de formulaire pour les requêtes POST
    if request.method == 'POST':
        try:
            form_data = request.form()
            programme = form_data.get('programme')
            if programme:
                return programme.lower()
        except:
            pass
    
    return None

def get_schema_routing_service(request: Request, session: Session = Depends(get_session)) -> SchemaRoutingService:
    """Dependency pour obtenir le service de routage des schémas"""
    routing_service = SchemaRoutingService(session)
    
    # Définir le schéma depuis la requête
    schema = get_schema_from_request(request)
    if schema:
        routing_service.set_schema(schema)
    
    return routing_service

def get_current_schema(request: Request) -> Optional[str]:
    """Dependency pour obtenir le schéma actuel"""
    return get_schema_from_request(request)

def execute_in_current_schema(
    routing_service: SchemaRoutingService,
    sql: str,
    params: Dict[str, Any] = None
) -> Any:
    """Exécute une requête SQL dans le schéma actuel"""
    return routing_service.execute_in_schema(sql, params)

def get_model_for_current_schema(
    routing_service: SchemaRoutingService,
    model_class: Type
) -> Type:
    """Retourne une version du modèle configurée pour le schéma actuel"""
    return routing_service.get_model_for_schema(model_class)

def create_schema_aware_query(
    routing_service: SchemaRoutingService,
    model_class: Type,
    filters: Dict[str, Any] = None
) -> str:
    """Crée une requête SQL consciente du schéma"""
    schema = routing_service.get_schema() or "public"
    table_name = model_class.__tablename__ if hasattr(model_class, '__tablename__') else model_class.__name__.lower()
    
    # Construire la requête SELECT
    sql = f"SELECT * FROM {schema}.{table_name}"
    
    if filters:
        conditions = []
        for key, value in filters.items():
            if isinstance(value, str):
                conditions.append(f"{key} = '{value}'")
            else:
                conditions.append(f"{key} = {value}")
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
    
    return sql

def get_schema_aware_session(request: Request, session: Session = Depends(get_session)) -> SchemaRoutingService:
    """Dependency pour obtenir une session consciente des schémas"""
    routing_service = SchemaRoutingService(session)
    
    # Définir le schéma depuis la requête
    schema = get_schema_from_request(request)
    if schema:
        routing_service.set_schema(schema)
        logger.info(f"Session configurée pour le schéma: {schema}")
    
    return routing_service

# ===== INSTANCE GLOBALE ET CONFIGURATION =====

# Instance globale
schema_manager = ProgramSchemaManager()

def setup_program_schemas(app: FastAPI):
    """Configure le système de schémas par programme"""
    
    # Ajouter le middleware pour le routage des schémas
    app.add_middleware(ProgramSchemaMiddleware)
    
    # Créer les schémas pour tous les programmes existants au démarrage
    @app.on_event("startup")
    async def create_program_schemas():
        try:
            print("🚀 Début de l'initialisation des schémas par programme")
            
            # Créer une nouvelle session pour le démarrage
            session = next(get_session())
            manager = ProgramSchemaManager()
            manager.session = session
            
            # Créer les schémas pour tous les programmes actifs
            programmes = session.exec(
                text("SELECT code FROM public.programme WHERE actif = true")
            ).all()
            
            print(f"📋 Programmes trouvés: {[p[0] for p in programmes]}")
            
            for programme_code in programmes:
                if not manager.schema_exists(programme_code[0]):
                    print(f"🔨 Création du schéma pour le programme {programme_code[0]}")
                    success = manager.create_program_schema(programme_code[0])
                    if success:
                        print(f"✅ Schéma {programme_code[0]} créé avec succès")
                    else:
                        pass
                        # logger.error(f"❌ Échec de création du schéma {programme_code[0]}")
                else:
                    print(f"ℹ️ Schéma {programme_code[0]} existe déjà")
            
            session.close()
            print("🎉 Initialisation des schémas par programme terminée")
            
        except Exception as e:
            # logger.error(f"💥 Erreur lors de l'initialisation des schémas: {e}")
            import traceback
            # logger.error(traceback.format_exc())

def get_current_programme_from_session(request: Request) -> Optional[str]:
    """Récupère le programme actuel depuis la session utilisateur"""
    if hasattr(request, 'session') and 'current_programme' in request.session:
        return request.session['current_programme']
    return None

def set_current_programme_in_session(request: Request, programme_code: str) -> None:
    """Définit le programme actuel dans la session utilisateur"""
    if not hasattr(request, 'session'):
        request.session = {}
    request.session['current_programme'] = programme_code.upper()

def get_program_schema_from_request(request: Request) -> str:
    """Extrait le schéma du programme depuis la requête"""
    return getattr(request.state, 'program_schema', None)

def configure_sqlmodel_schema(request: Request):
    """Configure SQLModel pour utiliser le bon schéma selon la requête"""
    schema = get_program_schema_from_request(request)
    
    if schema:
        # Configurer le search_path pour utiliser le schéma du programme
        from app_lia_web.core.database import engine
        with engine.connect() as conn:
            conn.execute(text(f"SET search_path TO {schema}, public"))
            conn.commit()
    
    return schema

def get_schema_manager() -> ProgramSchemaManager:
    """Retourne l'instance du gestionnaire de schémas"""
    return schema_manager

# ===== EXEMPLE D'UTILISATION DANS UNE ROUTE =====
"""
@router.get("/candidats")
async def get_candidats(
    request: Request,
    routing_service: SchemaRoutingService = Depends(get_schema_aware_session)
):
    # Utiliser le service de routage pour exécuter la requête
    sql = "SELECT * FROM candidats"
    result = routing_service.execute_in_schema(sql)
    
    # Ou utiliser une requête construite
    sql = create_schema_aware_query(routing_service, Candidat)
    result = routing_service.execute_in_schema(sql)
    
    return result.fetchall()
"""