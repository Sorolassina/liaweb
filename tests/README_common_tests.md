# Tests des Composants Communs de Métriques

## Vue d'ensemble

Ce document décrit l'organisation des tests pour les composants communs des métriques, qui sont utilisés par tous les modules de métriques (préinscriptions, inscriptions, etc.).

## Structure des Fichiers de Test

### 1. **`test_unitaires_metrics_common.py`**
**Tests unitaires pour les composants communs**

- **`TestSchemaDiscovery`** : Tests de la classe de découverte des schémas
  - `test_get_all_program_schemas()` : Récupération des schémas
  - `test_schema_has_table()` : Vérification d'existence d'une table
  - `test_get_schema_tables()` : Récupération des tables d'un schéma
  - `test_schema_discovery_error_handling()` : Gestion d'erreurs
  - `test_schema_discovery_with_mock_session()` : Tests avec session mockée

- **`TestGetProgramSchemas`** : Tests de la fonction utilitaire
  - `test_get_program_schemas()` : Récupération de l'instance de découverte
  - `test_get_program_schemas_singleton()` : Vérification du pattern singleton
  - `test_get_program_schemas_with_different_sessions()` : Différentes sessions

- **`TestCommonMetricsIntegration`** : Tests d'intégration des composants communs
  - `test_schema_discovery_integration()` : Intégration complète
  - `test_get_program_schemas_integration()` : Intégration de la fonction utilitaire

### 2. **`test_fonctionnels_metrics_common.py`**
**Tests fonctionnels pour les composants communs**

- **`TestSchemaDiscoveryFunctional`** : Tests fonctionnels de la découverte des schémas
  - `test_get_all_program_schemas_with_real_db()` : Récupération avec vraie DB
  - `test_schema_has_table_with_real_db()` : Vérification d'existence avec vraie DB
  - `test_get_schema_tables_with_real_db()` : Récupération des tables avec vraie DB
  - `test_schema_discovery_error_handling()` : Gestion d'erreurs avec vraie DB
  - `test_schema_discovery_performance()` : Performance avec vraie DB
  - `test_schema_discovery_consistency()` : Cohérence avec vraie DB

- **`TestGetProgramSchemasFunctional`** : Tests fonctionnels de la fonction utilitaire
  - `test_get_program_schemas_with_real_db()` : Fonction avec vraie DB
  - `test_get_program_schemas_multiple_calls()` : Appels multiples
  - `test_get_program_schemas_with_different_sessions()` : Différentes sessions

- **`TestCommonMetricsIntegration`** : Tests d'intégration des composants communs
  - `test_schema_discovery_with_preinscription_table()` : Découverte avec table préinscription
  - `test_schema_discovery_complete_workflow()` : Workflow complet
  - `test_schema_discovery_with_database_queries()` : Requêtes directes à la base
  - `test_schema_discovery_error_recovery()` : Récupération d'erreurs
  - `test_schema_discovery_memory_usage()` : Utilisation mémoire

## Composants Testés

### SchemaDiscovery
Classe principale pour la découverte des schémas de base de données.

**Méthodes testées :**
- `get_all_program_schemas()` : Récupère tous les schémas de programmes
- `schema_has_table(schema_name, table_name)` : Vérifie l'existence d'une table dans un schéma
- `get_schema_tables(schema_name)` : Récupère toutes les tables d'un schéma

### get_program_schemas()
Fonction utilitaire qui retourne une instance de SchemaDiscovery.

**Comportement testé :**
- Pattern singleton
- Gestion des sessions
- Intégration avec la base de données

## Marquage des Tests

- **Tests unitaires** : Pas de marquage spécial
- **Tests fonctionnels** : `@pytest.mark.integration` et `@pytest.mark.database`

## Exécution des Tests

```bash
# Tous les tests des composants communs
pytest tests/test_*metrics_common.py -v

# Tests unitaires seulement
pytest tests/test_unitaires_metrics_common.py -v

# Tests fonctionnels seulement
pytest tests/test_fonctionnels_metrics_common.py -v -m "integration"

# Tests avec couverture
pytest tests/test_*metrics_common.py --cov=app_lia_web.app.services.metrics.preinscription_metrics --cov-report=html
```

## Commandes Makefile

```bash
# Tests unitaires des composants communs
make test-file FILE=test_unitaires_metrics_common.py

# Tests fonctionnels des composants communs
make test-fonctionnels-common

# Tests avec couverture
make test-file-cov FILE=test_unitaires_metrics_common.py
```

## Fixtures Disponibles

- **`mock_session`** : Session mockée pour les tests unitaires
- **`test_session`** : Vraie session de base de données pour les tests fonctionnels

## Dépendances

Les tests des composants communs dépendent de :
- `app_lia_web.app.services.metrics.preinscription_metrics.SchemaDiscovery`
- `app_lia_web.app.services.metrics.preinscription_metrics.get_program_schemas`
- `app_lia_web.app.database.get_session_for_metrics`

## Utilisation par les Autres Modules

Ces composants communs sont utilisés par :
- Module de préinscriptions
- Module d'inscriptions (à venir)
- Module de candidats (à venir)
- Module d'entreprises (à venir)

## Maintenance

### Ajout de Nouveaux Tests
1. Ajouter les tests unitaires dans `test_unitaires_metrics_common.py`
2. Ajouter les tests fonctionnels dans `test_fonctionnels_metrics_common.py`
3. Mettre à jour ce document

### Modification des Composants
1. Mettre à jour les tests unitaires
2. Mettre à jour les tests fonctionnels
3. Vérifier la compatibilité avec les modules existants
4. Mettre à jour ce document

## Notes Techniques

- Les tests unitaires utilisent des mocks pour isoler les composants
- Les tests fonctionnels utilisent une vraie base de données
- La classe SchemaDiscovery implémente le pattern singleton
- Les tests de performance vérifient que les opérations sont raisonnablement rapides
- Les tests de mémoire vérifient que l'utilisation mémoire reste acceptable
