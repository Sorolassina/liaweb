#!/usr/bin/env python3
"""
Script simple pour créer la table des rendez-vous
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent))

from app_lia_web.core.database import create_db_and_tables
from app_lia_web.app.models.base import RendezVous

def create_rendez_vous_table():
    """Créer la table des rendez-vous"""
    try:
        print("🚀 Création de la table des rendez-vous...")
        create_db_and_tables()
        print("✅ Table des rendez-vous créée avec succès")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création de la table: {e}")
        return False

if __name__ == "__main__":
    success = create_rendez_vous_table()
    sys.exit(0 if success else 1)
