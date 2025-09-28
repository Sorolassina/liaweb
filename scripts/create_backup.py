# app/scripts/create_backup.py
"""
Script pour créer une sauvegarde complète de l'application
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app_lia_web.core.database import engine
from app_lia_web.app.models.base import User
from app_lia_web.app.services.archive import ArchiveService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_backup():
    """Crée une sauvegarde complète"""
    
    with Session(engine) as session:
        # Récupérer l'admin pour created_by
        admin_user = session.exec(select(User).where(User.role == "administrateur")).first()
        if not admin_user:
            logger.error("❌ Aucun utilisateur administrateur trouvé")
            return
        
        logger.info("🚀 Création d'une sauvegarde complète...")
        
        archive_service = ArchiveService(session)
        archive = archive_service.create_full_backup(
            admin_user, 
            "Sauvegarde automatique via script"
        )
        
        if archive:
            logger.info(f"✅ Sauvegarde créée avec succès!")
            logger.info(f"   📁 Nom: {archive.name}")
            logger.info(f"   📊 Statut: {archive.status}")
            logger.info(f"   📏 Taille: {archive.file_size / 1024 / 1024:.2f} MB" if archive.file_size else "   📏 Taille: Non disponible")
            logger.info(f"   📅 Créée le: {archive.created_at}")
            logger.info(f"   ⏰ Expire le: {archive.expires_at}")
        else:
            logger.error("❌ Échec de la création de la sauvegarde")

if __name__ == "__main__":
    create_backup()
