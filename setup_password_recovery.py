"""
Script de lancement et test du système de récupération de mot de passe
"""
import os
import sys
import subprocess
import logging

# Ajouter le répertoire app au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Exécute la migration de la base de données"""
    print("🔄 Exécution de la migration...")
    try:
        result = subprocess.run([
            sys.executable, 
            "scripts/migrate_password_recovery.py"
        ], cwd="app", capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Migration réussie")
            print(result.stdout)
            return True
        else:
            print("❌ Échec de la migration")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Erreur lors de la migration : {e}")
        return False


def run_tests():
    """Exécute les tests du système"""
    print("\n🧪 Exécution des tests...")
    try:
        result = subprocess.run([
            sys.executable, 
            "scripts/test_password_recovery.py"
        ], cwd="app", capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("Erreurs :", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Erreur lors des tests : {e}")
        return False


def check_requirements():
    """Vérifie que les dépendances sont installées"""
    print("🔍 Vérification des dépendances...")
    
    required_modules = [
        'fastapi',
        'sqlmodel', 
        'pydantic',
        'email_validator',
        'passlib',
        'python_jose'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} manquant")
            missing_modules.append(module)
    
    if missing_modules:
        print(f"\n⚠️ Modules manquants : {', '.join(missing_modules)}")
        print("Installez-les avec : pip install -r requirements.txt")
        return False
    
    return True


def main():
    """Fonction principale"""
    print("🚀 Configuration du système de récupération de mot de passe")
    print("=" * 60)
    
    # Vérifier les dépendances
    if not check_requirements():
        print("\n❌ Dépendances manquantes. Arrêt.")
        return False
    
    # Exécuter la migration
    if not run_migration():
        print("\n❌ Migration échouée. Arrêt.")
        return False
    
    # Exécuter les tests
    if not run_tests():
        print("\n⚠️ Tests échoués, mais le système peut fonctionner.")
    
    print("\n🎉 Configuration terminée !")
    print("\n📋 Prochaines étapes :")
    print("1. Vérifiez la configuration SMTP dans app/core/config.py")
    print("2. Lancez l'application : python main.py")
    print("3. Testez le système sur : http://localhost:8000/mot-de-passe-oublie")
    print("4. Consultez la documentation : app/docs/PASSWORD_RECOVERY_SYSTEM.md")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
