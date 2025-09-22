#!/usr/bin/env python3
"""
Script de démarrage pour créer les schémas par programme
"""
import subprocess
import sys
from pathlib import Path
from core.config import settings

def run_sql_script():
    """Exécute le script SQL pour créer les schémas"""
    script_path = Path(__file__).parent / "scripts" / "create_program_schemas_with_existing_models.sql"
    
    if not script_path.exists():
        print(f"❌ Script SQL non trouvé: {script_path}")
        return False
    
    print(f"📄 Exécution du script SQL: {script_path}")
    
    # Configuration par défaut (à adapter selon votre environnement)
    db_host = settings.PGHOST
    db_port = settings.PGPORT
    db_name = settings.PGDATABASE
    db_user = settings.PGUSER
    db_password = settings.PGPASSWORD
    
    # Commande psql
    cmd = [
        "psql",
        "-h", db_host,
        "-p", db_port,
        "-U", db_user,
        "-d", db_name,
        "-f", str(script_path)
    ]
    
    # Définir le mot de passe
    env["PGPASSWORD"] = db_password
    
    try:
        print(f"🔄 Exécution de la commande: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        
        print("✅ Script SQL exécuté avec succès!")
        
        if result.stdout:
            print("\n📋 Sortie du script:")
            print(result.stdout)
        
        if result.stderr:
            print("\n⚠️ Avertissements:")
            print(result.stderr)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'exécution du script SQL:")
        print(f"Code de retour: {e.returncode}")
        
        if e.stdout:
            print(f"\n📋 Sortie:")
            print(e.stdout)
        
        if e.stderr:
            print(f"\n❌ Erreur:")
            print(e.stderr)
        
        return False
    
    except FileNotFoundError:
        print("❌ psql non trouvé dans le PATH")
        print("💡 Assurez-vous que PostgreSQL est installé et que psql est accessible")
        return False

def main():
    """Fonction principale"""
    print("🚀 Création des schémas par programme")
    print("=" * 40)
    
    # Vérifier que psql est disponible
    psql_path = subprocess.which("psql")
    if not psql_path:
        print("❌ psql non trouvé dans le PATH")
        print("💡 Installez PostgreSQL ou ajoutez psql au PATH")
        sys.exit(1)
    
    print(f"✅ psql trouvé: {psql_path}")
    
    # Exécuter le script SQL
    success = run_sql_script()
    
    if success:
        print("\n🎉 Schémas créés avec succès!")
        print("\n📝 Prochaines étapes:")
        print("1. Démarrer l'application: python -m app_lia_web.app.main")
        print("2. Accéder à l'interface d'administration: http://localhost:8000/admin/schemas")
        print("3. Migrer les données existantes par programme")
        print("4. Tester les fonctionnalités avec les nouveaux schémas")
        sys.exit(0)
    else:
        print("\n❌ Échec de la création des schémas")
        print("\n🔧 Actions recommandées:")
        print("1. Vérifier la connexion à la base de données")
        print("2. Vérifier les permissions de l'utilisateur de base de données")
        print("3. Vérifier que la base de données existe")
        print("4. Exécuter le script manuellement avec psql")
        sys.exit(1)

if __name__ == "__main__":
    main()
