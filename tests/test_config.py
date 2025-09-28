"""
Tests de configuration et d'environnement
"""
import pytest
import os
import sys
from pathlib import Path


class TestEnvironment:
    """Tests pour vérifier la configuration de l'environnement."""
    
    def test_python_version(self):
        """Test de la version de Python."""
        assert sys.version_info >= (3, 8), "Python 3.8+ requis"
    
    def test_project_structure(self):
        """Test de la structure du projet."""
        project_root = Path(__file__).parent.parent
        
        # Vérifier les dossiers essentiels
        assert (project_root / "app").exists(), "Dossier app manquant"
        assert (project_root / "core").exists(), "Dossier core manquant"
        assert (project_root / "tests").exists(), "Dossier tests manquant"
        
        # Vérifier les fichiers essentiels
        assert (project_root / "main.py").exists(), "Fichier main.py manquant"
        assert (project_root / "pytest.ini").exists(), "Fichier pytest.ini manquant"
    
    def test_imports(self):
        """Test des imports essentiels."""
        try:
            from app_lia_web.app.models.base import User, Programme
            from app_lia_web.app.services.metrics import SchemaDiscovery
            from app_lia_web.core.database import get_session
        except ImportError as e:
            pytest.fail(f"Import échoué: {e}")
    
    def test_database_config(self):
        """Test de la configuration de la base de données."""
        # Vérifier que les variables d'environnement sont définies
        # ou que la configuration par défaut fonctionne
        try:
            from app_lia_web.core.database import get_session
            # Ne pas exécuter, juste vérifier que l'import fonctionne
            assert get_session is not None
        except Exception as e:
            pytest.fail(f"Configuration DB échouée: {e}")


class TestDependencies:
    """Tests pour vérifier les dépendances."""
    
    def test_sqlmodel_available(self):
        """Test de la disponibilité de SQLModel."""
        try:
            import sqlmodel
            assert hasattr(sqlmodel, 'SQLModel')
            assert hasattr(sqlmodel, 'Session')
        except ImportError:
            pytest.fail("SQLModel non disponible")
    
    def test_fastapi_available(self):
        """Test de la disponibilité de FastAPI."""
        try:
            import fastapi
            assert hasattr(fastapi, 'FastAPI')
        except ImportError:
            pytest.fail("FastAPI non disponible")
    
    def test_pytest_available(self):
        """Test de la disponibilité de pytest."""
        try:
            import pytest
            assert hasattr(pytest, 'fixture')
        except ImportError:
            pytest.fail("pytest non disponible")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
