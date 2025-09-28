"""
Script de test pour vérifier la création automatique de schémas lors de l'ajout de programmes
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import get_session
from app.models.base import Programme
from sqlmodel import select
from core.program_schema_integration import check_and_create_program_schemas

def test_program_creation():
    """Test de création de programme et vérification du schéma"""
    
    print("🧪 TEST: Création de programme et schéma automatique")
    print("=" * 60)
    
    session = next(get_session())
    
    try:
        # 1. Vérifier les programmes existants
        print("📋 ÉTAPE 1: Vérification des programmes existants")
        programmes = session.exec(select(Programme)).all()
        print(f"Programmes trouvés: {[p.code for p in programmes]}")
        
        # 2. Créer un programme de test s'il n'existe pas
        print("\n📋 ÉTAPE 2: Création d'un programme de test")
        test_program = session.exec(
            select(Programme).where(Programme.code == "TEST")
        ).first()
        
        if not test_program:
            test_program = Programme(
                code="TEST",
                nom="Programme de Test",
                objectif="Test de création automatique de schéma",
                actif=True,
                responsable_id=None
            )
            session.add(test_program)
            session.commit()
            print("✅ Programme TEST créé")
        else:
            print("ℹ️ Programme TEST existe déjà")
        
        # 3. Vérifier et créer les schémas
        print("\n📋 ÉTAPE 3: Vérification et création des schémas")
        check_and_create_program_schemas()
        
        # 4. Vérifier que le schéma a été créé
        print("\n📋 ÉTAPE 4: Vérification du schéma créé")
        from core.program_schema_integration import ProgramSchemaManager
        manager = ProgramSchemaManager()
        manager.session = session
        
        if manager.schema_exists("TEST"):
            print("✅ Schéma 'test' créé avec succès")
        else:
            print("❌ Schéma 'test' n'a pas été créé")
        
        print("\n🎉 TEST TERMINÉ")
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        session.close()

if __name__ == "__main__":
    test_program_creation()
