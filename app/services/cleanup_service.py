"""
Service de nettoyage automatique pour les codes de récupération expirés
"""
import logging
from datetime import datetime, timezone
from sqlmodel import Session, select
from app_lia_web.core.database import get_session
from app_lia_web.app.services.password_recovery_service import PasswordRecoveryService

logger = logging.getLogger(__name__)


class CleanupService:
    """Service de nettoyage automatique"""
    
    @staticmethod
    def cleanup_expired_recovery_codes():
        """Nettoie les codes de récupération expirés"""
        try:
            session = next(get_session())
            recovery_service = PasswordRecoveryService()
            
            count = recovery_service.cleanup_expired_codes(session)
            
            if count > 0:
                logger.info(f"🧹 Nettoyage automatique : {count} codes de récupération expirés supprimés")
            else:
                logger.debug("🧹 Nettoyage automatique : aucun code expiré à supprimer")
            
            session.close()
            return count
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage automatique : {e}")
            return 0


def run_cleanup():
    """Fonction pour exécuter le nettoyage (utilisable par un cron job)"""
    return CleanupService.cleanup_expired_recovery_codes()


if __name__ == "__main__":
    # Exécution directe du script
    count = run_cleanup()
    print(f"Nettoyage terminé : {count} codes supprimés")
