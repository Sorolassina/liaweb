"""
Configuration de la base de données PostgreSQL pour Tieka

Ce module configure la connexion à PostgreSQL avec SQLModel et fournit
les sessions de base de données pour l'application.
"""

# app/core/database.py
from typing import Generator
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import text
from .config import settings
import logging
from fastapi import Request, Depends
from typing import Optional
from fastapi.security import OAuth2PasswordBearer

# Importer SEULEMENT les modèles qui doivent rester dans le schéma public
from ..models.base import (
    User, Programme, Partenaire, Groupe, PasswordRecoveryCode, ProgrammeUtilisateur, Promotion
)
from ..models.jury import Jury, MembreJury, DecisionJuryTable, DecisionJuryCandidat
from ..models.activity import ActivityLog
from ..models.message import Conversation, Message

# Configuration du logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schéma OAuth2 pour l'authentification (token via /auth/token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# Liste des modèles qui restent dans le schéma public
public_models = [
    User, Programme, Partenaire, Groupe, PasswordRecoveryCode,
    ProgrammeUtilisateur, Promotion,
    Jury, MembreJury,
    ActivityLog, Conversation, Message
]

# Engine SQLModel
CONNECT_ARGS = {
    "options": "-c client_encoding=UTF8",
    "client_encoding": "utf8"
}
engine = create_engine(
    settings.DATABASE_URL,   # ex: "postgresql://user:pass@localhost:5432/db"
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args=CONNECT_ARGS
)
print("✅",settings.DATABASE_URL)

def create_db_and_tables() -> None:
    """
    Crée SEULEMENT les tables du schéma public (système).
    Effectue également la migration automatique des colonnes pour ces tables.
    """
    try:       
        from sqlmodel import MetaData
        from sqlalchemy import inspect
        
        # Créer les métadonnées pour les tables publiques seulement
        public_metadata = MetaData()
        
        # Ajouter les tables publiques aux métadonnées
        for model in public_models:
            if hasattr(model, '__table__'):
                public_metadata.create_all(bind=engine, tables=[model.__table__])
        
        logger.info(f"✅ Tables publiques (système) créées avec succès")
        
        # === MIGRATION AUTOMATIQUE DES COLONNES DES TABLES PUBLIQUES ===
        logger.info("🔄 Migration automatique des colonnes des tables publiques...")
        inspector = inspect(engine)
        identifier_preparer = engine.dialect.identifier_preparer

        def quote_table(name: str) -> str:
            if "." in name:
                schema_name, table_only = name.split(".", 1)
                return f"{identifier_preparer.quote_schema(schema_name)}.{identifier_preparer.quote(table_only)}"
            return identifier_preparer.quote(name)

        def quote_column(name: str) -> str:
            return identifier_preparer.quote(name)
        
        # Mapping des tables publiques à leurs modèles SQLModel
        public_models_dict = {
            'user': User,
            'programme': Programme,
            'partenaire': Partenaire,
            'groupe': Groupe,
            'password_recovery_code': PasswordRecoveryCode,
            'programme_utilisateur': ProgrammeUtilisateur,
            'promotion': Promotion,
            'jury': Jury,
            'membre_jury': MembreJury,
            'activity_log': ActivityLog,
            'conversation': Conversation,
            'message': Message,
        }
        
        columns_added = []
        migration_errors = []
        
        # Créer une session pour les migrations
        session = Session(engine)
        try:
            for table_name, model_class in public_models_dict.items():
                try:
                    if inspector.has_table(table_name):
                        # Récupérer les colonnes existantes dans la base
                        existing_columns = {col['name']: str(col['type']) for col in inspector.get_columns(table_name)}
                        
                        # Récupérer les colonnes attendues depuis le modèle SQLModel
                        model_columns = {}
                        if hasattr(model_class, '__table__'):
                            for col_name, col in model_class.__table__.columns.items():
                                # Convertir le type SQLAlchemy en string SQL
                                sql_type = str(col.type)
                                # Convertir les ENUM en VARCHAR pour compatibilité
                                if 'ENUM' in sql_type.upper() or hasattr(col.type, 'enums'):
                                    sql_type = "VARCHAR(50)"
                                elif 'TEXT' in sql_type.upper():
                                    sql_type = "TEXT"
                                elif 'INTEGER' in sql_type.upper() or 'INT' in sql_type.upper():
                                    sql_type = "INTEGER"
                                elif 'BOOLEAN' in sql_type.upper() or 'BOOL' in sql_type.upper():
                                    sql_type = "BOOLEAN"
                                elif 'DATE' in sql_type.upper():
                                    sql_type = "DATE"
                                elif 'TIMESTAMP' in sql_type.upper():
                                    sql_type = "TIMESTAMP WITH TIME ZONE"
                                elif 'FLOAT' in sql_type.upper() or 'REAL' in sql_type.upper():
                                    sql_type = "REAL"
                                elif 'NUMERIC' in sql_type.upper() or 'DECIMAL' in sql_type.upper():
                                    sql_type = "NUMERIC"
                                
                                model_columns[col_name] = sql_type
                        
                        # Trouver les colonnes manquantes
                        missing_columns = {col: sql_type for col, sql_type in model_columns.items() if col not in existing_columns}
                        
                        # Vérifier et mettre à jour les types de colonnes qui ont changé (ex: VARCHAR(255) -> TEXT)
                        columns_to_update = {}
                        for col_name, expected_type in model_columns.items():
                            if col_name in existing_columns:
                                existing_type = existing_columns[col_name].upper()
                                expected_type_upper = expected_type.upper()
                                # Si la colonne existe mais a un type différent (ex: VARCHAR(255) vs TEXT)
                                if expected_type_upper == "TEXT" and "VARCHAR" in existing_type:
                                    columns_to_update[col_name] = expected_type
                        
                        # Mettre à jour les types de colonnes
                        if columns_to_update:
                            logger.info(f"🔧 Mise à jour du type de {len(columns_to_update)} colonne(s) dans {table_name}: {list(columns_to_update.keys())}")
                            for col_name, new_type in columns_to_update.items():
                                try:
                                    quoted_table = quote_table(table_name)
                                    quoted_column = quote_column(col_name)
                                    alter_sql = (
                                        f"ALTER TABLE {quoted_table} "
                                        f"ALTER COLUMN {quoted_column} TYPE {new_type} USING {quoted_column}::{new_type}"
                                    )
                                    logger.info(f"   → {alter_sql}")
                                    session.execute(text(alter_sql))
                                    session.commit()
                                    logger.info(f"   ✅ Type de colonne {col_name} mis à jour à {new_type} dans {table_name}")
                                except Exception as e:
                                    logger.error(f"   ❌ Erreur lors de la mise à jour du type de {col_name} dans {table_name}: {e}")
                                    session.rollback()
                                    migration_errors.append(f"Erreur lors de la mise à jour du type de {table_name}.{col_name}: {e}")
                        
                        # Ajouter les colonnes manquantes
                        if missing_columns:
                            logger.info(f"🔧 Ajout de {len(missing_columns)} colonne(s) manquante(s) dans {table_name}: {list(missing_columns.keys())}")
                            for col_name, sql_type in missing_columns.items():
                                try:
                                    col_def = model_class.__table__.columns[col_name]
                                    
                                    # Construire la clause DEFAULT si nécessaire
                                    default_clause = ""
                                    if col_def.default is not None:
                                        if hasattr(col_def.default, 'arg'):
                                            default_value = col_def.default.arg
                                            if isinstance(default_value, bool):
                                                default_clause = f" DEFAULT {str(default_value).upper()}"
                                            elif isinstance(default_value, (int, float)):
                                                default_clause = f" DEFAULT {default_value}"
                                            elif isinstance(default_value, str):
                                                default_clause = f" DEFAULT '{default_value}'"
                                    
                                    # Construire la clause NULL/NOT NULL
                                    nullable_clause = "" if col_def.nullable else " NOT NULL"
                                    
                                    # Construire et exécuter l'ALTER TABLE
                                    quoted_table = quote_table(table_name)
                                    quoted_column = quote_column(col_name)
                                    alter_sql = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {sql_type}{nullable_clause}{default_clause}"
                                    logger.info(f"   → {alter_sql}")
                                    
                                    session.execute(text(alter_sql))
                                    session.commit()
                                    
                                    columns_added.append(f"{table_name}.{col_name}")
                                    logger.info(f"   ✅ Colonne {col_name} ajoutée à {table_name}")
                                    
                                except Exception as e:
                                    logger.error(f"   ❌ Erreur lors de l'ajout de la colonne {col_name} à {table_name}: {e}")
                                    session.rollback()
                                    migration_errors.append(f"Erreur lors de l'ajout de {table_name}.{col_name}: {e}")
                        else:
                            logger.info(f"✅ Table {table_name} à jour")
                    else:
                        logger.warning(f"⚠️ Table {table_name} n'existe pas - sera créée par create_db_and_tables()")
                        
                except Exception as e:
                    logger.error(f"Erreur lors de la vérification des colonnes de {table_name}: {e}")
                    migration_errors.append(f"Erreur lors de la vérification de {table_name}: {e}")
            
            if columns_added:
                logger.info(f"✅ Migration terminée: {len(columns_added)} colonne(s) ajoutée(s)")
            if migration_errors:
                logger.warning(f"⚠️ {len(migration_errors)} erreur(s) lors de la migration")
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des tables publiques: {e}")
        logger.info("💡 Merci de que votre base de données soit configurée correctement...")
        

def create_program_schemas_and_tables() -> None:
    """
    Crée les schémas pour tous les programmes existants et leurs tables.
    Effectue également la migration automatique des colonnes pour les tables par programme.
    
    Cette fonction :
    1. Interroge la table programme pour obtenir les codes de programmes
    2. Pour chaque programme, crée le schéma s'il n'existe pas
    3. Crée toutes les tables dans ce schéma
    4. Migre les colonnes manquantes pour chaque table dans chaque schéma
    """
    try:
        from .program_schema_integration import ProgramSchemaManager
        from sqlalchemy import inspect
        
        # Créer une session
        session = Session(engine)
        manager = ProgramSchemaManager(session=session)  # Passer la session au constructeur
        
        try:
            # Interroger la table programme pour obtenir les codes
            # On utilise une requête SQL brute pour éviter les problèmes de colonnes manquantes
            programmes_query = text("""
                SELECT code 
                FROM programme 
                WHERE actif = true
            """)
            result = session.exec(programmes_query)
            programme_codes = [row[0] for row in result]  # Extraire le premier élément de chaque Row
            
            if not programme_codes:
                logger.info("ℹ️ Aucun programme actif trouvé - aucun schéma à créer")
                return
            
            logger.info(f"📋 Programmes trouvés: {programme_codes}")
            
            # Mapping des tables par programme à leurs modèles SQLModel
            # Utiliser directement les modèles de ProgramSchemaManager pour garantir la cohérence
            program_models_dict = {}
            for model in manager.program_models:
                if hasattr(model, '__tablename__'):
                    table_name = model.__tablename__
                    program_models_dict[table_name] = model
            
            logger.info(f"📋 Tables par programme à migrer: {list(program_models_dict.keys())}")
            
            inspector = inspect(engine)
            
            # Pour chaque programme, créer le schéma et les tables
            for programme_code in programme_codes:
                schema_name = programme_code.lower()
                
                # Vérifier si le schéma existe déjà
                schema_exists_query = text(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema_name"
                ).bindparams(schema_name=schema_name)
                schema_exists = session.exec(schema_exists_query).first()
                
                if not schema_exists:
                    # Créer le schéma
                    logger.info(f"🔨 Création du schéma {schema_name} pour le programme {programme_code}")
                    session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                    session.commit()
                    logger.info(f"✅ Schéma {schema_name} créé")
                else:
                    logger.info(f"ℹ️ Schéma {schema_name} existe déjà")
                
                # Créer les tables dans le schéma (même si le schéma existait déjà)
                logger.info(f"🔨 Création des tables pour le schéma {schema_name}")
                manager._create_tables_in_schema(schema_name)
                logger.info(f"✅ Tables créées pour le schéma {schema_name}")
                
                # === MIGRATION AUTOMATIQUE DES COLONNES DES TABLES PAR PROGRAMME ===
                logger.info(f"🔄 Migration automatique des colonnes pour le schéma {schema_name}...")
                columns_added = []
                migration_errors = []
                
                # Basculer vers le schéma pour les vérifications
                session.execute(text(f"SET search_path TO {schema_name}, public"))
                
                for table_name, model_class in program_models_dict.items():
                    try:
                        # Vérifier si la table existe dans ce schéma
                        table_exists_query = text("""
                            SELECT table_name 
                            FROM information_schema.tables 
                            WHERE table_schema = :schema_name AND table_name = :table_name
                        """).bindparams(schema_name=schema_name, table_name=table_name)
                        table_exists = session.exec(table_exists_query).first()
                        
                        if table_exists:
                            # Récupérer les colonnes existantes dans la base
                            columns_query = text("""
                                SELECT column_name, data_type, character_maximum_length
                                FROM information_schema.columns
                                WHERE table_schema = :schema_name AND table_name = :table_name
                            """).bindparams(schema_name=schema_name, table_name=table_name)
                            
                            existing_columns = {}
                            for row in session.exec(columns_query):
                                col_name = row.column_name
                                col_type = row.data_type
                                # Construire le type complet
                                if col_type == 'character varying' and row.character_maximum_length:
                                    col_type = f"VARCHAR({row.character_maximum_length})"
                                existing_columns[col_name] = col_type
                            
                            # Récupérer les colonnes attendues depuis le modèle SQLModel
                            model_columns = {}
                            if hasattr(model_class, '__table__'):
                                for col_name, col in model_class.__table__.columns.items():
                                    # Convertir le type SQLAlchemy en string SQL
                                    sql_type = str(col.type)
                                    # Convertir les ENUM en VARCHAR pour compatibilité
                                    if 'ENUM' in sql_type.upper() or hasattr(col.type, 'enums'):
                                        sql_type = "VARCHAR(50)"
                                    elif 'TEXT' in sql_type.upper():
                                        sql_type = "TEXT"
                                    elif 'INTEGER' in sql_type.upper() or 'INT' in sql_type.upper():
                                        sql_type = "INTEGER"
                                    elif 'BOOLEAN' in sql_type.upper() or 'BOOL' in sql_type.upper():
                                        sql_type = "BOOLEAN"
                                    elif 'DATE' in sql_type.upper():
                                        sql_type = "DATE"
                                    elif 'TIMESTAMP' in sql_type.upper():
                                        sql_type = "TIMESTAMP WITH TIME ZONE"
                                    elif 'FLOAT' in sql_type.upper() or 'REAL' in sql_type.upper():
                                        sql_type = "REAL"
                                    elif 'NUMERIC' in sql_type.upper() or 'DECIMAL' in sql_type.upper():
                                        sql_type = "NUMERIC"
                                    elif 'VARCHAR' in sql_type.upper():
                                        # Garder VARCHAR avec sa longueur
                                        sql_type = sql_type
                                    
                                    model_columns[col_name] = sql_type
                            
                            # Trouver les colonnes manquantes
                            missing_columns = {col: sql_type for col, sql_type in model_columns.items() if col not in existing_columns}
                            
                            # Vérifier et mettre à jour les types de colonnes qui ont changé (ex: VARCHAR(255) -> TEXT)
                            columns_to_update = {}
                            for col_name, expected_type in model_columns.items():
                                if col_name in existing_columns:
                                    existing_type = existing_columns[col_name].upper()
                                    expected_type_upper = expected_type.upper()
                                    # Si la colonne existe mais a un type différent (ex: VARCHAR(255) vs TEXT)
                                    if expected_type_upper == "TEXT" and "VARCHAR" in existing_type:
                                        columns_to_update[col_name] = expected_type
                            
                            # Mettre à jour les types de colonnes
                            if columns_to_update:
                                logger.info(f"🔧 Mise à jour du type de {len(columns_to_update)} colonne(s) dans {schema_name}.{table_name}: {list(columns_to_update.keys())}")
                                for col_name, new_type in columns_to_update.items():
                                    try:
                                        alter_sql = f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN {col_name} TYPE {new_type} USING {col_name}::{new_type}"
                                        logger.info(f"   → {alter_sql}")
                                        session.execute(text(alter_sql))
                                        session.commit()
                                        logger.info(f"   ✅ Type de colonne {col_name} mis à jour à {new_type} dans {schema_name}.{table_name}")
                                    except Exception as e:
                                        logger.error(f"   ❌ Erreur lors de la mise à jour du type de {col_name} dans {schema_name}.{table_name}: {e}")
                                        session.rollback()
                                        migration_errors.append(f"Erreur lors de la mise à jour du type de {schema_name}.{table_name}.{col_name}: {e}")
                            
                            # Ajouter les colonnes manquantes
                            if missing_columns:
                                logger.info(f"🔧 Ajout de {len(missing_columns)} colonne(s) manquante(s) dans {schema_name}.{table_name}: {list(missing_columns.keys())}")
                                for col_name, sql_type in missing_columns.items():
                                    try:
                                        col_def = model_class.__table__.columns[col_name]
                                        
                                        # Construire la clause DEFAULT si nécessaire
                                        default_clause = ""
                                        if col_def.default is not None:
                                            if hasattr(col_def.default, 'arg'):
                                                default_value = col_def.default.arg
                                                if isinstance(default_value, bool):
                                                    default_clause = f" DEFAULT {str(default_value).upper()}"
                                                elif isinstance(default_value, (int, float)):
                                                    default_clause = f" DEFAULT {default_value}"
                                                elif isinstance(default_value, str):
                                                    default_clause = f" DEFAULT '{default_value}'"
                                        
                                        # Construire la clause NULL/NOT NULL
                                        nullable_clause = "" if col_def.nullable else " NOT NULL"
                                        
                                        # Construire et exécuter l'ALTER TABLE avec le schéma explicite
                                        alter_sql = f"ALTER TABLE {schema_name}.{table_name} ADD COLUMN {col_name} {sql_type}{nullable_clause}{default_clause}"
                                        logger.info(f"   → {alter_sql}")
                                        
                                        session.execute(text(alter_sql))
                                        session.commit()
                                        
                                        columns_added.append(f"{schema_name}.{table_name}.{col_name}")
                                        logger.info(f"   ✅ Colonne {col_name} ajoutée à {schema_name}.{table_name}")
                                        
                                    except Exception as e:
                                        logger.error(f"   ❌ Erreur lors de l'ajout de la colonne {col_name} à {schema_name}.{table_name}: {e}")
                                        session.rollback()
                                        migration_errors.append(f"Erreur lors de l'ajout de {schema_name}.{table_name}.{col_name}: {e}")
                            else:
                                logger.info(f"✅ Table {schema_name}.{table_name} à jour")
                        else:
                            logger.info(f"ℹ️ Table {schema_name}.{table_name} n'existe pas encore - sera créée")
                            
                    except Exception as e:
                        logger.error(f"Erreur lors de la vérification des colonnes de {schema_name}.{table_name}: {e}")
                        migration_errors.append(f"Erreur lors de la vérification de {schema_name}.{table_name}: {e}")
                
                # Réinitialiser le search_path
                session.execute(text("SET search_path TO public"))
                
                if columns_added:
                    logger.info(f"✅ Migration terminée pour {schema_name}: {len(columns_added)} colonne(s) ajoutée(s)")
                if migration_errors:
                    logger.warning(f"⚠️ {len(migration_errors)} erreur(s) lors de la migration de {schema_name}")
                
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des schémas par programme: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


# Dépendance FastAPI : ouvre/ferme une session par requête
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# (facultatif) Test de connexion
def test_db_connection() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
