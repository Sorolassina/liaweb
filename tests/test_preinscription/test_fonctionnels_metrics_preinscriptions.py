"""
Tests fonctionnels pour le module de métriques des préinscriptions
Ces tests vérifient le comportement end-to-end avec une vraie base de données
"""
import pytest
from app_lia_web.app.services.metrics.preinscription_metrics import (
    PreinscriptionAnalyzer,
    PreinscriptionMetricsService
)


@pytest.mark.integration
@pytest.mark.database
class TestPreinscriptionMetricsFunctional:
    """Tests fonctionnels pour les métriques de préinscription avec une vraie base de données."""
    
    def test_preinscription_analyzer_with_real_db(self, test_session):
        """Test de PreinscriptionAnalyzer avec une vraie base de données."""
        analyzer = PreinscriptionAnalyzer(test_session, "public")
        
        # Ces tests dépendent de la structure de la vraie DB
        has_table = analyzer.has_preinscription_table()
        assert isinstance(has_table, bool)
        
        # Test des métriques si la table existe
        if has_table:
            total_count = analyzer.get_total_count()
            assert isinstance(total_count, int)
            assert total_count >= 0
            
            status_counts = analyzer.get_count_by_status()
            assert isinstance(status_counts, dict)
            
            recent_count = analyzer.get_recent_count(30)
            assert isinstance(recent_count, int)
            assert recent_count >= 0
            
            monthly_trend = analyzer.get_monthly_trend(12)
            assert isinstance(monthly_trend, list)
            
            details = analyzer.get_detailed_preinscriptions(limit=5)
            assert isinstance(details, list)
            
            all_metrics = analyzer.get_all_metrics()
            assert isinstance(all_metrics, dict)
            assert "schema_name" in all_metrics
            assert all_metrics["schema_name"] == "public"
        else:
            # Si pas de table, vérifier que les méthodes retournent des valeurs par défaut
            assert analyzer.get_total_count() == 0
            assert analyzer.get_count_by_status() == {}
            assert analyzer.get_recent_count(30) == 0
            assert analyzer.get_monthly_trend(12) == []
            assert analyzer.get_detailed_preinscriptions(limit=5) == []
            
            metrics = analyzer.get_all_metrics()
            assert "error" in metrics
            assert metrics["error"] == "Table preinscription non trouvée"
    
    def test_preinscription_metrics_service_with_real_db(self, test_session):
        """Test de PreinscriptionMetricsService avec une vraie base de données."""
        service = PreinscriptionMetricsService(test_session)
        
        # Test des métriques globales
        metrics = service.get_global_metrics()
        assert isinstance(metrics, dict)
        assert "total_schemas" in metrics
        assert "schemas_with_preinscription" in metrics
        assert "total_preinscriptions" in metrics
        assert "status_distribution" in metrics
        assert "by_schema" in metrics
        
        # Vérifier que les valeurs sont cohérentes
        assert isinstance(metrics["total_schemas"], int)
        assert metrics["total_schemas"] >= 0
        assert isinstance(metrics["schemas_with_preinscription"], int)
        assert metrics["schemas_with_preinscription"] >= 0
        assert metrics["schemas_with_preinscription"] <= metrics["total_schemas"]
        assert isinstance(metrics["total_preinscriptions"], int)
        assert metrics["total_preinscriptions"] >= 0
        assert isinstance(metrics["status_distribution"], dict)
        assert isinstance(metrics["by_schema"], dict)
        
        # Vérifier que chaque schéma a des données cohérentes
        for schema_name, schema_data in metrics["by_schema"].items():
            assert isinstance(schema_name, str)
            assert isinstance(schema_data, dict)
            
            if "error" not in schema_data:
                assert "total" in schema_data
                assert "status_distribution" in schema_data
                assert "recent_30_days" in schema_data
                assert "monthly_trend" in schema_data
                assert "schema_name" in schema_data
                assert schema_data["schema_name"] == schema_name
    
    def test_get_schema_details_with_real_db(self, test_session):
        """Test de get_schema_details avec une vraie base de données."""
        service = PreinscriptionMetricsService(test_session)
        
        # Test avec le schéma public
        details = service.get_schema_details("public", limit=5)
        assert isinstance(details, dict)
        assert "schema_name" in details
        assert details["schema_name"] == "public"
        
        # Si la table existe, on devrait avoir des préinscriptions ou une erreur
        if "error" not in details:
            assert "preinscriptions" in details
            assert "count" in details
            assert isinstance(details["preinscriptions"], list)
            assert isinstance(details["count"], int)
            assert details["count"] == len(details["preinscriptions"])
            assert details["count"] <= 5  # limit=5
            
            # Vérifier la structure des préinscriptions
            for preinscription in details["preinscriptions"]:
                assert isinstance(preinscription, dict)
                assert "id" in preinscription
                assert "date_preinscription" in preinscription
                assert "statut" in preinscription
                assert "motivation" in preinscription
                assert "candidat" in preinscription
                assert isinstance(preinscription["candidat"], dict)
                assert "nom" in preinscription["candidat"]
                assert "prenom" in preinscription["candidat"]
                assert "email" in preinscription["candidat"]
                assert "telephone" in preinscription["candidat"]
        else:
            assert details["error"] == "Table preinscription non trouvée"
    
    def test_direct_class_usage_with_real_db(self, test_session):
        """Test de l'utilisation directe des classes avec une vraie base de données."""
        # Test direct de SchemaDiscovery
        from app_lia_web.app.services.metrics import SchemaDiscovery
        discovery = SchemaDiscovery(test_session)
        schemas = discovery.get_all_program_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) >= 0
        
        # Test direct de PreinscriptionMetricsService
        service = PreinscriptionMetricsService(test_session)
        metrics = service.get_global_metrics()
        assert isinstance(metrics, dict)
        assert "total_schemas" in metrics
        assert "schemas_with_preinscription" in metrics
        assert "total_preinscriptions" in metrics
        assert "status_distribution" in metrics
        assert "by_schema" in metrics
    
    def test_print_summary_with_real_db(self, test_session, capsys):
        """Test de l'affichage du résumé avec une vraie base de données."""
        service = PreinscriptionMetricsService(test_session)
        service.print_summary()
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Vérifier que le résumé contient les sections attendues
        assert "RÉSUMÉ DES PRÉINSCRIPTIONS PAR SCHÉMA" in output
        assert "STATISTIQUES GLOBALES" in output
        assert "DÉTAIL PAR SCHÉMA" in output
        
        # Vérifier que les statistiques sont affichées
        assert "Total schémas analysés:" in output
        assert "Schémas avec table preinscription:" in output
        assert "Total préinscriptions:" in output
    
    def test_error_handling_with_real_db(self, test_session):
        """Test de la gestion d'erreurs avec une vraie base de données."""
        # Test avec un schéma inexistant
        analyzer = PreinscriptionAnalyzer(test_session, "inexistant")
        
        # Toutes les méthodes doivent gérer gracieusement l'absence de schéma
        assert analyzer.has_preinscription_table() is False
        assert analyzer.get_total_count() == 0
        assert analyzer.get_count_by_status() == {}
        assert analyzer.get_recent_count(30) == 0
        assert analyzer.get_monthly_trend(12) == []
        assert analyzer.get_detailed_preinscriptions(limit=5) == []
        
        metrics = analyzer.get_all_metrics()
        assert "error" in metrics
        assert metrics["error"] == "Table preinscription non trouvée"
        
        # Test du service avec un schéma inexistant
        service = PreinscriptionMetricsService(test_session)
        details = service.get_schema_details("inexistant", limit=5)
        assert "error" in details
        assert details["error"] == "Table preinscription non trouvée"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
