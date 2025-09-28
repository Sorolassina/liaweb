"""
Tests unitaires pour les composants communs du module de métriques
Ces tests couvrent les classes et fonctions partagées entre tous les modules de métriques
"""
import pytest
from unittest.mock import Mock, patch
from app_lia_web.app.services.metrics import SchemaDiscovery, get_program_schemas


class TestSchemaDiscovery:
    """Tests pour la classe SchemaDiscovery - composant commun à tous les modules de métriques."""
    
    def test_init(self, mock_session):
        """Test de l'initialisation de SchemaDiscovery."""
        discovery = SchemaDiscovery(mock_session)
        assert discovery.session == mock_session
    
    def test_get_all_program_schemas(self, mock_session):
        """Test de la récupération des schémas de programmes."""
        discovery = SchemaDiscovery(mock_session)
        schemas = discovery.get_all_program_schemas()
        
        assert isinstance(schemas, list)
        assert len(schemas) == 3
        assert "acd" in schemas
        assert "aci" in schemas
        assert "act" in schemas
    
    def test_schema_has_table(self, mock_session):
        """Test de la vérification d'existence d'une table."""
        discovery = SchemaDiscovery(mock_session)
        
        # Test avec un schéma qui a la table preinscription
        assert discovery.schema_has_table("acd", "preinscription") is True
        assert discovery.schema_has_table("aci", "preinscription") is True
        
        # Test avec un schéma qui n'a pas la table
        assert discovery.schema_has_table("act", "preinscription") is False
    
    def test_get_schema_tables(self, mock_session):
        """Test de la récupération des tables d'un schéma."""
        discovery = SchemaDiscovery(mock_session)
        
        # Mock pour get_schema_tables
        mock_session.mock_results["get_schema_tables"] = [["candidat"], ["preinscription"], ["inscription"]]
        
        tables = discovery.get_schema_tables("acd")
        assert isinstance(tables, list)
    
    def test_get_all_program_schemas_error_handling(self):
        """Test de la gestion d'erreur dans get_all_program_schemas."""
        mock_session = Mock()
        mock_session.execute.side_effect = Exception("Database error")
        
        discovery = SchemaDiscovery(mock_session)
        schemas = discovery.get_all_program_schemas()
        
        assert schemas == []
    
    def test_schema_has_table_error_handling(self):
        """Test de la gestion d'erreur dans schema_has_table."""
        mock_session = Mock()
        mock_session.execute.side_effect = Exception("Database error")
        
        discovery = SchemaDiscovery(mock_session)
        result = discovery.schema_has_table("test", "table")
        
        assert result is False


class TestGetProgramSchemas:
    """Tests pour la fonction utilitaire get_program_schemas - composant commun."""
    
    @patch('app_lia_web.app.services.metrics.get_session')
    def test_get_program_schemas(self, mock_get_session, mock_session):
        """Test de la fonction get_program_schemas."""
        mock_get_session.return_value.__next__.return_value = mock_session
        
        discovery = get_program_schemas()
        assert isinstance(discovery, SchemaDiscovery)
        assert discovery.session == mock_session


# Tests d'intégration pour les composants communs
@pytest.mark.integration
@pytest.mark.database
class TestCommonMetricsIntegration:
    """Tests d'intégration pour les composants communs avec une vraie base de données."""
    
    def test_schema_discovery_with_real_db(self, test_session):
        """Test de SchemaDiscovery avec une vraie base de données."""
        discovery = SchemaDiscovery(test_session)
        schemas = discovery.get_all_program_schemas()
        
        # Avec une vraie DB, on devrait avoir au moins le schéma public
        assert isinstance(schemas, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
