# app/scripts/init_cleanup_rules.py
"""
Script pour initialiser les règles de nettoyage automatique
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app_lia_web.core.database import engine
from app_lia_web.app.models.archive import RegleNettoyage
from app_lia_web.app.models.base import User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_cleanup_rules():
    """Initialise les règles de nettoyage par défaut"""
    
    with Session(engine) as session:
        # Récupérer l'admin pour created_by
        admin_user = session.exec(select(User).where(User.role == "administrateur")).first()
        if not admin_user:
            logger.error("❌ Aucun utilisateur administrateur trouvé")
            return
        
        # Règles de nettoyage par défaut
        default_rules = [
            {
                "nom": "Logs d'activité anciens",
                "nom_table": "activitylog",
                "condition": "created_at < NOW() - INTERVAL '90 days'",
                "jours_retention": 90,
                "description": "Supprime les logs d'activité de plus de 90 jours"
            },
            {
                "nom": "Sessions expirées",
                "nom_table": "session",
                "condition": "expires_at < NOW()",
                "jours_retention": 7,
                "description": "Supprime les sessions expirées"
            },
            {
                "nom": "Documents temporaires",
                "nom_table": "document",
                "condition": "created_at < NOW() - INTERVAL '365 days' AND status = 'temporary'",
                "jours_retention": 365,
                "description": "Supprime les documents temporaires de plus d'un an"
            },
            {
                "nom": "Préinscriptions abandonnées",
                "nom_table": "preinscription",
                "condition": "created_at < NOW() - INTERVAL '180 days' AND statut = 'abandonnee'",
                "jours_retention": 180,
                "description": "Supprime les préinscriptions abandonnées de plus de 6 mois"
            },
            {
                "nom": "Archives expirées",
                "nom_table": "archive",
                "condition": "expire_le < NOW()",
                "jours_retention": 30,
                "description": "Supprime les archives expirées"
            }
        ]
        
        created_count = 0
        for rule_data in default_rules:
            # Vérifier si la règle existe déjà
            existing = session.exec(
                select(RegleNettoyage).where(RegleNettoyage.nom == rule_data["nom"])
            ).first()
            
            if not existing:
                rule = RegleNettoyage(
                    nom=rule_data["nom"],
                    nom_table=rule_data["nom_table"],
                    condition=rule_data["condition"],
                    jours_retention=rule_data["jours_retention"],
                    active=True,
                    cree_par=admin_user.id
                )
                session.add(rule)
                created_count += 1
                logger.info(f"✅ Règle créée: {rule_data['nom']}")
            else:
                logger.info(f"ℹ️ Règle existe déjà: {rule_data['nom']}")
        
        session.commit()
        logger.info(f"🎉 {created_count} nouvelles règles de nettoyage créées")

if __name__ == "__main__":
    logger.info("🚀 Initialisation des règles de nettoyage...")
    init_cleanup_rules()
    logger.info("✅ Initialisation terminée")
