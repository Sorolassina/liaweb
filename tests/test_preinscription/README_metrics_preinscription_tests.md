# Tests de Métriques - Préinscriptions

## Vue d'ensemble

Ce document décrit l'organisation des tests pour le module de métriques des préinscriptions. Ce module est le premier à être implémenté et sert de modèle pour les modules futurs.

**Note :** Ce document concerne uniquement les tests des préinscriptions. Les tests des composants communs sont documentés dans `README_common_tests.md`.

## Structure des Fichiers de Test

### 1. **`test_unitaires_metrics_preinscriptions.py`**
**Tests unitaires pour les préinscriptions**

- **`TestPreinscriptionAnalyzer`** : Tests de l'analyseur de préinscriptions
  - `has_preinscription_table()` : Vérification de la table
  - `get_total_count()` : Comptage total
  - `get_count_by_status()` : Comptage par statut
  - `get_recent_count()` : Comptage récent
  - `get_monthly_trend()` : Tendance mensuelle
  - `get_detailed_preinscriptions()` : Détails des préinscriptions
  - `get_all_metrics()` : Toutes les métriques
  - Cas avec/sans table

- **`TestPreinscriptionMetricsService`** : Tests du service principal
  - `get_global_metrics()` : Métriques globales
  - `get_schema_metrics()` : Métriques par schéma
  - `get_schema_details()` : Détails par schéma
  - `print_summary()` : Affichage du résumé

- **Tests de compatibilité supprimés** : Utiliser directement les classes
  - `PreinscriptionMetricsService` pour les métriques
  - `SchemaDiscovery` pour la découverte des schémas

- **`TestPreinscriptionMetricsTest`** : Tests de la classe de test

### 2. **`test_fonctionnels_metrics_preinscriptions.py`**
**Tests fonctionnels pour les préinscriptions**

- **`TestPreinscriptionMetricsFunctional`** : Tests end-to-end avec vraie DB
  - Tests avec vraie base de données
  - Vérification de la cohérence des données
  - Tests de gestion d'erreurs
  - Tests d'affichage
  - Tests d'utilisation directe des classes

### 3. **`test_performance_metrics_preinscriptions.py`**
**Tests de performance pour les préinscriptions**

- **`TestPreinscriptionPerformance`** : Tests de performance
  - `test_large_dataset_performance()` : Performance avec gros volumes
  - `test_query_optimization()` : Optimisation des requêtes
  - `test_schema_discovery_performance()` : Performance de découverte
  - `test_metrics_calculation_performance()` : Performance de calcul
  - `test_memory_usage()` : Utilisation mémoire
  - `test_concurrent_analysis_performance()` : Analyses concurrentes

### 4. **`test_load_metrics_preinscriptions.py`**
**Tests de charge pour les préinscriptions**

- **`TestPreinscriptionLoad`** : Tests de charge
  - `test_concurrent_requests()` : Requêtes simultanées
  - `test_high_volume_requests()` : Volume élevé de requêtes
  - `test_database_connection_pool()` : Pool de connexions
  - `test_memory_under_load()` : Mémoire sous charge
  - `test_error_handling_under_load()` : Gestion d'erreurs sous charge
  - `test_throughput_measurement()` : Mesure du débit

### 5. **`test_security_metrics_preinscriptions.py`**
**Tests de sécurité pour les préinscriptions**

- **`TestPreinscriptionSecurity`** : Tests de sécurité
  - `test_sql_injection_protection()` : Protection injection SQL
  - `test_data_access_control()` : Contrôle d'accès aux données
  - `test_input_validation()` : Validation des entrées
  - `test_xss_protection()` : Protection XSS
  - `test_authorization_bypass()` : Contournement d'autorisation
  - `test_data_encryption()` : Chiffrement des données
  - `test_session_security()` : Sécurité de session
  - `test_logging_security()` : Sécurité des logs
  - `test_error_information_disclosure()` : Divulgation d'informations
  - `test_rate_limiting()` : Limitation du taux

### 6. **`test_validation_metrics_preinscriptions.py`**
**Tests de validation pour les préinscriptions**

- **`TestPreinscriptionValidation`** : Tests de validation
  - `test_data_validation()` : Validation des données
  - `test_business_rules()` : Règles métier
  - `test_program_id_validation()` : Validation ID programme
  - `test_program_id_invalidation()` : Invalidation ID programme
  - `test_date_validation()` : Validation des dates
  - `test_date_invalidation()` : Invalidation des dates
  - `test_status_validation()` : Validation des statuts
  - `test_status_invalidation()` : Invalidation des statuts
  - `test_email_validation()` : Validation des emails
  - `test_email_invalidation()` : Invalidation des emails
  - `test_required_fields_validation()` : Validation champs obligatoires
  - `test_data_type_validation()` : Validation des types
  - `test_business_logic_validation()` : Validation logique métier

## Composants Testés

### PreinscriptionAnalyzer
Classe principale pour l'analyse des préinscriptions.

**Méthodes testées :**
- `has_preinscription_table()` : Vérifie l'existence de la table preinscriptions
- `get_total_count()` : Compte le nombre total de préinscriptions
- `get_count_by_status()` : Compte par statut
- `get_recent_count()` : Compte les préinscriptions récentes
- `get_monthly_trend()` : Tendance mensuelle
- `get_detailed_preinscriptions()` : Détails des préinscriptions
- `get_all_metrics()` : Toutes les métriques

### PreinscriptionMetricsService
Service principal pour les métriques de préinscription.

**Méthodes testées :**
- `get_global_metrics()` : Métriques globales
- `get_schema_metrics()` : Métriques par schéma
- `get_schema_details()` : Détails par schéma
- `print_summary()` : Affichage du résumé

## Conventions de Nommage

- **`test_unitaires_metrics_preinscriptions.py`** : Tests unitaires avec mocks
- **`test_fonctionnels_metrics_preinscriptions.py`** : Tests fonctionnels avec vraie DB
- **`test_performance_metrics_preinscriptions.py`** : Tests de performance
- **`test_load_metrics_preinscriptions.py`** : Tests de charge
- **`test_security_metrics_preinscriptions.py`** : Tests de sécurité
- **`test_validation_metrics_preinscriptions.py`** : Tests de validation

## Marquage des Tests

- **Tests unitaires** : Pas de marquage spécial
- **Tests fonctionnels** : `@pytest.mark.integration` et `@pytest.mark.database`
- **Tests de performance** : `@pytest.mark.performance`
- **Tests de charge** : `@pytest.mark.load`
- **Tests de sécurité** : `@pytest.mark.security`
- **Tests de validation** : `@pytest.mark.validation`

## Exécution des Tests

```bash
# Tous les tests de préinscriptions
pytest tests/test_preinscription/test_*metrics_preinscriptions.py -v

# Tests unitaires seulement
pytest tests/test_preinscription/test_unitaires_metrics_preinscriptions.py -v

# Tests fonctionnels seulement
pytest tests/test_preinscription/test_fonctionnels_metrics_preinscriptions.py -v -m "integration"

# Tests de performance
pytest tests/test_preinscription/test_performance_metrics_preinscriptions.py -v -m "performance"

# Tests de charge
pytest tests/test_preinscription/test_load_metrics_preinscriptions.py -v -m "load"

# Tests de sécurité
pytest tests/test_preinscription/test_security_metrics_preinscriptions.py -v -m "security"

# Tests de validation
pytest tests/test_preinscription/test_validation_metrics_preinscriptions.py -v -m "validation"
```

## Commandes Makefile

```bash
# Tests unitaires des préinscriptions
make test-file FILE=test_preinscription/test_unitaires_metrics_preinscriptions.py

# Tests fonctionnels des préinscriptions
make test-file FILE=test_preinscription/test_fonctionnels_metrics_preinscriptions.py

# Tests de performance
make test-performance

# Tests de charge
make test-load

# Tests de sécurité
make test-security

# Tests de validation
make test-validation
```

## Fixtures Disponibles

- **`mock_session`** : Session mockée pour les tests unitaires
- **`test_session`** : Vraie session de base de données pour les tests fonctionnels

## Dépendances

Les tests des préinscriptions dépendent de :
- `app_lia_web.app.services.metrics.preinscription_metrics.PreinscriptionAnalyzer`
- `app_lia_web.app.services.metrics.preinscription_metrics.PreinscriptionMetricsService`
- `app_lia_web.app.services.metrics.preinscription_metrics.SchemaDiscovery`
- `app_lia_web.app.database.get_session_for_metrics`

## Maintenance

### Ajout de Nouveaux Tests
1. Ajouter les tests unitaires dans `test_unitaires_metrics_preinscriptions.py`
2. Ajouter les tests fonctionnels dans `test_fonctionnels_metrics_preinscriptions.py`
3. Ajouter les tests de performance dans `test_performance_metrics_preinscriptions.py`
4. Ajouter les tests de charge dans `test_load_metrics_preinscriptions.py`
5. Ajouter les tests de sécurité dans `test_security_metrics_preinscriptions.py`
6. Ajouter les tests de validation dans `test_validation_metrics_preinscriptions.py`
7. Mettre à jour ce document

### Modification des Composants
1. Mettre à jour les tests unitaires
2. Mettre à jour les tests fonctionnels
3. Mettre à jour les tests de performance
4. Mettre à jour les tests de charge
5. Mettre à jour les tests de sécurité
6. Mettre à jour les tests de validation
7. Vérifier la compatibilité avec les modules existants
8. Mettre à jour ce document

## Notes Techniques

- Les tests unitaires utilisent des mocks pour isoler les composants
- Les tests fonctionnels utilisent une vraie base de données
- Les tests de performance vérifient que les opérations sont raisonnablement rapides
- Les tests de charge vérifient le comportement sous stress
- Les tests de sécurité vérifient la protection contre les attaques courantes
- Les tests de validation vérifient la conformité aux règles métier