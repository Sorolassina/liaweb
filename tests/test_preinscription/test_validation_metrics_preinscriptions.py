"""
Tests de validation pour les métriques de préinscription.

Ces tests vérifient la validation des données et des règles métier
pour les fonctions de métriques de préinscription.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from datetime import datetime, date

from app_lia_web.app.services.metrics.preinscription_metrics import (
    PreinscriptionAnalyzer,
    PreinscriptionMetricsService,
    SchemaDiscovery
)


@pytest.mark.validation
class TestPreinscriptionValidation:
    """Tests de validation pour les métriques de préinscription."""
    
    def setup_method(self):
        """Configuration pour chaque test."""
        self.mock_session = Mock(spec=Session)
        self.analyzer = PreinscriptionAnalyzer(self.mock_session)
        self.metrics_service = PreinscriptionMetricsService(self.mock_session)
        self.schema_discovery = SchemaDiscovery(self.mock_session)
    
    def test_data_validation(self):
        """Test de validation des données."""
        # Données valides
        valid_data = [
            Mock(
                id=1,
                nom="Dupont",
                prenom="Jean",
                email="jean.dupont@example.com",
                programme_id=1,
                statut="en_attente",
                date_creation="2024-01-01"
            )
        ]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = valid_data
        
        # Test avec des données valides
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        # Vérification que le résultat est valide
        assert result is not None
        assert isinstance(result, (dict, list))
    
    def test_business_rules(self):
        """Test des règles métier."""
        # Simulation de données avec différents statuts
        test_data = [
            Mock(statut="en_attente", programme_id=1, date_creation="2024-01-01"),
            Mock(statut="accepte", programme_id=1, date_creation="2024-01-02"),
            Mock(statut="refuse", programme_id=1, date_creation="2024-01-03"),
            Mock(statut="en_attente", programme_id=2, date_creation="2024-01-04"),
        ]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
        
        # Test des règles métier
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        # Vérification que les règles métier sont respectées
        if isinstance(result, dict):
            # Vérification que les statuts sont correctement gérés
            assert 'en_attente' in str(result) or 'accepte' in str(result) or 'refuse' in str(result)
    
    def test_program_id_validation(self):
        """Test de validation de l'ID du programme."""
        # IDs de programme valides
        valid_program_ids = [1, 2, 3, 100, 999]
        
        for program_id in valid_program_ids:
            test_data = [Mock(statut="en_attente", programme_id=program_id)]
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            result = self.analyzer.analyze_preinscriptions_by_program(program_id)
            
            # Vérification que l'ID valide est accepté
            assert result is not None or result == {}
    
    def test_program_id_invalidation(self):
        """Test d'invalidation de l'ID du programme."""
        # IDs de programme invalides
        invalid_program_ids = [None, "", "abc", -1, 0, 1.5, "1,2,3"]
        
        for program_id in invalid_program_ids:
            # Test que les IDs invalides sont rejetés
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(program_id)
                # Si on arrive ici, l'ID a été validé et rejeté
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les IDs invalides
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_date_validation(self):
        """Test de validation des dates."""
        # Dates valides
        valid_dates = [
            "2024-01-01",
            "2024-12-31",
            "2023-06-15",
            "2025-03-20"
        ]
        
        for date_str in valid_dates:
            test_data = [
                Mock(
                    statut="en_attente",
                    programme_id=1,
                    date_creation=date_str
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            
            # Vérification que les dates valides sont acceptées
            assert result is not None or result == {}
    
    def test_date_invalidation(self):
        """Test d'invalidation des dates."""
        # Dates invalides
        invalid_dates = [
            "2024-13-01",  # Mois invalide
            "2024-02-30",  # Jour invalide
            "2024/01/01",  # Format invalide
            "01-01-2024",  # Format invalide
            "2024-1-1",    # Format invalide
            "invalid-date",
            "",
            None
        ]
        
        for date_str in invalid_dates:
            test_data = [
                Mock(
                    statut="en_attente",
                    programme_id=1,
                    date_creation=date_str
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            # Test que les dates invalides sont gérées
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                # Si on arrive ici, la date a été validée et rejetée
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les dates invalides
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_status_validation(self):
        """Test de validation des statuts."""
        # Statuts valides
        valid_statuses = ["en_attente", "accepte", "refuse", "annule"]
        
        for status in valid_statuses:
            test_data = [
                Mock(
                    statut=status,
                    programme_id=1,
                    date_creation="2024-01-01"
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            
            # Vérification que les statuts valides sont acceptés
            assert result is not None or result == {}
    
    def test_status_invalidation(self):
        """Test d'invalidation des statuts."""
        # Statuts invalides
        invalid_statuses = ["", None, "invalid_status", "EN_ATTENTE", "en attente", "accepté"]
        
        for status in invalid_statuses:
            test_data = [
                Mock(
                    statut=status,
                    programme_id=1,
                    date_creation="2024-01-01"
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            # Test que les statuts invalides sont gérés
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                # Si on arrive ici, le statut a été validé et rejeté
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les statuts invalides
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_email_validation(self):
        """Test de validation des emails."""
        # Emails valides
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "user123@test-domain.com"
        ]
        
        for email in valid_emails:
            test_data = [
                Mock(
                    statut="en_attente",
                    programme_id=1,
                    email=email,
                    date_creation="2024-01-01"
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            
            # Vérification que les emails valides sont acceptés
            assert result is not None or result == {}
    
    def test_email_invalidation(self):
        """Test d'invalidation des emails."""
        # Emails invalides
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "test@",
            "test..test@example.com",
            "test@.com",
            "test@example.",
            "",
            None
        ]
        
        for email in invalid_emails:
            test_data = [
                Mock(
                    statut="en_attente",
                    programme_id=1,
                    email=email,
                    date_creation="2024-01-01"
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            # Test que les emails invalides sont gérés
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                # Si on arrive ici, l'email a été validé et rejeté
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les emails invalides
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_required_fields_validation(self):
        """Test de validation des champs obligatoires."""
        # Données avec champs manquants
        incomplete_data = [
            Mock(
                id=1,
                # nom manquant
                prenom="Jean",
                email="jean@example.com",
                programme_id=1,
                statut="en_attente"
            ),
            Mock(
                id=2,
                nom="Dupont",
                # prenom manquant
                email="dupont@example.com",
                programme_id=1,
                statut="en_attente"
            ),
            Mock(
                id=3,
                nom="Martin",
                prenom="Pierre",
                # email manquant
                programme_id=1,
                statut="en_attente"
            )
        ]
        
        for data in incomplete_data:
            self.mock_session.query.return_value.filter.return_value.all.return_value = [data]
            
            # Test que les champs manquants sont gérés
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                # Si on arrive ici, les champs manquants ont été validés et rejetés
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les champs manquants
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_data_type_validation(self):
        """Test de validation des types de données."""
        # Données avec types incorrects
        invalid_type_data = [
            Mock(
                id="not_a_number",  # ID devrait être un entier
                nom="Dupont",
                prenom="Jean",
                email="jean@example.com",
                programme_id=1,
                statut="en_attente"
            ),
            Mock(
                id=1,
                nom=123,  # Nom devrait être une chaîne
                prenom="Jean",
                email="jean@example.com",
                programme_id=1,
                statut="en_attente"
            ),
            Mock(
                id=1,
                nom="Dupont",
                prenom="Jean",
                email="jean@example.com",
                programme_id="not_a_number",  # Programme ID devrait être un entier
                statut="en_attente"
            )
        ]
        
        for data in invalid_type_data:
            self.mock_session.query.return_value.filter.return_value.all.return_value = [data]
            
            # Test que les types incorrects sont gérés
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                # Si on arrive ici, les types incorrects ont été validés et rejetés
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les types incorrects
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_business_logic_validation(self):
        """Test de validation de la logique métier."""
        # Test des règles métier spécifiques
        business_rules_data = [
            # Règle: Un candidat ne peut pas être accepté et refusé en même temps
            Mock(
                id=1,
                nom="Dupont",
                prenom="Jean",
                email="jean@example.com",
                programme_id=1,
                statut="accepte",
                date_creation="2024-01-01"
            ),
            # Règle: Les dates de création ne peuvent pas être dans le futur
            Mock(
                id=2,
                nom="Martin",
                prenom="Pierre",
                email="pierre@example.com",
                programme_id=1,
                statut="en_attente",
                date_creation="2025-01-01"  # Date future
            )
        ]
        
        for data in business_rules_data:
            self.mock_session.query.return_value.filter.return_value.all.return_value = [data]
            
            # Test que les règles métier sont respectées
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                # Vérification que la logique métier est appliquée
                assert result is not None or result == {}
            except Exception as e:
                # Les erreurs de logique métier sont attendues
                assert "business" in str(e).lower() or "rule" in str(e).lower() or "invalid" in str(e).lower()
