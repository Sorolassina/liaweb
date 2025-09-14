# scripts/migrate_seminaires.py
"""
Script de migration pour créer les tables des séminaires
"""
import sys
import os
from pathlib import Path

# Ajouter le chemin du projet


from sqlmodel import SQLModel, create_engine
from app_lia_web.core.config import settings
from app_lia_web.app.models.seminaire import (
    Seminaire, SessionSeminaire, InvitationSeminaire, 
    PresenceSeminaire, LivrableSeminaire, RenduLivrable
)

def migrate_seminaires():
    """Créer les tables des séminaires"""
    print("🚀 Début de la migration des séminaires...")
    
    # Créer le moteur de base de données
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # Créer toutes les tables des séminaires
        print("📋 Création des tables...")
        SQLModel.metadata.create_all(engine)
        
        print("✅ Migration des séminaires terminée avec succès!")
        print("\nTables créées:")
        print("- seminaire")
        print("- sessionseminaire") 
        print("- invitationseminaire")
        print("- presenceseminaire")
        print("- livrableseminaire")
        print("- rendulivrable")
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        return False
    
    return True

def verify_tables():
    """Vérifier que les tables ont été créées"""
    print("\n🔍 Vérification des tables...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Vérifier chaque table
            tables_to_check = [
                'seminaire',
                'sessionseminaire', 
                'invitationseminaire',
                'presenceseminaire',
                'livrableseminaire',
                'rendulivrable'
            ]
            
            for table in tables_to_check:
                result = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = result.scalar()
                print(f"✅ Table '{table}': {count} enregistrements")
                
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("MIGRATION DES SÉMINAIRES")
    print("=" * 50)
    
    # Exécuter la migration
    if migrate_seminaires():
        # Vérifier les tables
        verify_tables()
        
        print("\n🎉 Migration terminée avec succès!")
        print("\nProchaines étapes:")
        print("1. Ajouter le routeur seminaire à main.py")
        print("2. Créer les templates manquants")
        print("3. Configurer les permissions")
        print("4. Tester les fonctionnalités")
    else:
        print("\n💥 Migration échouée!")
        sys.exit(1)
