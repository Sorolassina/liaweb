#!/usr/bin/env python3
"""
Script pour modifier les enums dans la base de données PostgreSQL
Usage: python scripts/modify_enums.py
"""

import psycopg2
import sys
from pathlib import Path

# Configuration de la base de données
DB_CONFIG = {
    'host': 'localhost',
    'user': 'liauser',
    'password': 'liapass',  # À adapter selon votre configuration
    'database': 'lia_coaching'
}

def add_enum_values(enum_name: str, new_values: list):
    """Ajouter de nouvelles valeurs à un enum existant"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        for value in new_values:
            try:
                cursor.execute(f"ALTER TYPE {enum_name} ADD VALUE '{value}';")
                print(f"✅ Ajouté '{value}' à l'enum {enum_name}")
            except psycopg2.errors.DuplicateObject:
                print(f"⚠️ '{value}' existe déjà dans {enum_name}")
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Modification de l'enum {enum_name} terminée")
        
    except Exception as e:
        print(f"❌ Erreur lors de la modification de {enum_name}: {e}")

def create_new_enum_type(old_enum_name: str, new_enum_name: str, values: list):
    """Créer un nouveau type enum avec les valeurs spécifiées"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Créer le nouveau type
        values_str = "', '".join(values)
        cursor.execute(f"CREATE TYPE {new_enum_name} AS ENUM ('{values_str}');")
        print(f"✅ Créé le nouveau type {new_enum_name}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de {new_enum_name}: {e}")

def migrate_enum_column(table_name: str, column_name: str, old_enum: str, new_enum: str, mapping: dict):
    """Migrer une colonne d'un enum vers un autre"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Ajouter une colonne temporaire
        temp_column = f"{column_name}_temp"
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {temp_column} {new_enum};")
        print(f"✅ Ajouté la colonne temporaire {temp_column}")
        
        # Migrer les données
        for old_value, new_value in mapping.items():
            cursor.execute(f"""
                UPDATE {table_name} 
                SET {temp_column} = '{new_value}'::text::"{new_enum}"
                WHERE {column_name} = '{old_value}';
            """)
            print(f"✅ Migré '{old_value}' → '{new_value}'")
        
        # Supprimer l'ancienne colonne et renommer
        cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name};")
        cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN {temp_column} TO {column_name};")
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Migration de {table_name}.{column_name} terminée")
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")

def main():
    """Fonction principale avec exemples d'utilisation"""
    print("🔧 Script de modification des enums")
    print("=" * 50)
    
    # Exemple 1: Ajouter de nouvelles valeurs à GroupeCodev
    print("\n📝 Exemple 1: Ajouter de nouveaux groupes")
    new_groups = ['GROUPE_11', 'GROUPE_12', 'GROUPE_SPECIAL']
    add_enum_values('groupecodev', new_groups)
    
    # Exemple 2: Créer un nouveau type enum
    print("\n📝 Exemple 2: Créer un nouveau type")
    new_promotion_values = [
        'PROMOTION_2027_A', 'PROMOTION_2027_B', 'PROMOTION_2027_C'
    ]
    create_new_enum_type('typepromotion', 'typepromotion_new', new_promotion_values)
    
    # Exemple 3: Migration complète (commenté pour éviter les erreurs)
    print("\n📝 Exemple 3: Migration complète (commenté)")
    print("# Décommentez et adaptez selon vos besoins:")
    print("# mapping = {'GROUPE_1': 'GROUPE_A', 'GROUPE_2': 'GROUPE_B'}")
    print("# migrate_enum_column('decisionjurycandidat', 'groupe_codev', 'groupecodev', 'groupecodev_new', mapping)")

if __name__ == "__main__":
    main()
