# app/services/database_migration.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging
from sqlmodel import Session, text, inspect
from sqlalchemy import create_engine, MetaData, Table, Column, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.exc import ProgrammingError

from app_lia_web.core.config import settings
from app_lia_web.app.models.enums import TypeDocument, UserRole, StatutPresence, TypeUtilisateur, StatutDossier, DecisionJury

logger = logging.getLogger(__name__)

class DatabaseMigrationService:
    """Service de migration automatique de la base de données"""
    
    def __init__(self, session: Session):
        self.session = session
        self.engine = session.bind
        
    def migrate_database(self) -> Dict[str, Any]:
        """Effectue toutes les migrations nécessaires"""
        migration_results = {
            "enums_updated": [],
            "tables_created": [],
            "columns_added": [],
            "errors": []
        }
        
        try:
            # 1. Migrer les enums
            self._migrate_enums(migration_results)
            
            # 2. Migrer les tables
            self._migrate_tables(migration_results)
            
            # 3. Migrer les colonnes
            self._migrate_columns(migration_results)
            
            logger.info("✅ Migration de la base de données terminée avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la migration: {e}")
            migration_results["errors"].append(str(e))
            
        return migration_results
    
    def _migrate_enums(self, results: Dict[str, Any]):
        """Migre les enums PostgreSQL"""
        logger.info("🔄 Vérification des enums...")
        
        # Mapping des enums Python vers PostgreSQL
        enum_mappings = {
            'typedocument': {
                'values': [e.value for e in TypeDocument],
                'description': 'Types de documents'
            },
            'userrole': {
                'values': [e.value for e in UserRole],
                'description': 'Rôles utilisateurs'
            },
            'statutpresence': {
                'values': [e.value for e in StatutPresence],
                'description': 'Statuts de présence'
            },
            'typeutilisateur': {
                'values': [e.value for e in TypeUtilisateur],
                'description': 'Types d\'utilisateurs'
            },
            'statutdossier': {
                'values': [e.value for e in StatutDossier],
                'description': 'Statuts de dossier'
            },
            'decisionjury': {
                'values': [e.value for e in DecisionJury],
                'description': 'Décisions de jury'
            }
        }
        
        for enum_name, config in enum_mappings.items():
            try:
                self._update_enum(enum_name, config['values'], results)
            except Exception as e:
                logger.error(f"Erreur lors de la migration de l'enum {enum_name}: {e}")
                results["errors"].append(f"Enum {enum_name}: {str(e)}")
    
    def _update_enum(self, enum_name: str, expected_values: List[str], results: Dict[str, Any]):
        """Met à jour un enum spécifique"""
        try:
            # Vérifier si l'enum existe
            enum_exists_query = text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = :enum_name
                )
            """)
            
            enum_exists = self.session.exec(enum_exists_query, {"enum_name": enum_name}).first()
            
            if not enum_exists:
                logger.info(f"📝 Création de l'enum {enum_name}")
                # Créer l'enum
                create_enum_query = text(f"""
                    CREATE TYPE {enum_name} AS ENUM ({', '.join([f"'{v}'" for v in expected_values])})
                """)
                self.session.exec(create_enum_query)
                results["enums_updated"].append(f"Créé: {enum_name}")
            else:
                # Vérifier les valeurs existantes
                existing_values_query = text("""
                    SELECT enumlabel FROM pg_enum 
                    WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = :enum_name)
                    ORDER BY enumlabel
                """)
                
                existing_values = [row[0] for row in self.session.exec(existing_values_query, {"enum_name": enum_name}).all()]
                
                # Ajouter les valeurs manquantes
                missing_values = set(expected_values) - set(existing_values)
                
                if missing_values:
                    logger.info(f"📝 Ajout de valeurs à l'enum {enum_name}: {missing_values}")
                    
                    for value in missing_values:
                        add_value_query = text(f"ALTER TYPE {enum_name} ADD VALUE :value")
                        self.session.exec(add_value_query, {"value": value})
                    
                    results["enums_updated"].append(f"Mis à jour: {enum_name} (+{len(missing_values)} valeurs)")
                else:
                    logger.info(f"✅ Enum {enum_name} à jour")
            
            self.session.commit()
            
        except Exception as e:
            self.session.rollback()
            raise e
    
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
        """Migre les colonnes (ajout si nécessaire)"""
        logger.info("🔄 Vérification des colonnes...")
        
        # Mapping des colonnes critiques à vérifier
        critical_columns = {
            'user': ['role', 'type_utilisateur', 'actif'],
            'programme': ['statut'],
            'document': ['type_document'],
            'preinscription': ['statut'],
            'jury': ['decision']
        }
        
        inspector = inspect(self.engine)
        
        for table_name, expected_columns in critical_columns.items():
            try:
                if inspector.has_table(table_name):
                    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
                    missing_columns = set(expected_columns) - set(existing_columns)
                    
                    if missing_columns:
                        logger.warning(f"⚠️ Colonnes manquantes dans {table_name}: {missing_columns}")
                        results["errors"].append(f"Colonnes manquantes dans {table_name}: {missing_columns}")
                    else:
                        logger.info(f"✅ Table {table_name} à jour")
                else:
                    logger.warning(f"⚠️ Table {table_name} n'existe pas")
                    results["errors"].append(f"Table {table_name} n'existe pas")
                    
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des colonnes de {table_name}: {e}")
    
    def get_database_status(self) -> Dict[str, Any]:
        """Retourne le statut de la base de données"""
        status = {
            "enums": {},
            "tables": [],
            "connection": False
        }
        
        try:
            # Test de connexion
            self.session.exec(text("SELECT 1"))
            status["connection"] = True
            
            # Vérifier les enums
            enums_query = text("""
                SELECT t.typname, e.enumlabel 
                FROM pg_type t 
                JOIN pg_enum e ON t.oid = e.enumtypid 
                WHERE t.typtype = 'e'
                ORDER BY t.typname, e.enumsortorder
            """)
            
            enum_data = self.session.exec(enums_query).all()
            
            for enum_name, enum_value in enum_data:
                if enum_name not in status["enums"]:
                    status["enums"][enum_name] = []
                status["enums"][enum_name].append(enum_value)
            
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
