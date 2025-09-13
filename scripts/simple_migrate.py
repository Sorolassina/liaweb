"""
Script de migration simple pour créer la table de récupération de mot de passe
"""
import os
import sys
import logging

# Ajouter le répertoire app au path
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
sys.path.insert(0, app_dir)

from sqlmodel import SQLModel, create_engine
from app_lia_web.core.config import settings
from app_lia_web.app.models.password_recovery import PasswordRecoveryCode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_table():
    """Crée la table en utilisant SQLModel"""
    try:
        # Créer l'engine
        engine = create_engine(settings.DATABASE_URL)
        
        # Créer la table
        SQLModel.metadata.create_all(engine)
        
        logger.info("✅ Table passwordrecoverycode créée avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création de la table : {e}")
        return False


if __name__ == "__main__":
    print("🚀 Migration simple de la table de récupération de mot de passe")
    print("=" * 60)
    
    if create_table():
        print("✅ Migration réussie")
        print("\n🎉 La table passwordrecoverycode est maintenant disponible !")
        print("\n📋 Prochaines étapes :")
        print("1. Testez le système : python scripts/test_password_recovery.py")
        print("2. Lancez l'application : python main.py")
        print("3. Testez sur : http://localhost:8000/mot-de-passe-oublie")
    else:
        print("❌ Échec de la migration")
        exit(1)
