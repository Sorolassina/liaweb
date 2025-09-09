#!/usr/bin/env python3
"""
Script de migration pour créer la table des rendez-vous
"""
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from core.database import engine
from sqlmodel import text

def create_rendez_vous_table():
    """Créer la table des rendez-vous"""
    
    # Lire le script SQL
    script_path = Path(__file__).parent / "create_rendez_vous_table.sql"
    
    if not script_path.exists():
        print(f"❌ Script SQL non trouvé: {script_path}")
        return False
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Exécuter le script
        with engine.connect() as conn:
            conn.execute(text(sql_script))
            conn.commit()
        
        print("✅ Table des rendez-vous créée avec succès")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de la table: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Création de la table des rendez-vous...")
    success = create_rendez_vous_table()
    
    if success:
        print("✅ Migration terminée avec succès")
        sys.exit(0)
    else:
        print("❌ Migration échouée")
        sys.exit(1)
