"""
Tests unitaires pour les modèles SQLModel
"""
import pytest
from datetime import date, datetime
from app_lia_web.app.models.base import User, Programme, SessionProgramme, SessionParticipant
from app_lia_web.app.models.enums import UserRole, TypeUtilisateur, StatutDossier


class TestUser:
    """Tests pour le modèle User."""
    
    def test_user_creation(self):
        """Test de la création d'un utilisateur."""
        user = User(
            email="test@example.com",
            nom_complet="Test User",
            mot_de_passe_hash="hashed_password",
            role=UserRole.CONSEILLER,
            type_utilisateur=TypeUtilisateur.INTERNE,
            actif=True
        )
        
        assert user.email == "test@example.com"
        assert user.nom_complet == "Test User"
        assert user.role == UserRole.CONSEILLER
        assert user.type_utilisateur == TypeUtilisateur.INTERNE
        assert user.actif is True
        assert user.telephone is None  # Champ optionnel
    
    def test_user_role_enum(self):
        """Test des valeurs d'enum pour le rôle utilisateur."""
        user = User(
            email="test@example.com",
            nom_complet="Test User",
            mot_de_passe_hash="hashed_password",
            role=UserRole.ADMIN
        )
        
        assert user.role == UserRole.ADMIN
        assert user.role.value == "admin"
    
    def test_user_defaults(self):
        """Test des valeurs par défaut."""
        user = User(
            email="test@example.com",
            nom_complet="Test User",
            mot_de_passe_hash="hashed_password"
        )
        
        assert user.actif is True  # Valeur par défaut
        assert user.role is None  # Pas de valeur par défaut définie


class TestProgramme:
    """Tests pour le modèle Programme."""
    
    def test_programme_creation(self):
        """Test de la création d'un programme."""
        programme = Programme(
            nom="Test Programme",
            description="Description du programme test",
            duree_mois=12,
            actif=True
        )
        
        assert programme.nom == "Test Programme"
        assert programme.description == "Description du programme test"
        assert programme.duree_mois == 12
        assert programme.actif is True
    
    def test_programme_defaults(self):
        """Test des valeurs par défaut."""
        programme = Programme(nom="Test Programme")
        
        assert programme.actif is True
        assert programme.description is None
        assert programme.duree_mois is None


class TestSession:
    """Tests pour le modèle Session."""
    
    def test_session_creation(self):
        """Test de la création d'une session."""
        session = Session(
            nom="Session Test",
            programme_id=1,
            date_debut=date(2024, 1, 1),
            date_fin=date(2024, 12, 31),
            statut="planifie"
        )
        
        assert session.nom == "Session Test"
        assert session.programme_id == 1
        assert session.date_debut == date(2024, 1, 1)
        assert session.date_fin == date(2024, 12, 31)
        assert session.statut == "planifie"


class TestEvent:
    """Tests pour le modèle Event."""
    
    def test_event_creation(self):
        """Test de la création d'un événement."""
        event = Event(
            titre="Événement Test",
            description="Description de l'événement",
            date_debut=date(2024, 6, 1),
            lieu="Lieu de l'événement",
            statut="planifie",
            programme_id=1,
            organisateur_id=1
        )
        
        assert event.titre == "Événement Test"
        assert event.description == "Description de l'événement"
        assert event.date_debut == date(2024, 6, 1)
        assert event.lieu == "Lieu de l'événement"
        assert event.statut == "planifie"
        assert event.programme_id == 1
        assert event.organisateur_id == 1
    
    def test_event_defaults(self):
        """Test des valeurs par défaut."""
        event = Event(
            titre="Événement Test",
            programme_id=1,
            organisateur_id=1
        )
        
        assert event.statut == "planifie"  # Valeur par défaut
        assert event.description is None
        assert event.date_fin is None


# Tests d'intégration avec la base de données
@pytest.mark.integration
@pytest.mark.database
class TestModelsIntegration:
    """Tests d'intégration pour les modèles avec la base de données."""
    
    def test_user_crud(self, test_session):
        """Test CRUD pour le modèle User."""
        # Create
        user = User(
            email="integration@test.com",
            nom_complet="Integration Test",
            mot_de_passe_hash="hashed_password",
            role=UserRole.CONSEILLER
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        
        assert user.id is not None
        assert user.email == "integration@test.com"
        
        # Read
        found_user = test_session.get(User, user.id)
        assert found_user is not None
        assert found_user.nom_complet == "Integration Test"
        
        # Update
        found_user.nom_complet = "Updated Name"
        test_session.commit()
        test_session.refresh(found_user)
        
        assert found_user.nom_complet == "Updated Name"
        
        # Delete
        test_session.delete(found_user)
        test_session.commit()
        
        deleted_user = test_session.get(User, user.id)
        assert deleted_user is None
    
    def test_programme_crud(self, test_session):
        """Test CRUD pour le modèle Programme."""
        # Create
        programme = Programme(
            nom="Integration Programme",
            description="Programme d'intégration",
            duree_mois=6
        )
        test_session.add(programme)
        test_session.commit()
        test_session.refresh(programme)
        
        assert programme.id is not None
        assert programme.nom == "Integration Programme"
        
        # Read
        found_programme = test_session.get(Programme, programme.id)
        assert found_programme is not None
        assert found_programme.duree_mois == 6
        
        # Update
        found_programme.duree_mois = 12
        test_session.commit()
        test_session.refresh(found_programme)
        
        assert found_programme.duree_mois == 12
        
        # Delete
        test_session.delete(found_programme)
        test_session.commit()
        
        deleted_programme = test_session.get(Programme, programme.id)
        assert deleted_programme is None
    
    def test_user_programme_relationship(self, test_session, sample_user, sample_programme):
        """Test de la relation entre User et Programme."""
        # Vérifier que les objets de test existent
        assert sample_user.id is not None
        assert sample_programme.id is not None
        
        # Les relations directes ne sont pas définies dans les modèles de base
        # mais on peut vérifier que les IDs existent
        assert sample_user.id > 0
        assert sample_programme.id > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
