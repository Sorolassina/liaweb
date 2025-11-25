#!/usr/bin/env python3
"""
Script pour ajouter les colonnes statut_programme et raison_abandon à suivi_mensuel
et situation_entree à candidat dans tous les schémas de programme
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer les modules de l'application
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import get_session
from app.core.program_schema_integration import SchemaRoutingService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_all_program_schemas(session):
    """Récupère la liste de tous les schémas de programmes"""
    try:
        result = session.execute(text("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
            ORDER BY schema_name
        """))
        schemas = [row[0] for row in result]
        return schemas
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des schémas: {e}")
        return []

def table_exists(session, schema_name, table_name):
    """Vérifie si une table existe dans un schéma"""
    try:
        result = session.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = :schema_name 
                AND table_name = :table_name
            )
        """), {"schema_name": schema_name, "table_name": table_name})
        return result.fetchone()[0]
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de la table {table_name} dans {schema_name}: {e}")
        return False

def column_exists(session, schema_name, table_name, column_name):
    """Vérifie si une colonne existe dans une table"""
    try:
        result = session.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                AND table_name = :table_name
                AND column_name = :column_name
            )
        """), {"schema_name": schema_name, "table_name": table_name, "column_name": column_name})
        return result.fetchone()[0]
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de la colonne {column_name} dans {schema_name}.{table_name}: {e}")
        return False

def add_columns_to_schema(session, schema_name):
    """Ajoute les colonnes nécessaires à un schéma"""
    changes_made = []
    
    try:
        # 1. Ajouter situation_entree à candidat
        if table_exists(session, schema_name, "candidat"):
            if not column_exists(session, schema_name, "candidat", "situation_entree"):
                try:
                    session.execute(text(f"""
                        ALTER TABLE {schema_name}.candidat 
                        ADD COLUMN situation_entree VARCHAR(200)
                    """))
                    session.commit()
                    changes_made.append(f"{schema_name}.candidat.situation_entree")
                    logger.info(f"✅ Colonne situation_entree ajoutée à {schema_name}.candidat")
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'ajout de situation_entree à {schema_name}.candidat: {e}")
                    session.rollback()
            else:
                logger.info(f"ℹ️ Colonne situation_entree existe déjà dans {schema_name}.candidat")
        
        # 2. Ajouter statut_programme et raison_abandon à suivi_mensuel
        if table_exists(session, schema_name, "suivi_mensuel"):
            # statut_programme
            if not column_exists(session, schema_name, "suivi_mensuel", "statut_programme"):
                try:
                    session.execute(text(f"""
                        ALTER TABLE {schema_name}.suivi_mensuel 
                        ADD COLUMN statut_programme VARCHAR(50)
                    """))
                    session.commit()
                    changes_made.append(f"{schema_name}.suivi_mensuel.statut_programme")
                    logger.info(f"✅ Colonne statut_programme ajoutée à {schema_name}.suivi_mensuel")
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'ajout de statut_programme à {schema_name}.suivi_mensuel: {e}")
                    session.rollback()
            else:
                logger.info(f"ℹ️ Colonne statut_programme existe déjà dans {schema_name}.suivi_mensuel")
            
            # raison_abandon
            if not column_exists(session, schema_name, "suivi_mensuel", "raison_abandon"):
                try:
                    session.execute(text(f"""
                        ALTER TABLE {schema_name}.suivi_mensuel 
                        ADD COLUMN raison_abandon TEXT
                    """))
                    session.commit()
                    changes_made.append(f"{schema_name}.suivi_mensuel.raison_abandon")
                    logger.info(f"✅ Colonne raison_abandon ajoutée à {schema_name}.suivi_mensuel")
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'ajout de raison_abandon à {schema_name}.suivi_mensuel: {e}")
                    session.rollback()
            else:
                logger.info(f"ℹ️ Colonne raison_abandon existe déjà dans {schema_name}.suivi_mensuel")
            
            # Créer un index sur statut_programme
            try:
                session.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_statut_programme 
                    ON {schema_name}.suivi_mensuel(statut_programme)
                """))
                session.commit()
                logger.info(f"✅ Index créé sur {schema_name}.suivi_mensuel.statut_programme")
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de la création de l'index sur {schema_name}.suivi_mensuel.statut_programme: {e}")
                session.rollback()
        
    except Exception as e:
        logger.error(f"❌ Erreur générale pour le schéma {schema_name}: {e}")
        session.rollback()
    
    return changes_made

def main():
    """Fonction principale"""
    logger.info("🚀 Début de la migration : ajout des colonnes statut_programme et raison_abandon")
    logger.info("=" * 80)
    
    session = next(get_session())
    schema_routing_service = SchemaRoutingService(session)
    
    try:
        # Récupérer tous les schémas de programmes
        all_schemas = get_all_program_schemas(session)
        logger.info(f"📋 {len(all_schemas)} schéma(s) de programme trouvé(s): {', '.join(all_schemas)}")
        logger.info("")
        
        all_changes = []
        
        # Traiter chaque schéma
        for schema_name in all_schemas:
            logger.info(f"📁 Traitement du schéma: {schema_name}")
            logger.info("-" * 80)
            
            # Configurer le search_path pour ce schéma
            session.execute(text(f"SET search_path TO {schema_name}, public"))
            session.commit()
            
            changes = add_columns_to_schema(session, schema_name)
            all_changes.extend(changes)
            
            logger.info("")
        
        # Réinitialiser le search_path
        session.execute(text("SET search_path TO public"))
        session.commit()
        
        logger.info("=" * 80)
        if all_changes:
            logger.info(f"✅ Migration terminée : {len(all_changes)} colonne(s) ajoutée(s)")
            for change in all_changes:
                logger.info(f"   → {change}")
        else:
            logger.info("ℹ️ Aucune modification nécessaire - toutes les colonnes existent déjà")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration: {e}", exc_info=True)
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

