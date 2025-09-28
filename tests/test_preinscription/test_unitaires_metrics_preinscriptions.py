"""
Tests unitaires pour le module de métriques des préinscriptions
Ces tests couvrent uniquement les classes et fonctions spécifiques aux préinscriptions
"""
import pytest
from unittest.mock import Mock, patch
from app_lia_web.app.services.metrics.preinscription_metrics import (
    PreinscriptionAnalyzer,
    PreinscriptionMetricsService
)


class TestPreinscriptionAnalyzer:
    """Tests pour la classe PreinscriptionAnalyzer - analyse des préinscriptions dans un schéma."""
    
    def test_init(self, mock_session):
        """Test de l'initialisation de PreinscriptionAnalyzer."""
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        assert analyzer.session == mock_session
        assert analyzer.schema_name == "acd"
        assert analyzer.discovery is not None
    
    def test_has_preinscription_table(self, mock_session):
        """Test de la vérification de la table preinscription."""
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        assert analyzer.has_preinscription_table() is True
        
        analyzer_act = PreinscriptionAnalyzer(mock_session, "act")
        assert analyzer_act.has_preinscription_table() is False
    
    def test_get_total_count(self, mock_session):
        """Test du comptage total des préinscriptions."""
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        count = analyzer.get_total_count()
        assert count == 5
    
    def test_get_total_count_no_table(self, mock_session):
        """Test du comptage quand la table n'existe pas."""
        analyzer = PreinscriptionAnalyzer(mock_session, "act")  # act n'a pas la table
        count = analyzer.get_total_count()
        assert count == 0
    
    def test_get_count_by_status(self, mock_session):
        """Test du comptage par statut."""
        # Mock pour get_count_by_status
        mock_session.mock_results["count_by_status"] = [
            ["en_attente", 3],
            ["accepte", 2]
        ]
        
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        status_counts = analyzer.get_count_by_status()
        
        assert isinstance(status_counts, dict)
    
    def test_get_count_by_status_no_table(self, mock_session):
        """Test du comptage par statut quand la table n'existe pas."""
        analyzer = PreinscriptionAnalyzer(mock_session, "act")
        status_counts = analyzer.get_count_by_status()
        
        assert isinstance(status_counts, dict)
        assert status_counts == {}
    
    def test_get_recent_count(self, mock_session):
        """Test du comptage des préinscriptions récentes."""
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        recent_count = analyzer.get_recent_count(30)
        assert isinstance(recent_count, int)
    
    def test_get_recent_count_no_table(self, mock_session):
        """Test du comptage des préinscriptions récentes quand la table n'existe pas."""
        analyzer = PreinscriptionAnalyzer(mock_session, "act")
        recent_count = analyzer.get_recent_count(30)
        assert recent_count == 0
    
    def test_get_monthly_trend(self, mock_session):
        """Test de la tendance mensuelle."""
        # Mock pour get_monthly_trend
        from datetime import datetime
        mock_session.mock_results["monthly_trend"] = [
            [datetime(2024, 1, 1), 2],
            [datetime(2024, 2, 1), 3]
        ]
        
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        trend = analyzer.get_monthly_trend(12)
        
        assert isinstance(trend, list)
    
    def test_get_monthly_trend_no_table(self, mock_session):
        """Test de la tendance mensuelle quand la table n'existe pas."""
        analyzer = PreinscriptionAnalyzer(mock_session, "act")
        trend = analyzer.get_monthly_trend(12)
        
        assert isinstance(trend, list)
        assert trend == []
    
    def test_get_detailed_preinscriptions(self, mock_session):
        """Test de la récupération des détails des préinscriptions."""
        # Mock pour get_detailed_preinscriptions
        mock_session.mock_results["detailed_preinscriptions"] = [
            [1, "2024-01-01", "en_attente", "Motivation test", "Doe", "John", "john@test.com", "123456789"]
        ]
        
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        details = analyzer.get_detailed_preinscriptions(limit=5)
        
        assert isinstance(details, list)
        if details:
            detail = details[0]
            assert "id" in detail
            assert "date_preinscription" in detail
            assert "statut" in detail
            assert "motivation" in detail
            assert "candidat" in detail
    
    def test_get_detailed_preinscriptions_no_table(self, mock_session):
        """Test de la récupération des détails quand la table n'existe pas."""
        analyzer = PreinscriptionAnalyzer(mock_session, "act")
        details = analyzer.get_detailed_preinscriptions(limit=5)
        
        assert isinstance(details, list)
        assert details == []
    
    def test_get_all_metrics(self, mock_session):
        """Test de la récupération de toutes les métriques."""
        analyzer = PreinscriptionAnalyzer(mock_session, "acd")
        metrics = analyzer.get_all_metrics()
        
        assert isinstance(metrics, dict)
        assert "total" in metrics
        assert "status_distribution" in metrics
        assert "recent_30_days" in metrics
        assert "monthly_trend" in metrics
        assert "schema_name" in metrics
        assert metrics["schema_name"] == "acd"
    
    def test_get_all_metrics_no_table(self, mock_session):
        """Test des métriques quand la table n'existe pas."""
        analyzer = PreinscriptionAnalyzer(mock_session, "act")
        metrics = analyzer.get_all_metrics()
        
        assert "error" in metrics
        assert metrics["error"] == "Table preinscription non trouvée"


class TestPreinscriptionMetricsService:
    """Tests pour la classe PreinscriptionMetricsService - service principal des préinscriptions."""
    
    def test_init(self, mock_session):
        """Test de l'initialisation du service."""
        service = PreinscriptionMetricsService(mock_session)
        assert service.session == mock_session
        assert service.discovery is not None
    
    def test_get_global_metrics(self, mock_session):
        """Test de la récupération des métriques globales."""
        service = PreinscriptionMetricsService(mock_session)
        metrics = service.get_global_metrics()
        
        assert isinstance(metrics, dict)
        assert "total_schemas" in metrics
        assert "schemas_with_preinscription" in metrics
        assert "total_preinscriptions" in metrics
        assert "status_distribution" in metrics
        assert "by_schema" in metrics
        
        assert metrics["total_schemas"] == 3
        assert metrics["schemas_with_preinscription"] == 2  # acd et aci ont la table
    
    def test_get_schema_metrics(self, mock_session):
        """Test de la récupération des métriques pour un schéma spécifique."""
        service = PreinscriptionMetricsService(mock_session)
        metrics = service.get_schema_metrics("acd")
        
        assert isinstance(metrics, dict)
        assert "schema_name" in metrics
        assert metrics["schema_name"] == "acd"
    
    def test_get_schema_details(self, mock_session):
        """Test de la récupération des détails pour un schéma."""
        # Mock pour get_detailed_preinscriptions
        mock_session.mock_results["detailed_preinscriptions"] = [
            [1, "2024-01-01", "en_attente", "Motivation test", "Doe", "John", "john@test.com", "123456789"]
        ]
        
        service = PreinscriptionMetricsService(mock_session)
        details = service.get_schema_details("acd", limit=5)
        
        assert isinstance(details, dict)
        assert "schema_name" in details
        assert "preinscriptions" in details
        assert "count" in details
        assert details["schema_name"] == "acd"
    
    def test_get_schema_details_no_table(self, mock_session):
        """Test de la récupération des détails pour un schéma sans table preinscription."""
        service = PreinscriptionMetricsService(mock_session)
        details = service.get_schema_details("act", limit=5)  # act n'a pas la table
        
        assert isinstance(details, dict)
        assert "error" in details
        assert details["error"] == "Table preinscription non trouvée"
    
    def test_print_summary(self, mock_session, capsys):
        """Test de l'affichage du résumé."""
        service = PreinscriptionMetricsService(mock_session)
        service.print_summary()
        
        captured = capsys.readouterr()
        assert "RÉSUMÉ DES PRÉINSCRIPTIONS PAR SCHÉMA" in captured.out
        assert "STATISTIQUES GLOBALES" in captured.out
        assert "DÉTAIL PAR SCHÉMA" in captured.out


class TestPreinscriptionMetricsTest:
    """Tests pour la classe de test des préinscriptions."""
    
    @patch('app_lia_web.app.services.metrics.preinscription_metrics.get_session')
    def test_run_test(self, mock_get_session, mock_session):
        """Test de l'exécution des tests."""
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        # Le test ne devrait pas lever d'exception
        from app_lia_web.app.services.metrics.preinscription_metrics import PreinscriptionMetricsTest
        PreinscriptionMetricsTest.run_test()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
