# 🧪 Tests Unitaires - LIA WEB

## 📋 Vue d'ensemble

Ce répertoire contient tous les tests unitaires et d'intégration pour l'application LIA WEB.

## 🏗️ Structure des tests

```
tests/
├── __init__.py              # Module de tests
├── conftest.py              # Configuration pytest et fixtures
├── test_config.py           # Tests de configuration et environnement
├── test_models.py           # Tests des modèles SQLModel
├── test_metrics.py          # Tests du module de métriques
└── README.md               # Ce fichier
```

## 🚀 Exécution des tests

### Avec pytest directement

```bash
# Tous les tests
pytest tests/ -v

# Tests unitaires uniquement
pytest tests/ -m "not integration and not database" -v

# Tests d'intégration
pytest tests/ -m "integration" -v

# Tests avec couverture
pytest tests/ --cov=app --cov-report=html -v
```

### Avec le script personnalisé

```bash
# Tous les tests
python run_tests.py

# Tests unitaires
python run_tests.py --type unit

# Tests d'intégration
python run_tests.py --type integration

# Tests rapides
python run_tests.py --type fast
```

### Avec Make

```bash
# Voir toutes les commandes disponibles
make help

# Tests unitaires
make test-unit

# Tests avec couverture
make test-coverage

# Nettoyage
make clean
```

## 🏷️ Marqueurs de tests

Les tests utilisent des marqueurs pytest pour les catégoriser :

- `unit` : Tests unitaires (pas de base de données)
- `integration` : Tests d'intégration (avec base de données)
- `slow` : Tests lents
- `database` : Tests nécessitant une base de données

## 🔧 Configuration

### Fixtures disponibles

- `test_session` : Session de base de données pour les tests
- `sample_user` : Utilisateur de test
- `sample_programme` : Programme de test
- `mock_session` : Session mockée pour les tests unitaires

### Base de données de test

Les tests d'intégration utilisent une base SQLite en mémoire pour éviter les conflits avec la base de production.

## 📊 Couverture de code

Le rapport de couverture est généré dans `htmlcov/index.html` après l'exécution des tests avec l'option `--cov`.

### Objectif de couverture

- **Minimum** : 70% de couverture de code
- **Objectif** : 80% de couverture de code

## 🧪 Types de tests

### Tests unitaires

- Testent des fonctions/méthodes isolément
- Utilisent des mocks pour les dépendances externes
- Exécution rapide
- Pas de base de données

### Tests d'intégration

- Testent l'interaction entre plusieurs composants
- Utilisent une vraie base de données (SQLite en mémoire)
- Plus lents mais plus réalistes

### Tests de configuration

- Vérifient que l'environnement est correctement configuré
- Testent les imports et les dépendances
- Vérifient la structure du projet

## 📝 Écriture de nouveaux tests

### Structure d'un test

```python
def test_nom_de_la_fonction():
    """Description du test."""
    # Arrange (préparation)
    input_data = "test"
    
    # Act (exécution)
    result = ma_fonction(input_data)
    
    # Assert (vérification)
    assert result == "expected"
```

### Utilisation des fixtures

```python
def test_avec_fixture(sample_user):
    """Test utilisant une fixture."""
    assert sample_user.email == "test@example.com"
```

### Tests avec base de données

```python
@pytest.mark.integration
@pytest.mark.database
def test_crud_operation(test_session):
    """Test CRUD avec base de données."""
    # Créer un objet
    obj = MonModele(nom="test")
    test_session.add(obj)
    test_session.commit()
    
    # Vérifier la création
    assert obj.id is not None
```

## 🐛 Débogage des tests

### Mode verbeux

```bash
pytest tests/ -v -s
```

### Arrêt au premier échec

```bash
pytest tests/ -x
```

### Exécution d'un test spécifique

```bash
pytest tests/test_models.py::TestUser::test_user_creation -v
```

## 📚 Bonnes pratiques

1. **Nommage** : Utilisez des noms descriptifs pour les tests
2. **Documentation** : Ajoutez des docstrings aux tests
3. **Isolation** : Chaque test doit être indépendant
4. **Nettoyage** : Utilisez les fixtures pour la préparation/nettoyage
5. **Assertions** : Utilisez des assertions spécifiques
6. **Mocking** : Mockez les dépendances externes dans les tests unitaires

## 🔍 Exemples de tests

Voir les fichiers de test existants pour des exemples concrets :

- `test_models.py` : Tests des modèles SQLModel
- `test_metrics.py` : Tests du module de métriques
- `test_config.py` : Tests de configuration

## 📞 Support

Pour toute question sur les tests, consultez :

1. La documentation pytest : https://docs.pytest.org/
2. Les exemples dans ce répertoire
3. L'équipe de développement
