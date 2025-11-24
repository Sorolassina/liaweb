#!/usr/bin/env python3
"""
Script pour corriger toutes les contraintes de clés étrangères dans decision_jury_candidat
qui référencent des tables dans le schéma public (jury, promotion, groupe, partenaire, user)
"""
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine
from sqlalchemy import text
from sqlmodel import Session

def fix_public_foreign_keys():
    """Corrige toutes les contraintes de clés étrangères vers public pour tous les schémas de programme"""
    session = Session(engine)
    
    # Liste des contraintes à corriger (nom_constrainte, colonne, table_public)
    foreign_keys_to_fix = [
        ("decision_jury_candidat_jury_id_fkey", "jury_id", "jury"),
        ("decision_jury_candidat_promotion_id_fkey", "promotion_id", "promotion"),
        ("decision_jury_candidat_groupe_id_fkey", "groupe_id", "groupe"),
        ("decision_jury_candidat_partenaire_id_fkey", "partenaire_id", "partenaire"),
        ("decision_jury_candidat_conseiller_id_fkey", "conseiller_id", "user"),
    ]
    
    try:
        # Récupérer tous les schémas de programme
        result = session.exec(text("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
            AND schema_name NOT LIKE 'pg_%'
        """))
        
        schemas = [row[0] for row in result]
        print(f"📋 Schémas trouvés: {schemas}")
        
        for schema in schemas:
            print(f"\n🔧 Correction des contraintes pour le schéma: {schema}")
            
            # Vérifier si la table existe
            table_check = session.exec(text(f"""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_schema = :schema 
                    AND table_name = 'decision_jury_candidat'
                )
            """).bindparams(schema=schema)).first()
            
            if not table_check[0]:
                print(f"  ⚠️  Table decision_jury_candidat n'existe pas dans {schema}, ignoré")
                continue
            
            # Corriger chaque contrainte
            for constraint_name, column_name, public_table in foreign_keys_to_fix:
                print(f"  🔧 Correction de {constraint_name} ({column_name} -> public.{public_table})")
                
                # Vérifier si la contrainte existe
                constraint_check = session.exec(text(f"""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_schema = :schema 
                    AND table_name = 'decision_jury_candidat'
                    AND constraint_name = :constraint_name
                """).bindparams(schema=schema, constraint_name=constraint_name)).first()
                
                if constraint_check:
                    print(f"    ✓ Contrainte trouvée, suppression...")
                    # Supprimer l'ancienne contrainte
                    session.exec(text(f"""
                        ALTER TABLE {schema}.decision_jury_candidat 
                        DROP CONSTRAINT IF EXISTS {constraint_name}
                    """))
                    session.commit()
                    print(f"    ✓ Ancienne contrainte supprimée")
                
                # Vérifier si la colonne existe avant de créer la contrainte
                column_check = session.exec(text(f"""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_schema = :schema 
                        AND table_name = 'decision_jury_candidat'
                        AND column_name = :column_name
                    )
                """).bindparams(schema=schema, column_name=column_name)).first()
                
                if column_check[0]:
                    # Créer la nouvelle contrainte qui référence explicitement public.table
                    print(f"    ✓ Création de la nouvelle contrainte vers public.{public_table}...")
                    try:
                        session.exec(text(f"""
                            ALTER TABLE {schema}.decision_jury_candidat 
                            ADD CONSTRAINT {constraint_name} 
                            FOREIGN KEY ({column_name}) REFERENCES public.{public_table}(id)
                        """))
                        session.commit()
                        print(f"    ✅ Contrainte corrigée pour {constraint_name}")
                    except Exception as e:
                        print(f"    ⚠️  Erreur lors de la création de {constraint_name}: {e}")
                        session.rollback()
                else:
                    print(f"    ⚠️  Colonne {column_name} n'existe pas, ignoré")
        
        print("\n✅ Toutes les contraintes ont été corrigées avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return False
    finally:
        session.close()
    
    return True

if __name__ == "__main__":
    print("=" * 80)
    print("🔧 Correction des contraintes de clés étrangères vers public")
    print("=" * 80)
    success = fix_public_foreign_keys()
    sys.exit(0 if success else 1)

