# app/services/database_migration.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging
from sqlmodel import Session, text, inspect
from sqlalchemy import create_engine, MetaData, Table, Column, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.exc import ProgrammingError

from ..core.config import settings
from ..models.enums import TypeDocument, UserRole, StatutPresence, TypeUtilisateur, StatutDossier, DecisionJury

logger = logging.getLogger(__name__)

class DatabaseMigrationService:
    """Service de migration automatique de la base de données"""
    
    def __init__(self, session: Session):
        self.session = session
        self.engine = session.bind
        
    def migrate_database(self) -> Dict[str, Any]:
        """Effectue toutes les migrations nécessaires"""
        migration_results = {
            "tables_created": [],
            "columns_added": [],
            "errors": []
        }
        
        try:
            
            # 1. Migrer les tables
            self._migrate_tables(migration_results)
            
            # 3. Migrer les colonnes
            self._migrate_columns(migration_results)
            
            logger.info("✅ Migration de la base de données terminée avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la migration: {e}")
            migration_results["errors"].append(str(e))
            
        return migration_results
    
   
    def _migrate_tables(self, results: Dict[str, Any]):
        """Migre les tables (création si nécessaire)"""
        logger.info("🔄 Vérification des tables...")
        
        # Cette partie peut être étendue pour créer des tables spécifiques
        # Pour l'instant, on se concentre sur les enums et colonnes
        
        # Vérifier les tables critiques
        critical_tables = ['user', 'programme', 'candidat', 'document', 'preinscription']
        
        for table_name in critical_tables:
            try:
                inspector = inspect(self.engine)
                if not inspector.has_table(table_name):
                    logger.warning(f"⚠️ Table {table_name} manquante - nécessite une migration manuelle")
                    results["errors"].append(f"Table {table_name} manquante")
            except Exception as e:
                logger.error(f"Erreur lors de la vérification de la table {table_name}: {e}")
    
    def _migrate_columns(self, results: Dict[str, Any]):
        """Migre les colonnes (ajout si nécessaire) en comparant les modèles SQLModel avec les tables existantes"""
        logger.info("🔄 Vérification des colonnes...")
        
        inspector = inspect(self.engine)
        
        # Importer les modèles publics
        from ..models.base import (
            User, Programme, Partenaire, Groupe, PasswordRecoveryCode,
            ProgrammeUtilisateur, Promotion, ActivityLog, Conversation, Message
        )
        
        # Mapping des tables publiques à leurs modèles SQLModel
        public_models = {
            'user': User,
            'programme': Programme,
            'partenaire': Partenaire,
            'groupe': Groupe,
            'password_recovery_code': PasswordRecoveryCode,
            'programme_utilisateur': ProgrammeUtilisateur,
            'promotion': Promotion,
            'activity_log': ActivityLog,
            'conversation': Conversation,
            'message': Message,
        }
        
        for table_name, model_class in public_models.items():
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
                            else:
                                # Garder le type original si c'est déjà une string SQL (ex: VARCHAR(255))
                                sql_type = sql_type
                            
                            model_columns[col_name] = sql_type
                    
                    # Trouver les colonnes manquantes
                    missing_columns = {col: sql_type for col, sql_type in model_columns.items() if col not in existing_columns}
                    
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
                                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}{nullable_clause}{default_clause}"
                                logger.info(f"   → {alter_sql}")
                                
                                self.session.execute(text(alter_sql))
                                self.session.commit()
                                
                                results["columns_added"].append(f"{table_name}.{col_name}")
                                logger.info(f"   ✅ Colonne {col_name} ajoutée à {table_name}")
                                
                            except Exception as e:
                                logger.error(f"   ❌ Erreur lors de l'ajout de la colonne {col_name} à {table_name}: {e}")
                                self.session.rollback()
                                results["errors"].append(f"Erreur lors de l'ajout de {table_name}.{col_name}: {e}")
                    else:
                        logger.info(f"✅ Table {table_name} à jour")
                else:
                    logger.warning(f"⚠️ Table {table_name} n'existe pas - sera créée par create_db_and_tables()")
                    
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des colonnes de {table_name}: {e}")
                results["errors"].append(f"Erreur lors de la vérification de {table_name}: {e}")
    
    def get_database_status(self) -> Dict[str, Any]:
        """Retourne le statut de la base de données"""
        status = {
            "tables": [],
            "connection": False
        }
        
        try:            
            # Vérifier les tables
            tables_query = text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            
            tables = self.session.exec(tables_query).all()
            status["tables"] = [table[0] for table in tables]
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du statut: {e}")
            status["error"] = str(e)
        
        return status
