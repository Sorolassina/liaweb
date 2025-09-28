"""
Tests de charge pour les métriques de préinscription.

Ces tests vérifient le comportement du système sous charge
avec de nombreuses requêtes simultanées.
"""

import pytest
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app_lia_web.app.services.metrics.preinscription_metrics import (
    PreinscriptionAnalyzer,
    PreinscriptionMetricsService,
    SchemaDiscovery
)


@pytest.mark.load
class TestPreinscriptionLoad:
    """Tests de charge pour les métriques de préinscription."""
    
    def setup_method(self):
        """Configuration pour chaque test."""
        self.mock_session = Mock(spec=Session)
        self.analyzer = PreinscriptionAnalyzer(self.mock_session)
        self.metrics_service = PreinscriptionMetricsService(self.mock_session)
        self.schema_discovery = SchemaDiscovery(self.mock_session)
    
    def test_concurrent_requests(self):
        """Test de requêtes simultanées."""
        # Simulation de données
        test_data = [Mock(statut="en_attente", programme_id=1) for _ in range(1000)]
        self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def make_request(request_id):
            """Fait une requête d'analyse."""
            try:
                start_time = time.time()
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                end_time = time.time()
                
                results.put({
                    'request_id': request_id,
                    'execution_time': end_time - start_time,
                    'success': True,
                    'result': result
                })
            except Exception as e:
                errors.put({
                    'request_id': request_id,
                    'error': str(e),
                    'success': False
                })
        
        # Lancement de 50 requêtes simultanées
        threads = []
        for i in range(50):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Attente de la fin de tous les threads
        for thread in threads:
            thread.join(timeout=30)  # Timeout de 30 secondes
        
        # Vérification des résultats
        successful_requests = 0
        total_time = 0
        
        while not results.empty():
            result = results.get()
            successful_requests += 1
            total_time += result['execution_time']
            assert result['success'] is True
            assert result['result'] is not None
        
        # Vérification qu'il n'y a pas d'erreurs
        assert errors.empty(), f"Erreurs détectées: {[errors.get() for _ in range(errors.qsize())]}"
        
        # Vérification du taux de succès
        assert successful_requests == 50, f"Seulement {successful_requests}/50 requêtes réussies"
        
        # Vérification du temps moyen
        avg_time = total_time / successful_requests
        assert avg_time < 2.0, f"Temps moyen trop élevé: {avg_time:.2f}s"
    
    def test_high_volume_requests(self):
        """Test avec un volume élevé de requêtes."""
        # Simulation de données
        test_data = [Mock(statut="en_attente", programme_id=1) for _ in range(5000)]
        self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
        
        def make_request(request_id):
            """Fait une requête d'analyse."""
            start_time = time.time()
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            end_time = time.time()
            
            return {
                'request_id': request_id,
                'execution_time': end_time - start_time,
                'success': True,
                'result': result
            }
        
        # Utilisation de ThreadPoolExecutor pour gérer les threads
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Soumission de 200 requêtes
            futures = [executor.submit(make_request, i) for i in range(200)]
            
            results = []
            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    pytest.fail(f"Erreur dans une requête: {e}")
        
        # Vérification des résultats
        assert len(results) == 200, f"Seulement {len(results)}/200 requêtes terminées"
        
        # Calcul des statistiques
        execution_times = [r['execution_time'] for r in results]
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        min_time = min(execution_times)
        
        # Vérifications de performance
        assert avg_time < 3.0, f"Temps moyen trop élevé: {avg_time:.2f}s"
        assert max_time < 10.0, f"Temps maximum trop élevé: {max_time:.2f}s"
        assert min_time > 0, "Temps minimum invalide"
        
        # Vérification que toutes les requêtes ont réussi
        for result in results:
            assert result['success'] is True
            assert result['result'] is not None
    
    def test_database_connection_pool(self):
        """Test du pool de connexions à la base de données."""
        # Simulation de connexions multiples
        mock_connections = [Mock() for _ in range(10)]
        
        with patch('app_lia_web.app.services.metrics.preinscription_metrics.get_session_for_metrics') as mock_get_session:
            mock_get_session.side_effect = mock_connections
            
            def use_connection(connection_id):
                """Utilise une connexion."""
                session = mock_get_session()
                analyzer = PreinscriptionAnalyzer(session)
                
                # Simulation de données
                test_data = [Mock(statut="en_attente", programme_id=1) for _ in range(100)]
                session.query.return_value.filter.return_value.all.return_value = test_data
                
                result = analyzer.analyze_preinscriptions_by_program(1)
                return result
            
            # Utilisation concurrente de connexions
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(use_connection, i) for i in range(10)]
                
                results = []
                for future in as_completed(futures, timeout=30):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        pytest.fail(f"Erreur de connexion: {e}")
            
            # Vérification que toutes les connexions ont été utilisées
            assert len(results) == 10, f"Seulement {len(results)}/10 connexions utilisées"
            
            # Vérification que get_session a été appelé 10 fois
            assert mock_get_session.call_count == 10
    
    def test_memory_under_load(self):
        """Test de l'utilisation mémoire sous charge."""
        import psutil
        import os
        
        # Mesure de la mémoire initiale
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        def memory_intensive_request(request_id):
            """Requête intensive en mémoire."""
            # Simulation de données volumineuses
            large_dataset = [Mock(statut="en_attente", programme_id=1) for _ in range(2000)]
            self.mock_session.query.return_value.filter.return_value.all.return_value = large_dataset
            
            result = self.analyzer.analyze_preinscriptions_by_program(1)
            return result
        
        # Lancement de requêtes intensives
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(memory_intensive_request, i) for i in range(15)]
            
            results = []
            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    pytest.fail(f"Erreur de mémoire: {e}")
        
        # Mesure de la mémoire finale
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Vérification de l'utilisation mémoire
        assert memory_increase < 200, f"Trop de mémoire utilisée: {memory_increase:.2f}MB"
        assert len(results) == 15, f"Seulement {len(results)}/15 requêtes terminées"
    
    def test_error_handling_under_load(self):
        """Test de gestion d'erreurs sous charge."""
        # Simulation d'erreurs aléatoires
        error_count = 0
        success_count = 0
        
        def request_with_random_error(request_id):
            """Requête avec erreur aléatoire."""
            nonlocal error_count, success_count
            
            # Simulation d'erreur pour 10% des requêtes
            if request_id % 10 == 0:
                error_count += 1
                raise Exception(f"Erreur simulée pour la requête {request_id}")
            else:
                success_count += 1
                test_data = [Mock(statut="en_attente", programme_id=1) for _ in range(100)]
                self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
                return self.analyzer.analyze_preinscriptions_by_program(1)
        
        # Lancement de requêtes avec erreurs
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(request_with_random_error, i) for i in range(100)]
            
            results = []
            errors = []
            
            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))
        
        # Vérification de la gestion d'erreurs
        assert len(errors) == 10, f"Attendu 10 erreurs, obtenu {len(errors)}"
        assert len(results) == 90, f"Attendu 90 succès, obtenu {len(results)}"
        
        # Vérification que les erreurs sont bien gérées
        for error in errors:
            assert "Erreur simulée" in error
    
    def test_throughput_measurement(self):
        """Test de mesure du débit."""
        # Simulation de données
        test_data = [Mock(statut="en_attente", programme_id=1) for _ in range(1000)]
        self.mock_session.query.return_value.filter.return_value.all.return_value = test_data
        
        def measure_throughput():
            """Mesure le débit de traitement."""
            start_time = time.time()
            
            # Traitement de 100 requêtes
            for i in range(100):
                result = self.analyzer.analyze_preinscriptions_by_program(1)
                assert result is not None
            
            end_time = time.time()
            total_time = end_time - start_time
            
            return {
                'total_requests': 100,
                'total_time': total_time,
                'throughput': 100 / total_time  # requêtes par seconde
            }
        
        # Mesure du débit
        result = measure_throughput()
        
        # Vérification du débit minimum
        assert result['throughput'] > 10, f"Débit trop faible: {result['throughput']:.2f} req/s"
        assert result['total_time'] < 10, f"Temps total trop élevé: {result['total_time']:.2f}s"
