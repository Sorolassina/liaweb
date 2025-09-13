"""
Vérification rapide du système de récupération de mot de passe
"""
import sys
import os

# Ajouter le répertoire app au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def check_files():
    """Vérifie que tous les fichiers nécessaires existent"""
    print("🔍 Vérification des fichiers...")
    
    required_files = [
        "app/models/password_recovery.py",
        "app/services/password_recovery_service.py", 
        "app/schemas/password_recovery_schemas.py",
        "app/routers/password_recovery.py",
        "app/templates/password_recovery/forgot_password.html",
        "app/templates/password_recovery/verify_code.html",
        "app/templates/password_recovery/reset_password.html",
        "app/scripts/migrate_password_recovery.py",
        "app/scripts/test_password_recovery.py",
        "app/docs/PASSWORD_RECOVERY_SYSTEM.md"
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    return len(missing_files) == 0


def check_imports():
    """Vérifie que les imports fonctionnent"""
    print("\n🔍 Vérification des imports...")
    
    try:
        from app_lia_web.app.models.password_recovery import PasswordRecoveryCode
        print("✅ PasswordRecoveryCode")
    except Exception as e:
        print(f"❌ PasswordRecoveryCode : {e}")
        return False
    
    try:
        from app_lia_web.app.services.password_recovery_service import PasswordRecoveryService
        print("✅ PasswordRecoveryService")
    except Exception as e:
        print(f"❌ PasswordRecoveryService : {e}")
        return False
    
    try:
        from app_lia_web.app.schemas.password_recovery_schemas import PasswordRecoveryRequest
        print("✅ PasswordRecoveryRequest")
    except Exception as e:
        print(f"❌ PasswordRecoveryRequest : {e}")
        return False
    
    try:
        from app_lia_web.app.routers.password_recovery import router
        print("✅ password_recovery router")
    except Exception as e:
        print(f"❌ password_recovery router : {e}")
        return False
    
    return True


def check_config():
    """Vérifie la configuration"""
    print("\n🔍 Vérification de la configuration...")
    
    try:
        from app_lia_web.core.config import settings
        
        # Vérifier les paramètres SMTP
        smtp_config = [
            ("SMTP_HOST", settings.SMTP_HOST),
            ("SMTP_PORT", settings.SMTP_PORT),
            ("SMTP_USER", settings.SMTP_USER),
            ("SMTP_PASSWORD", settings.SMTP_PASSWORD),
            ("MAIL_FROM", settings.MAIL_FROM),
            ("MAIL_FROM_NAME", settings.MAIL_FROM_NAME)
        ]
        
        for name, value in smtp_config:
            if value:
                print(f"✅ {name} : {'*' * len(str(value))}")
            else:
                print(f"⚠️ {name} : Non configuré")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de configuration : {e}")
        return False


def main():
    """Fonction principale"""
    print("🔧 Vérification du système de récupération de mot de passe")
    print("=" * 60)
    
    # Vérifier les fichiers
    files_ok = check_files()
    
    # Vérifier les imports
    imports_ok = check_imports()
    
    # Vérifier la configuration
    config_ok = check_config()
    
    print("\n📊 Résumé :")
    print(f"Fichiers : {'✅ OK' if files_ok else '❌ Manquants'}")
    print(f"Imports : {'✅ OK' if imports_ok else '❌ Erreurs'}")
    print(f"Configuration : {'✅ OK' if config_ok else '❌ Problèmes'}")
    
    if files_ok and imports_ok and config_ok:
        print("\n🎉 Système prêt à être utilisé !")
        print("\n📋 Prochaines étapes :")
        print("1. Exécutez la migration : python scripts/migrate_password_recovery.py")
        print("2. Testez le système : python scripts/test_password_recovery.py")
        print("3. Lancez l'application et testez sur : /mot-de-passe-oublie")
        return True
    else:
        print("\n⚠️ Des problèmes ont été détectés. Vérifiez les erreurs ci-dessus.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
