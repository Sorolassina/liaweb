# app/scripts/run_cleanup.py
"""
Script pour exécuter le nettoyage automatique
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from core.database import engine
from models.base import User
from services.ACD.archive import ArchiveService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_cleanup():
    """Exécute le nettoyage automatique"""
    
    with Session(engine) as session:
        # Récupérer l'admin pour executed_by
        admin_user = session.exec(select(User).where(User.role == "administrateur")).first()
        if not admin_user:
            logger.error("❌ Aucun utilisateur administrateur trouvé")
            return
        
        logger.info("🧹 Exécution du nettoyage automatique...")
        
        archive_service = ArchiveService(session)
        cleanup_stats = archive_service.cleanup_old_data(admin_user)
        
        if cleanup_stats:
            logger.info("✅ Nettoyage terminé avec succès!")
            total_deleted = 0
            for table, count in cleanup_stats.items():
                logger.info(f"   📊 {table}: {count} enregistrements supprimés")
                total_deleted += count
            logger.info(f"   🎯 Total: {total_deleted} enregistrements supprimés")
        else:
            logger.warning("⚠️ Aucune donnée nettoyée ou erreur lors du nettoyage")

if __name__ == "__main__":
    run_cleanup()
