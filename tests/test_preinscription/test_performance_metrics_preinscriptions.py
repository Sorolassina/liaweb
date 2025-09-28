"""
Tests de performance pour les métriques de préinscription.

Ces tests vérifient les performances des fonctions de métriques
avec de gros volumes de données et des requêtes complexes.
"""

import pytest
import time
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app_lia_web.app.services.metrics.preinscription_metrics import (
    PreinscriptionAnalyzer,
    PreinscriptionMetricsService,
    SchemaDiscovery
)


@pytest.mark.performance
class TestPreinscriptionPerformance:
    """Tests de performance pour les métriques de préinscription."""
    
    def setup_method(self):
        """Configuration pour chaque test."""
        self.mock_session = Mock(spec=Session)
        self.analyzer = PreinscriptionAnalyzer(self.mock_session)
        self.metrics_service = PreinscriptionMetricsService(self.mock_session)
        self.schema_discovery = SchemaDiscovery(self.mock_session)
    
    def test_large_dataset_performance(self):
        """Test de performance avec un grand volume de données."""
        # Simulation d'un grand nombre de préinscriptions
        large_dataset = [
            Mock(
                id=i,
                nom=f"Candidat{i}",
                prenom=f"Prenom{i}",
                email=f"candidat{i}@example.com",
                programme_id=1,
                statut="en_attente",
                date_creation=f"2024-01-{(i % 28) + 1:02d}"
            )
            for i in range(10000)  # 10k enregistrements
        ]
        
        # Mock de la requête
        self.mock_session.query.return_value.filter.return_value.all.return_value = large_dataset
        
        # Mesure du temps d'exécution
        start_time = time.time()
        
        # Test de la fonction d'analyse
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Vérification que l'exécution est raisonnable (< 5 secondes)
        assert execution_time < 5.0, f"Trop lent: {execution_time:.2f}s"
        assert result is not None
    
    def test_query_optimization(self):
        """Test d'optimisation des requêtes."""
        # Simulation de données avec différents statuts
        test_data = [
            Mock(statut="en_attente", programme_id=1),
            Mock(statut="accepte", programme_id=1),
            Mock(statut="refuse", programme_id=1),
            Mock(statut="en_attente", programme_id=2),
        ]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
        
        # Test de performance avec filtres multiples
        start_time = time.time()
        
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Vérification de l'optimisation
        assert execution_time < 1.0, f"Requête non optimisée: {execution_time:.2f}s"
        assert result is not None
    
    def test_schema_discovery_performance(self):
        """Test de performance de la découverte de schémas."""
        # Simulation de nombreux schémas
        mock_schemas = [f"programme_{i}" for i in range(100)]
        
        with patch('app_lia_web.app.services.metrics.preinscription_metrics.inspect') as mock_inspect:
            mock_inspect.get_schema_names.return_value = mock_schemas
            
            start_time = time.time()
            
            result = self.schema_discovery.get_all_program_schemas()
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Vérification de la performance
            assert execution_time < 2.0, f"Découverte de schémas trop lente: {execution_time:.2f}s"
            assert len(result) == 100
    
    def test_metrics_calculation_performance(self):
        """Test de performance du calcul des métriques."""
        # Simulation de données complexes
        complex_data = [
            Mock(
                statut="en_attente",
                programme_id=1,
                date_creation="2024-01-01",
                source="web"
            )
            for _ in range(5000)
        ]
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = complex_data
        
        start_time = time.time()
        
        # Test du service de métriques
        result = self.metrics_service.get_preinscription_metrics(1)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Vérification de la performance
        assert execution_time < 3.0, f"Calcul des métriques trop lent: {execution_time:.2f}s"
        assert result is not None
    
    def test_memory_usage(self):
        """Test d'utilisation mémoire."""
        import psutil
        import os
        
        # Mesure de la mémoire avant
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Simulation de traitement de données
        large_dataset = [Mock(id=i, statut="en_attente") for i in range(10000)]
        self.mock_session.query.return_value.filter.return_value.all.return_value = large_dataset
        
        # Traitement
        result = self.analyzer.analyze_preinscriptions_by_program(1)
        
        # Mesure de la mémoire après
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Vérification de l'utilisation mémoire
        assert memory_increase < 100, f"Trop de mémoire utilisée: {memory_increase:.2f}MB"
        assert result is not None
    
    def test_concurrent_analysis_performance(self):
        """Test de performance avec analyses concurrentes."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def analyze_program(program_id):
            """Fonction d'analyse pour un programme."""
            test_data = [Mock(statut="en_attente", programme_id=program_id) for _ in range(1000)]
            self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
            
            start_time = time.time()
            result = self.analyzer.analyze_preinscriptions_by_program(program_id)
            end_time = time.time()
            
            results.put((program_id, end_time - start_time, result))
        
        # Lancement de plusieurs analyses en parallèle
        threads = []
        for i in range(5):  # 5 analyses concurrentes
            thread = threading.Thread(target=analyze_program, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Attente de la fin de tous les threads
        for thread in threads:
            thread.join()
        
        # Vérification des résultats
        total_time = 0
        while not results.empty():
            program_id, exec_time, result = results.get()
            total_time += exec_time
            assert result is not None
        
        # Vérification que le temps total est raisonnable
        assert total_time < 10.0, f"Analyses concurrentes trop lentes: {total_time:.2f}s"
