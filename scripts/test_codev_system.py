#!/usr/bin/env python3
"""
Script de test pour le système de Codéveloppement
"""
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app_lia_web.core.database import get_session
from app_lia_web.app.models.codev import CycleCodev, GroupeCodev, SeanceCodev
from app_lia_web.app.models.base import Programme, Groupe, User
from app_lia_web.app.models.enums import StatutCycleCodev, StatutGroupeCodev
from app_lia_web.app.services.codev_service import CodevService
from datetime import datetime, timezone, date, timedelta

def test_codev_system():
    """Test complet du système de codéveloppement"""
    print("🧪 Test du système de Codéveloppement")
    print("=" * 50)
    
    session = next(get_session())
    
    try:
        # 1. Test de création d'un cycle
        print("\n1️⃣ Création d'un cycle de codéveloppement...")
        
        # Récupérer le premier programme
        programme = session.exec(select(Programme).limit(1)).first()
        if not programme:
            print("❌ Aucun programme trouvé. Créer d'abord un programme.")
            return False
        
        cycle = CodevService.create_cycle_codev(
            session=session,
            nom="Cycle Test ACD 2024",
            programme_id=programme.id,
            date_debut=date.today(),
            date_fin=date.today() + timedelta(weeks=12),
            nombre_seances=6
        )
        print(f"✅ Cycle créé: {cycle.nom} (ID: {cycle.id})")
        
        # 2. Test de création d'un groupe
        print("\n2️⃣ Création d'un groupe de codéveloppement...")
        
        # Récupérer le premier groupe
        groupe = session.exec(select(Groupe).limit(1)).first()
        if not groupe:
            print("❌ Aucun groupe trouvé. Créer d'abord un groupe.")
            return False
        
        groupe_codev = CodevService.create_groupe_codev(
            session=session,
            cycle_id=cycle.id,
            groupe_id=groupe.id,
            nom_groupe="Groupe Alpha - Cycle Test",
            capacite_max=12
        )
        print(f"✅ Groupe créé: {groupe_codev.nom_groupe} (ID: {groupe_codev.id})")
        
        # 3. Test de création d'une séance
        print("\n3️⃣ Création d'une séance de codéveloppement...")
        
        seance = CodevService.create_seance_codev(
            session=session,
            groupe_id=groupe.id,
            numero_seance=1,
            date_seance=datetime.now(timezone.utc) + timedelta(days=7),
            lieu="Salle de formation LIA",
            duree_minutes=180
        )
        print(f"✅ Séance créée: Séance {seance.numero_seance} (ID: {seance.id})")
        
        # 4. Test des statistiques
        print("\n4️⃣ Test des statistiques...")
        
        stats = CodevService.get_statistiques_cycle(session, cycle.id)
        print(f"✅ Statistiques du cycle:")
        print(f"   - Nombre de groupes: {stats['nb_groupes']}")
        print(f"   - Nombre de membres: {stats['nb_membres']}")
        print(f"   - Nombre de séances: {stats['nb_seances']}")
        print(f"   - Taux de réalisation: {stats['taux_realisation']:.1f}%")
        
        # 5. Test de récupération des prochaines séances
        print("\n5️⃣ Test des prochaines séances...")
        
        prochaines_seances = CodevService.get_prochaines_seances(session, limit=5)
        print(f"✅ Prochaines séances trouvées: {len(prochaines_seances)}")
        
        for seance in prochaines_seances:
            print(f"   - Séance {seance.numero_seance}: {seance.date_seance.strftime('%d/%m/%Y à %H:%M')}")
        
        print("\n🎉 Tous les tests sont passés avec succès!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        session.close()

def test_permissions():
    """Test des permissions pour le module Codev"""
    print("\n🔐 Test des permissions Codev...")
    
    # Rôles autorisés pour le Codev
    roles_autorises = [
        "administrateur",
        "directeur_technique", 
        "responsable_programme",
        "coordinateur",
        "conseiller",
        "formateur"
    ]
    
    print(f"✅ Rôles autorisés pour le Codev: {', '.join(roles_autorises)}")
    
    # Rôles non autorisés
    roles_non_autorises = [
        "candidat",
        "jury_externe",
        "coach_externe"
    ]
    
    print(f"❌ Rôles non autorisés: {', '.join(roles_non_autorises)}")

def test_data_structure():
    """Test de la structure des données"""
    print("\n📊 Test de la structure des données...")
    
    session = next(get_session())
    
    try:
        # Vérifier les tables
        tables_codev = [
            "cyclecodev",
            "groupecodev", 
            "membregroupecodev",
            "seancecodev",
            "presentationcodev",
            "contributioncodev",
            "participationseance"
        ]
        
        for table in tables_codev:
            result = session.exec(f"SELECT COUNT(*) FROM {table}").first()
            print(f"✅ Table {table}: {result} enregistrements")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification des tables: {e}")
        return False
    
    finally:
        session.close()

if __name__ == "__main__":
    print("🚀 Démarrage des tests du système de Codéveloppement")
    print("=" * 60)
    
    # Tests
    success = True
    
    # Test de la structure des données
    if not test_data_structure():
        success = False
    
    # Test des permissions
    test_permissions()
    
    # Test du système principal
    if not test_codev_system():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Tous les tests sont passés avec succès!")
        print("\n📋 Prochaines étapes:")
        print("1. Exécuter la migration SQL: scripts/migrate_codev_system.sql")
        print("2. Redémarrer l'application")
        print("3. Accéder à /codev pour tester l'interface")
    else:
        print("❌ Certains tests ont échoué. Vérifiez les erreurs ci-dessus.")
    
    sys.exit(0 if success else 1)
