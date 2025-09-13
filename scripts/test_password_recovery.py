"""
Script de test pour le système de récupération de mot de passe
"""
import os
import sys
import asyncio
import logging
from sqlmodel import Session, select

# Ajouter le répertoire app au path
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
sys.path.insert(0, app_dir)

from app_lia_web.core.database import get_session
from app_lia_web.app.services.password_recovery_service import PasswordRecoveryService
from app_lia_web.app.models.password_recovery import PasswordRecoveryCode
from app_lia_web.app.models.base import User

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_password_recovery():
    """Test complet du système de récupération de mot de passe"""
    
    print("🧪 Test du système de récupération de mot de passe")
    print("=" * 50)
    
    session = next(get_session())
    recovery_service = PasswordRecoveryService()
    
    try:
        # 1. Test de création d'un code de récupération
        print("\n1️⃣ Test de création d'un code de récupération")
        test_email = "test@example.com"
        
        # Créer un utilisateur de test s'il n'existe pas
        user = session.exec(select(User).where(User.email == test_email)).first()
        if not user:
            from app_lia_web.core.security import get_password_hash
            user = User(
                email=test_email,
                nom_complet="Utilisateur Test",
                mot_de_passe_hash=get_password_hash("motdepasse123"),
                role="conseiller",
                actif=True
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"✅ Utilisateur de test créé : {user.email}")
        else:
            print(f"✅ Utilisateur de test trouvé : {user.email}")
        
        # Demander une récupération
        success = recovery_service.request_password_recovery(session, test_email, "127.0.0.1")
        print(f"📧 Demande de récupération : {'✅ Succès' if success else '❌ Échec'}")
        
        # 2. Vérifier que le code a été créé
        print("\n2️⃣ Vérification de la création du code")
        recovery_code = session.exec(
            select(PasswordRecoveryCode).where(
                PasswordRecoveryCode.email == test_email
            ).order_by(PasswordRecoveryCode.created_at.desc())
        ).first()
        
        if recovery_code:
            print(f"✅ Code créé : {recovery_code.code}")
            print(f"📅 Expire le : {recovery_code.expires_at}")
            print(f"🔒 Utilisé : {recovery_code.used}")
            
            # 3. Test de vérification du code
            print("\n3️⃣ Test de vérification du code")
            is_valid = recovery_service.verify_recovery_code(session, test_email, recovery_code.code)
            print(f"🔍 Vérification du code : {'✅ Valide' if is_valid else '❌ Invalide'}")
            
            # 4. Test de réinitialisation du mot de passe
            print("\n4️⃣ Test de réinitialisation du mot de passe")
            new_password = "NouveauMotDePasse123"
            reset_success = recovery_service.reset_password(session, test_email, recovery_code.code, new_password)
            print(f"🔑 Réinitialisation : {'✅ Succès' if reset_success else '❌ Échec'}")
            
            # 5. Vérifier que le code est marqué comme utilisé
            print("\n5️⃣ Vérification du statut du code")
            session.refresh(recovery_code)
            print(f"🔒 Code utilisé : {'✅ Oui' if recovery_code.used else '❌ Non'}")
            print(f"📅 Date d'utilisation : {recovery_code.used_at}")
            
            # 6. Test avec un code invalide
            print("\n6️⃣ Test avec un code invalide")
            invalid_code = "999999"
            is_invalid = recovery_service.verify_recovery_code(session, test_email, invalid_code)
            print(f"🚫 Code invalide : {'✅ Correctement rejeté' if not is_invalid else '❌ Erreur'}")
            
        else:
            print("❌ Aucun code de récupération trouvé")
        
        # 7. Test de nettoyage
        print("\n7️⃣ Test de nettoyage des codes expirés")
        cleanup_count = recovery_service.cleanup_expired_codes(session)
        print(f"🧹 Codes nettoyés : {cleanup_count}")
        
        print("\n✅ Tests terminés avec succès !")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors des tests : {e}")
        print(f"❌ Erreur : {e}")
    
    finally:
        session.close()


async def test_email_sending():
    """Test de l'envoi d'email (nécessite une configuration SMTP valide)"""
    print("\n📧 Test de l'envoi d'email")
    print("=" * 30)
    
    session = next(get_session())
    recovery_service = PasswordRecoveryService()
    
    try:
        # Test avec un email réel (remplacez par votre email)
        test_email = "sorolassina58@gmail.com"  # Email de test
        
        success = recovery_service.request_password_recovery(session, test_email, "127.0.0.1")
        print(f"📧 Envoi d'email à {test_email} : {'✅ Succès' if success else '❌ Échec'}")
        
        if success:
            print("📬 Vérifiez votre boîte email pour le code de récupération")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du test d'email : {e}")
        print(f"❌ Erreur : {e}")
    
    finally:
        session.close()


if __name__ == "__main__":
    print("🚀 Démarrage des tests de récupération de mot de passe")
    
    # Exécuter les tests
    asyncio.run(test_password_recovery())
    
    # Demander si on veut tester l'envoi d'email
    response = input("\n📧 Voulez-vous tester l'envoi d'email ? (y/N): ")
    if response.lower() in ['y', 'yes', 'oui']:
        asyncio.run(test_email_sending())
    
    print("\n🎉 Tests terminés !")
