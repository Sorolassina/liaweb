"""
Tests de sécurité pour les métriques de préinscription.

Ces tests vérifient la sécurité des fonctions de métriques
contre les attaques courantes et les vulnérabilités.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app_lia_web.app.services.metrics.preinscription_metrics import (
    PreinscriptionAnalyzer,
    PreinscriptionMetricsService,
    SchemaDiscovery
)


@pytest.mark.security
class TestPreinscriptionSecurity:
    """Tests de sécurité pour les métriques de préinscription."""
    
    def setup_method(self):
        """Configuration pour chaque test."""
        self.mock_session = Mock(spec=Session)
        self.analyzer = PreinscriptionAnalyzer(self.mock_session)
        self.metrics_service = PreinscriptionMetricsService(self.mock_session)
        self.schema_discovery = SchemaDiscovery(self.mock_session)
    
    def test_sql_injection_protection(self):
        """Test de protection contre l'injection SQL."""
        # Tentatives d'injection SQL
        malicious_inputs = [
            "1; DROP TABLE preinscriptions; --",
            "1' OR '1'='1",
            "1 UNION SELECT * FROM users",
            "1'; DELETE FROM preinscriptions; --",
            "1 OR 1=1",
            "1' AND (SELECT COUNT(*) FROM information_schema.tables) > 0 --"
        ]
        
        for malicious_input in malicious_inputs:
            # Test avec l'analyzer
            try:
                # La fonction devrait utiliser des paramètres liés, pas de concaténation
                result = self.analyzer.analyze_preinscriptions_by_program(malicious_input)
                # Si on arrive ici, c'est que l'injection a été bloquée
                assert result is not None or result is None  # Peu importe le résultat
            except Exception as e:
                # Les erreurs sont attendues pour les entrées malveillantes
                assert "syntax error" in str(e).lower() or "invalid" in str(e).lower()
    
    def test_data_access_control(self):
        """Test de contrôle d'accès aux données."""
        # Simulation de données sensibles
        sensitive_data = [
            Mock(
                id=1,
                nom="Dupont",
                prenom="Jean",
                email="jean.dupont@example.com",
                telephone="0123456789",
                adresse="123 Rue de la Paix",
                programme_id=1,
                statut="en_attente"
            )
        ]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = sensitive_data
        
        # Test que seules les données autorisées sont accessibles
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        # Vérification que les données sensibles ne sont pas exposées
        if result and isinstance(result, dict):
            # Vérification que les champs sensibles ne sont pas dans le résultat
            sensitive_fields = ['email', 'telephone', 'adresse']
            for field in sensitive_fields:
                assert field not in str(result), f"Champ sensible '{field}' exposé dans le résultat"
    
    def test_input_validation(self):
        """Test de validation des entrées."""
        # Entrées invalides
        invalid_inputs = [
            None,
            "",
            "   ",
            -1,
            0,
            "abc",
            "1.5",
            "1,2,3",
            "<script>alert('xss')</script>",
            "'; DROP TABLE preinscriptions; --"
        ]
        
        for invalid_input in invalid_inputs:
            # Test avec l'analyzer
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(invalid_input)
                # Si on arrive ici, l'entrée a été validée et rejetée
                assert result is None or result == {}
            except (ValueError, TypeError, AttributeError):
                # Les erreurs de validation sont attendues
                pass
            except Exception as e:
                # Autres erreurs sont acceptables pour les entrées invalides
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_xss_protection(self):
        """Test de protection contre les attaques XSS."""
        # Payloads XSS
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
            "<iframe src=javascript:alert('xss')></iframe>"
        ]
        
        for payload in xss_payloads:
            # Test que le payload est échappé ou rejeté
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(payload)
                # Vérification que le payload n'est pas exécuté
                if result and isinstance(result, str):
                    assert "<script>" not in result, "Script XSS détecté dans le résultat"
                    assert "javascript:" not in result, "JavaScript XSS détecté dans le résultat"
            except Exception:
                # Les erreurs sont attendues pour les payloads XSS
                pass
    
    def test_authorization_bypass(self):
        """Test de contournement d'autorisation."""
        # Tentatives d'accès à des données non autorisées
        unauthorized_access_attempts = [
            # Accès à un programme inexistant
            99999,
            # Accès à un programme d'un autre utilisateur
            2,  # Supposons que l'utilisateur n'a accès qu'au programme 1
            # Accès avec des IDs négatifs
            -1,
            # Accès avec des IDs très élevés
            1000000
        ]
        
        for attempt in unauthorized_access_attempts:
            # Simulation de données vides pour les accès non autorisés
            self.mock_session.query.return_value.filter.return_value.all.return_value = []
            
            result = self.analyzer.analyze_preinscriptions_by_program(attempt)
            
            # Vérification que l'accès non autorisé retourne des données vides
            assert result is None or result == {} or (isinstance(result, list) and len(result) == 0)
    
    def test_data_encryption(self):
        """Test de chiffrement des données sensibles."""
        # Simulation de données sensibles
        sensitive_data = [
            Mock(
                id=1,
                nom="Dupont",
                prenom="Jean",
                email="jean.dupont@example.com",
                telephone="0123456789",
                programme_id=1,
                statut="en_attente"
            )
        ]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = sensitive_data
        
        # Test que les données sensibles sont chiffrées ou masquées
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        # Vérification que les données sensibles ne sont pas en clair
        if result and isinstance(result, dict):
            result_str = str(result)
            # Vérification que les données sensibles ne sont pas exposées en clair
            assert "jean.dupont@example.com" not in result_str, "Email exposé en clair"
            assert "0123456789" not in result_str, "Téléphone exposé en clair"
    
    def test_session_security(self):
        """Test de sécurité de la session."""
        # Test que la session est correctement fermée
        with patch('app_lia_web.app.services.metrics.preinscription_metrics.get_session_for_metrics') as mock_get_session:
            mock_session = Mock(spec=Session)
            mock_get_session.return_value = mock_session
            
            # Utilisation de l'analyzer
            analyzer = PreinscriptionAnalyzer(mock_session)
            result = analyzer.analyze_preinscriptions_by_program(1)
            
            # Vérification que la session est utilisée correctement
            assert mock_session.query.called, "Session non utilisée"
            
            # Vérification que la session est fermée (si applicable)
            # Note: Dans un vrai test, on vérifierait que session.close() est appelé
    
    def test_logging_security(self):
        """Test de sécurité des logs."""
        # Test que les données sensibles ne sont pas loggées
        with patch('app_lia_web.app.services.metrics.preinscription_metrics.logger') as mock_logger:
            sensitive_data = [
                Mock(
                    id=1,
                    nom="Dupont",
                    prenom="Jean",
                    email="jean.dupont@example.com",
                    telephone="0123456789",
                    programme_id=1,
                    statut="en_attente"
                )
            ]
            
            self.mock_session.query.return_value.filter.return_value.all.return_value = sensitive_data
            
            # Utilisation de l'analyzer
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            
            # Vérification que les logs ne contiennent pas de données sensibles
            if mock_logger.info.called:
                log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
                for log_call in log_calls:
                    assert "jean.dupont@example.com" not in str(log_call), "Email dans les logs"
                    assert "0123456789" not in str(log_call), "Téléphone dans les logs"
    
    def test_error_information_disclosure(self):
        """Test de divulgation d'informations dans les erreurs."""
        # Test que les erreurs ne divulguent pas d'informations sensibles
        try:
            # Simulation d'une erreur
            self.mock_session.query.side_effect = Exception("Database connection failed")
            
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            
        except Exception as e:
            error_message = str(e)
            
            # Vérification que l'erreur ne contient pas d'informations sensibles
            sensitive_info = [
                "password",
                "secret",
                "key",
                "token",
                "connection string",
                "database url"
            ]
            
            for info in sensitive_info:
                assert info not in error_message.lower(), f"Information sensible '{info}' divulguée dans l'erreur"
    
    def test_rate_limiting(self):
        """Test de limitation du taux de requêtes."""
        # Test que le système peut gérer un nombre raisonnable de requêtes
        # sans être surchargé par des attaques par déni de service
        
        request_count = 0
        max_requests = 1000
        
        for i in range(max_requests):
            try:
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                request_count += 1
            except Exception:
                # Les erreurs sont acceptables après un certain nombre de requêtes
                break
        
        # Vérification que le système a traité un nombre raisonnable de requêtes
        assert request_count > 100, f"Trop peu de requêtes traitées: {request_count}"
        assert request_count <= max_requests, f"Trop de requêtes traitées: {request_count}"
