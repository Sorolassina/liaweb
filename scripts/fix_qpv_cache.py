#!/usr/bin/env python3
"""
Script pour corriger les données QPV en cache malformées
Convertit les données sauvegardées avec str() vers le format JSON propre
"""

import sys
import os
import json
import ast
from pathlib import Path

# Ajouter le répertoire parent au path pour importer les modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app_lia_web.core.config import settings

def fix_qpv_cache():
    """Corrige les données QPV en cache malformées"""
    
    print("🔧 Début de la correction des données QPV en cache...")
    
    # Connexion à la base de données
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Récupérer toutes les éligibilités avec des données QPV
        result = conn.execute(text("""
            SELECT id, details_json, qpv_ok 
            FROM eligibilite 
            WHERE details_json IS NOT NULL 
            AND details_json != ''
            AND qpv_ok IS NOT NULL
        """))
        
        rows = result.fetchall()
        print(f"📊 Trouvé {len(rows)} enregistrements à vérifier")
        
        fixed_count = 0
        error_count = 0
        
        for row in rows:
            eligibilite_id, details_json, qpv_ok = row
            
            try:
                # Essayer de parser comme JSON
                try:
                    json.loads(details_json)
                    print(f"✅ ID {eligibilite_id}: JSON valide, pas de correction nécessaire")
                    continue
                except json.JSONDecodeError:
                    pass
                
                # Essayer de parser comme dict Python
                try:
                    data = ast.literal_eval(details_json)
                    print(f"🔧 ID {eligibilite_id}: Conversion dict Python → JSON")
                    
                    # Convertir en JSON propre
                    new_json = json.dumps(data, ensure_ascii=False, indent=None)
                    
                    # Mettre à jour en base
                    conn.execute(text("""
                        UPDATE eligibilite 
                        SET details_json = :new_json 
                        WHERE id = :id
                    """), {"new_json": new_json, "id": eligibilite_id})
                    
                    fixed_count += 1
                    
                except (ValueError, SyntaxError) as e:
                    print(f"❌ ID {eligibilite_id}: Impossible de parser - {e}")
                    error_count += 1
                    
            except Exception as e:
                print(f"❌ ID {eligibilite_id}: Erreur générale - {e}")
                error_count += 1
        
        # Commit des changements
        conn.commit()
        
        print(f"\n📈 Résumé:")
        print(f"   ✅ Corrigés: {fixed_count}")
        print(f"   ❌ Erreurs: {error_count}")
        print(f"   📊 Total: {len(rows)}")
        
        if fixed_count > 0:
            print(f"\n🎉 Migration terminée avec succès!")
        else:
            print(f"\nℹ️ Aucune correction nécessaire")

if __name__ == "__main__":
    fix_qpv_cache()
