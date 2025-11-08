"""
Script Python pour lister tous les schémas de la base de données
Utilisation: python -m app.scripts.list_schemas
OU depuis le répertoire app/: python scripts/list_schemas.py
"""
import sys
import os
from pathlib import Path

# Déterminer le répertoire de l'application
script_path = Path(__file__).resolve()
app_dir = script_path.parent.parent  # scripts -> app
project_root = app_dir.parent  # app -> app_lia_web

# Sauvegarder le répertoire de travail original
original_cwd = os.getcwd()

# IMPORTANT: Ajouter le répertoire app au PYTHONPATH AVANT les imports
# Cela permet à Python de trouver les modules core.* même depuis le répertoire racine
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

# Changer le répertoire de travail vers app pour les imports relatifs
# Cela aide aussi pour les imports relatifs dans certains cas
os.chdir(app_dir)

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker


# Importer la configuration de la base de données et SchemaRoutingService
USE_APP_SESSION = False
SchemaRoutingService = None
settings = None
get_session = None

# Essayer d'abord les imports absolus (depuis app/)
# Ces imports fonctionnent maintenant car app_dir est dans sys.path
try:
    from core.config import settings
    from core.database import get_session
    from core.program_schema_integration import SchemaRoutingService
    USE_APP_SESSION = True
except ImportError as e1:
    # Essayer les imports relatifs (si exécuté comme module: python -m app.scripts.list_schemas)
    try:
        from app.core.config import settings
        from app.core.database import get_session
        from app.core.program_schema_integration import SchemaRoutingService
        USE_APP_SESSION = True
    except ImportError as e2:
        # Si on ne peut pas importer depuis l'app, utiliser une connexion directe
        USE_APP_SESSION = False
        SchemaRoutingService = None
        print("⚠️  Impossible d'importer depuis l'application, utilisation d'une connexion directe")
        print(f"   Erreur import absolu: {e1}")
        print(f"   Erreur import relatif: {e2}")
        print("💡 Pour utiliser la configuration de l'app, exécutez depuis le répertoire app/")
        print()

def get_direct_session():
    """Crée une session directe vers la base de données"""
    # Configuration par défaut (modifier selon vos besoins)
    db_url = os.getenv(
        'DATABASE_URL',
        'postgresql://liauser:liapass123@localhost:5432/lia_coaching'
    )
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def list_schemas():
    """Liste tous les schémas de la base de données"""
    if USE_APP_SESSION:
        session = next(get_session())
        schema_routing_service = SchemaRoutingService(session)
    else:
        session = get_direct_session()
        schema_routing_service = None
    
    try:
        print("🔍 Liste des schémas de la base de données")
        print("=" * 60)
        print()
        
        # Pour les requêtes information_schema, on peut utiliser directement la session
        # car information_schema est un schéma système PostgreSQL
        
        # 1. Lister tous les schémas
        print("📋 SCHÉMAS DISPONIBLES:")
        print("-" * 60)
        result = session.execute(text("""
            SELECT 
                schema_name AS schema_name,
                schema_owner AS owner
            FROM information_schema.schemata
            WHERE schema_name NOT LIKE 'pg_%' 
              AND schema_name != 'information_schema'
            ORDER BY 
                CASE 
                    WHEN schema_name = 'public' THEN 1
                    ELSE 2
                END,
                schema_name
        """))
        
        schemas = result.fetchall()
        print(f"{'Schéma':<30} {'Propriétaire':<20}")
        print("-" * 60)
        for schema_name, owner in schemas:
            schema_type = "Public" if schema_name == "public" else "Programme"
            print(f"{schema_name:<30} {owner:<20} ({schema_type})")
        
        print()
        print(f"Total: {len(schemas)} schéma(s)")
        print()
        
        # 2. Compter les schémas par type
        print("📊 RÉSUMÉ PAR TYPE:")
        print("-" * 60)
        result = session.execute(text("""
            SELECT 
                CASE 
                    WHEN schema_name = 'public' THEN 'Public'
                    ELSE 'Programme'
                END AS schema_type,
                COUNT(*) AS count,
                STRING_AGG(schema_name, ', ' ORDER BY schema_name) AS schemas
            FROM information_schema.schemata
            WHERE schema_name NOT LIKE 'pg_%' 
              AND schema_name != 'information_schema'
            GROUP BY 
                CASE 
                    WHEN schema_name = 'public' THEN 'Public'
                    ELSE 'Programme'
                END
        """))
        
        for schema_type, count, schemas_list in result.fetchall():
            print(f"{schema_type}: {count} schéma(s)")
            print(f"  → {schemas_list}")
        print()
        
        # 3. Lister les tables dans chaque schéma
        print("🗂️  TABLES PAR SCHÉMA:")
        print("-" * 60)
        result = session.execute(text("""
            SELECT 
                table_schema AS schema_name,
                COUNT(*) AS table_count,
                STRING_AGG(table_name, ', ' ORDER BY table_name) AS tables
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_schema NOT LIKE 'pg_%'
            GROUP BY table_schema
            ORDER BY table_schema
        """))
        
        for schema_name, table_count, tables_list in result.fetchall():
            print(f"\n📁 Schéma: {schema_name}")
            print(f"   Tables: {table_count}")
            print(f"   Liste: {tables_list}")
        
        print()
        print("=" * 60)
        
        # 4. Vérifier les tables essentielles dans chaque schéma de programme
        # Ici, on utilise SchemaRoutingService pour basculer dans chaque schéma
        print("\n🔍 VÉRIFICATION DES TABLES ESSENTIELLES:")
        print("-" * 60)
        
        program_schemas = [s[0] for s in schemas if s[0] != 'public']
        required_tables = ['candidat', 'entreprise', 'preinscription']
        
        for schema_name in program_schemas:
            print(f"\n📁 Schéma: {schema_name}")
            
            # Utiliser SchemaRoutingService si disponible pour basculer dans le schéma
            if schema_routing_service:
                schema_routing_service.set_schema(schema_name)
                # Utiliser execute_in_schema pour les requêtes dans le schéma spécifique
                # Mais pour information_schema, on peut utiliser directement la session
                result = session.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                      AND table_name IN ('candidat', 'entreprise', 'preinscription')
                    ORDER BY table_name
                """), {"schema_name": schema_name})
            else:
                result = session.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                      AND table_name IN ('candidat', 'entreprise', 'preinscription')
                    ORDER BY table_name
                """), {"schema_name": schema_name})
            
            existing_tables = [row[0] for row in result.fetchall()]
            missing_tables = [t for t in required_tables if t not in existing_tables]
            
            if existing_tables:
                print(f"   ✓ Tables présentes: {', '.join(existing_tables)}")
            if missing_tables:
                print(f"   ❌ Tables manquantes: {', '.join(missing_tables)}")
            if not existing_tables and not missing_tables:
                print(f"   ⚠️  Aucune table essentielle trouvée")
        
        # 5. Vérifier l'existence réelle des tables en utilisant SchemaRoutingService
        if schema_routing_service and program_schemas:
            print("\n🔍 VÉRIFICATION DIRECTE DES TABLES (via SchemaRoutingService):")
            print("-" * 60)
            
            for schema_name in program_schemas:
                print(f"\n📁 Schéma: {schema_name}")
                schema_routing_service.set_schema(schema_name)
                
                for table_name in required_tables:
                    try:
                        # Utiliser execute_in_schema pour vérifier l'existence de la table
                        # En utilisant une requête qui teste directement dans le schéma
                        result = schema_routing_service.execute_in_schema(
                            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = '{schema_name}' AND table_name = '{table_name}')"
                        )
                        exists = result.scalar()
                        status = "✓" if exists else "❌"
                        print(f"   {status} {table_name}: {'Existe' if exists else 'Manquante'}")
                    except Exception as e:
                        print(f"   ❌ {table_name}: Erreur lors de la vérification - {e}")
        
        print()
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des schémas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()
        # Restaurer le répertoire de travail original
        os.chdir(original_cwd)

if __name__ == "__main__":
    list_schemas()
