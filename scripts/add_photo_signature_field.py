#!/usr/bin/env python3
"""
Migration pour ajouter le champ photo_signature à la table PresenceSeminaire
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app_lia_web.core.database import engine

def add_photo_signature_field():
    """Ajouter le champ photo_signature à la table PresenceSeminaire"""
    
    try:
        with engine.connect() as conn:
            # Vérifier si la colonne existe déjà
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'presenceseminaire' 
                AND column_name = 'photo_signature'
            """))
            
            if result.fetchone():
                print("✅ La colonne 'photo_signature' existe déjà dans la table 'presenceseminaire'")
                return
            
            # Ajouter la colonne
            conn.execute(text("""
                ALTER TABLE presenceseminaire 
                ADD COLUMN photo_signature TEXT
            """))
            
            conn.commit()
            print("✅ Colonne 'photo_signature' ajoutée avec succès à la table 'presenceseminaire'")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout de la colonne: {e}")
        raise

if __name__ == "__main__":
    add_photo_signature_field()
