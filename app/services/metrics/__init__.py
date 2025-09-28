"""
Module de métriques pour l'analyse des données par schéma
"""
from typing import List
from sqlmodel import Session, text
from app_lia_web.core.database import get_session
import logging

logger = logging.getLogger(__name__)

def get_session_for_metrics() -> Session:
    """
    Retourne une session de base de données pour les métriques.
    """
    return next(get_session())

class SchemaDiscovery :
    """Classe pour découvrir et analyser les schémas de la base de données."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_all_program_schemas(self) -> List[str]: #🎉 Requête testé fonctionnellement
        """
        Récupère la liste de tous les schémas de programmes existants.
        """
        try:
            result = self.session.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
                ORDER BY schema_name
            """))
            schemas = [row[0] for row in result.fetchall()]
            return schemas
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des schémas: {e}")
            return []
    
    def schema_has_table(self, schema_name: str, table_name: str) -> bool:
        """
        Vérifie si un schéma contient une table spécifique.
        """
        try:
            result = self.session.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = :schema AND table_name = :table
                )
            """), {"schema": schema_name, "table": table_name})
            return result.fetchone()[0]
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la table {table_name} dans {schema_name}: {e}")
            return False
    
    def get_schema_tables(self, schema_name: str) -> List[str]: #🎉Requête testé fonctionnellement
        """
        Récupère la liste des tables d'un schéma.
        """
        try:
            result = self.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = :schema
                ORDER BY table_name
            """), {"schema": schema_name})
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tables pour {schema_name}: {e}")
            return []

# Instance globale pour les schémas (sera initialisée avec une session active)
program_schemas = None


def get_program_schemas() -> SchemaDiscovery:
    """
    Retourne l'instance globale de SchemaDiscovery.
    Crée une nouvelle session si nécessaire.
    """
    global program_schemas
    if program_schemas is None:
        # Créer une session temporaire pour l'initialisation
        session = next(get_session())
        program_schemas = SchemaDiscovery(session)
    return program_schemas

def init_program_schemas(session: Session):
    """
    Initialise l'instance globale avec une session spécifique.
    """
    global program_schemas
    program_schemas = SchemaDiscovery(session)