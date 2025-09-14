# scripts/test_seminaires.py
"""
Script de test pour vérifier le système de séminaires
"""
import sys
import os
from pathlib import Path

# Ajouter le chemin du projet
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, select
from app_lia_web.core.database import get_session
from app_lia_web.app.models.seminaire import (
    Seminaire, SessionSeminaire, InvitationSeminaire, 
    PresenceSeminaire, LivrableSeminaire, RenduLivrable
)
from app_lia_web.app.models.base import Programme, User, Inscription
from app_lia_web.app.models.enums import StatutSeminaire, TypeInvitation, StatutPresence
from app_lia_web.app.services.seminaire_service import SeminaireService
from datetime import datetime, date, timezone

def test_seminaire_creation():
    """Tester la création d'un séminaire"""
    print("🧪 Test de création de séminaire...")
    
    with get_session() as db:
        # Récupérer un programme existant
        programme = db.exec(select(Programme).limit(1)).first()
        if not programme:
            print("❌ Aucun programme trouvé. Créez d'abord un programme.")
            return False
        
        # Récupérer un utilisateur existant
        user = db.exec(select(User).limit(1)).first()
        if not user:
            print("❌ Aucun utilisateur trouvé. Créez d'abord un utilisateur.")
            return False
        
        # Créer un séminaire de test
        seminaire_data = {
            'titre': 'Séminaire de Test',
            'description': 'Séminaire créé pour tester le système',
            'programme_id': programme.id,
            'date_debut': date.today(),
            'date_fin': date.today(),
            'lieu': 'Salle de conférence',
            'organisateur_id': user.id,
            'capacite_max': 50,
            'invitation_auto': False,
            'invitation_promos': False
        }
        
        seminaire = Seminaire(**seminaire_data)
        db.add(seminaire)
        db.commit()
        db.refresh(seminaire)
        
        print(f"✅ Séminaire créé avec l'ID: {seminaire.id}")
        return seminaire

def test_session_creation(seminaire_id):
    """Tester la création d'une session"""
    print("🧪 Test de création de session...")
    
    with get_session() as db:
        session_data = {
            'seminaire_id': seminaire_id,
            'titre': 'Session Matin',
            'description': 'Session du matin du séminaire',
            'date_session': date.today(),
            'heure_debut': datetime.now(timezone.utc),
            'heure_fin': datetime.now(timezone.utc),
            'lieu': 'Salle A',
            'obligatoire': True
        }
        
        session = SessionSeminaire(**session_data)
        db.add(session)
        db.commit()
        db.refresh(session)
        
        print(f"✅ Session créée avec l'ID: {session.id}")
        return session

def test_invitation_creation(seminaire_id):
    """Tester la création d'une invitation"""
    print("🧪 Test de création d'invitation...")
    
    with get_session() as db:
        # Récupérer une inscription existante
        inscription = db.exec(select(Inscription).limit(1)).first()
        if not inscription:
            print("❌ Aucune inscription trouvée. Créez d'abord une inscription.")
            return False
        
        invitation_data = {
            'seminaire_id': seminaire_id,
            'type_invitation': TypeInvitation.INDIVIDUELLE,
            'inscription_id': inscription.id,
            'statut': 'ENVOYEE',
            'token_invitation': 'test_token_123456789'
        }
        
        invitation = InvitationSeminaire(**invitation_data)
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        
        print(f"✅ Invitation créée avec l'ID: {invitation.id}")
        return invitation

def test_presence_creation(session_id, inscription_id):
    """Tester la création d'une présence"""
    print("🧪 Test de création de présence...")
    
    with get_session() as db:
        presence_data = {
            'session_id': session_id,
            'inscription_id': inscription_id,
            'presence': StatutPresence.PRESENT,
            'methode_signature': 'MANUEL',
            'note': 'Présent à la session'
        }
        
        presence = PresenceSeminaire(**presence_data)
        db.add(presence)
        db.commit()
        db.refresh(presence)
        
        print(f"✅ Présence créée avec l'ID: {presence.id}")
        return presence

def test_livrable_creation(seminaire_id):
    """Tester la création d'un livrable"""
    print("🧪 Test de création de livrable...")
    
    with get_session() as db:
        livrable_data = {
            'seminaire_id': seminaire_id,
            'titre': 'Rapport de Séminaire',
            'description': 'Rapport à rendre à la fin du séminaire',
            'type_livrable': 'DOCUMENT',
            'obligatoire': True,
            'consignes': 'Rédiger un rapport de 2 pages maximum',
            'format_accepte': 'PDF',
            'taille_max_mb': 5
        }
        
        livrable = LivrableSeminaire(**livrable_data)
        db.add(livrable)
        db.commit()
        db.refresh(livrable)
        
        print(f"✅ Livrable créé avec l'ID: {livrable.id}")
        return livrable

def test_service_methods():
    """Tester les méthodes du service"""
    print("🧪 Test des méthodes du service...")
    
    service = SeminaireService()
    
    with get_session() as db:
        # Tester get_seminaires
        seminaires = service.get_seminaires(db)
        print(f"✅ Nombre de séminaires trouvés: {len(seminaires)}")
        
        # Tester get_seminaire_stats
        stats = service.get_seminaire_stats(db)
        print(f"✅ Statistiques: {stats}")
        
        return True

def cleanup_test_data():
    """Nettoyer les données de test"""
    print("🧹 Nettoyage des données de test...")
    
    with get_session() as db:
        # Supprimer les données de test
        db.exec(select(RenduLivrable).where(RenduLivrable.nom_fichier.like('%test%'))).delete()
        db.exec(select(LivrableSeminaire).where(LivrableSeminaire.titre.like('%Test%'))).delete()
        db.exec(select(PresenceSeminaire).where(PresenceSeminaire.note.like('%test%'))).delete()
        db.exec(select(InvitationSeminaire).where(InvitationSeminaire.token_invitation.like('%test%'))).delete()
        db.exec(select(SessionSeminaire).where(SessionSeminaire.titre.like('%Test%'))).delete()
        db.exec(select(Seminaire).where(Seminaire.titre.like('%Test%'))).delete()
        
        db.commit()
        print("✅ Données de test nettoyées")

def main():
    """Fonction principale de test"""
    print("=" * 60)
    print("TEST DU SYSTÈME DE SÉMINAIRES")
    print("=" * 60)
    
    try:
        # Test 1: Création de séminaire
        seminaire = test_seminaire_creation()
        if not seminaire:
            return
        
        # Test 2: Création de session
        session = test_session_creation(seminaire.id)
        if not session:
            return
        
        # Test 3: Création d'invitation
        invitation = test_invitation_creation(seminaire.id)
        if not invitation:
            return
        
        # Test 4: Création de présence
        presence = test_presence_creation(session.id, invitation.inscription_id)
        if not presence:
            return
        
        # Test 5: Création de livrable
        livrable = test_livrable_creation(seminaire.id)
        if not livrable:
            return
        
        # Test 6: Méthodes du service
        test_service_methods()
        
        print("\n🎉 Tous les tests sont passés avec succès!")
        print("\nFonctionnalités testées:")
        print("✅ Création de séminaire")
        print("✅ Création de session")
        print("✅ Création d'invitation")
        print("✅ Création de présence")
        print("✅ Création de livrable")
        print("✅ Méthodes du service")
        
        # Nettoyer les données de test
        cleanup_test_data()
        
    except Exception as e:
        print(f"❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
