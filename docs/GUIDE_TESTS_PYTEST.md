# 🧪 Guide Complet - Tests et Configuration Pytest

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Configuration pytest.ini](#configuration-pytestini)
3. [Marqueurs pytest](#marqueurs-pytest)
4. [Filtres d'avertissements](#filtres-davertissements)
5. [Makefile et commandes](#makefile-et-commandes)
6. [Exemples d'utilisation](#exemples-dutilisation)
7. [Bonnes pratiques](#bonnes-pratiques)

---

## 🎯 Vue d'ensemble

Ce guide explique la configuration complète des tests unitaires et d'intégration pour le projet LIA WEB, incluant :
- Configuration pytest
- Marqueurs pour organiser les tests
- Commandes Makefile
- Exemples pratiques

---

## ⚙️ Configuration pytest.ini

### **Fichier : `pytest.ini`**

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    database: Tests that require database
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### **Explication des options `addopts` :**

| Option | Description | Exemple de résultat |
|--------|-------------|-------------------|
| `-v` | Mode verbeux | Affiche le nom de chaque test |
| `--tb=short` | Traceback court | Erreurs concises en cas d'échec |
| `--strict-markers` | Validation stricte des marqueurs | Erreur si marqueur non déclaré |
| `--disable-warnings` | Masque les avertissements | Sortie plus propre |
| `--cov=app` | Couverture du dossier `app/` | Analyse quelles lignes sont testées |
| `--cov-report=html` | Rapport HTML | Génère `htmlcov/index.html` |
| `--cov-report=term-missing` | Lignes manquantes | Affiche les lignes non couvertes |
| `--cov-fail-under=80` | Seuil minimum 80% | Échec si couverture insuffisante |

---

## 🏷️ Marqueurs pytest

### **1. `@pytest.mark.unit` - Tests unitaires**

**Objectif :** Tests rapides et isolés, sans dépendances externes.

**Caractéristiques :**
- ⚡ Rapides (quelques millisecondes)
- 🎭 Utilisent des mocks
- 🔒 Pas de base de données
- 🧪 Testent des fonctions individuelles

**Exemple :**
```python
@pytest.mark.unit
def test_user_creation():
    """Test de création d'un utilisateur."""
    user = User(
        email="test@example.com",
        nom_complet="Test User",
        mot_de_passe_hash="hashed_password"
    )
    assert user.email == "test@example.com"
    assert user.nom_complet == "Test User"

@pytest.mark.unit
def test_schema_discovery(mock_session):
    """Test avec mock - pas de vraie DB."""
    discovery = SchemaDiscovery(mock_session)
    schemas = discovery.get_all_program_schemas()
    assert "acd" in schemas
    assert "aci" in schemas
```

### **2. `@pytest.mark.integration` - Tests d'intégration**

**Objectif :** Tests des interactions entre composants.

**Caractéristiques :**
- 🔄 Testent plusieurs composants ensemble
- 🗄️ Utilisent une vraie base de données (SQLite en mémoire)
- ⏱️ Plus lents que les tests unitaires
- 🧪 Testent des workflows complets

**Exemple :**
```python
@pytest.mark.integration
@pytest.mark.database
def test_user_crud(test_session):
    """Test CRUD complet avec vraie DB."""
    # Create
    user = User(email="test@example.com", nom_complet="Test")
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    
    assert user.id is not None
    assert user.email == "test@example.com"
    
    # Read
    found_user = test_session.get(User, user.id)
    assert found_user.nom_complet == "Test"
    
    # Update
    found_user.nom_complet = "Updated Name"
    test_session.commit()
    test_session.refresh(found_user)
    
    assert found_user.nom_complet == "Updated Name"
    
    # Delete
    test_session.delete(found_user)
    test_session.commit()
    
    deleted_user = test_session.get(User, user.id)
    assert deleted_user is None
```

### **3. `@pytest.mark.slow` - Tests lents**

**Objectif :** Marquer les tests qui prennent du temps.

**Caractéristiques :**
- ⏳ Durée > 5 secondes
- 📊 Traitement de gros volumes
- 🧪 Tests de performance
- 🔄 Peuvent être exclus des tests rapides

**Exemple :**
```python
@pytest.mark.slow
@pytest.mark.integration
def test_large_dataset_processing():
    """Test avec un gros volume de données."""
    # Création de 10000 enregistrements
    users = []
    for i in range(10000):
        user = User(
            email=f"user{i}@example.com",
            nom_complet=f"User {i}",
            mot_de_passe_hash="hashed"
        )
        users.append(user)
    
    # Test de performance
    start_time = time.time()
    # Traitement des données...
    processing_time = time.time() - start_time
    
    assert processing_time < 30  # Doit être < 30 secondes
```

### **4. `@pytest.mark.database` - Tests avec base de données**

**Objectif :** Marquer les tests nécessitant une base de données.

**Caractéristiques :**
- 🗄️ Nécessitent une connexion DB
- 🔄 Peuvent modifier les données
- ⚠️ Nécessitent une session de test
- 🧹 Doivent nettoyer après eux

**Exemple :**
```python
@pytest.mark.database
def test_schema_discovery_with_real_db(test_session):
    """Test de découverte de schémas avec vraie DB."""
    discovery = SchemaDiscovery(test_session)
    schemas = discovery.get_all_program_schemas()
    
    # Avec une vraie DB, on devrait avoir au moins le schéma public
    assert isinstance(schemas, list)
    assert len(schemas) >= 0  # Peut être vide selon l'état de la DB
```

---

## 🔇 Filtres d'avertissements

### **Configuration :**
```ini
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### **Explication :**

#### **`ignore::DeprecationWarning`**
- **Objectif :** Masque les avertissements de dépréciation
- **Pourquoi :** Évite le bruit dans les tests
- **Exemple :** Masque les avertissements des bibliothèques tierces

#### **`ignore::PendingDeprecationWarning`**
- **Objectif :** Masque les avertissements futurs de dépréciation
- **Pourquoi :** Avertissements "à venir" qui polluent la sortie
- **Exemple :** Masque les avertissements des futures versions

### **Exemple d'avertissement masqué :**
```python
# Sans filtre : Affiche l'avertissement
# DeprecationWarning: Function old_function is deprecated

# Avec filtre : Masque l'avertissement
# (Sortie propre)
```

---

## 🔧 Makefile et commandes

### **Commandes de base :**

```bash
# Tests généraux
make test              # Tous les tests (simple)
make test-full         # Tous les tests (avec toutes les options)
make test-unit         # Tests unitaires uniquement
make test-integration  # Tests d'intégration
make test-coverage     # Tests avec couverture
make test-fast         # Tests rapides (sans les lents)
```

### **Tests spécifiques :**

```bash
# Test d'un fichier
make test-file FILE=test_models.py

# Test d'une classe
make test-class CLASS=TestUser

# Test d'une fonction
make test-func FUNC=test_user_creation
```

### **Tests avec couverture :**

```bash
# Test d'un fichier avec couverture
make test-file-cov FILE=test_models.py

# Test d'une classe avec couverture
make test-class-cov CLASS=TestUser

# Test d'une fonction avec couverture
make test-func-cov FUNC=test_user_creation
```

### **Équivalence avec pytest direct :**

| Commande Make | Équivalent pytest |
|---------------|-------------------|
| `make test-unit` | `pytest -m "unit" -v` |
| `make test-integration` | `pytest -m "integration" -v` |
| `make test-fast` | `pytest -m "not slow" -v` |
| `make test-coverage` | `pytest --cov=app --cov-report=html -v` |

---

## 🚀 Exemples d'utilisation

### **Scénario 1 : Développement quotidien**

```bash
# Test rapide pendant le développement
make test-unit

# Résultat :
# 🧪 Tests unitaires...
# tests/test_models.py::TestUser::test_user_creation PASSED
# tests/test_metrics.py::TestSchemaDiscovery::test_init PASSED
# ========== 15 passed in 2.34s ==========
```

### **Scénario 2 : Avant un commit**

```bash
# Tests complets avec couverture
make test-full

# Résultat :
# 🧪 Tests avec toutes les options (pytest.ini)...
# tests/test_models.py::TestUser::test_user_creation PASSED
# tests/test_metrics.py::TestSchemaDiscovery::test_init PASSED
# ---------- coverage: platform win32, python 3.11.0 -----------
# Name                     Stmts   Miss  Cover   Missing
# ------------------------------------------------------
# app/models/base.py         150      5    97%   45-49
# app/services/metrics.py    200     10    95%   100-110
# ------------------------------------------------------
# TOTAL                      350     15    96%
# ========== 15 passed in 5.67s ==========
```

### **Scénario 3 : Test spécifique**

```bash
# Test d'une fonction spécifique
make test-func FUNC=test_user_creation

# Résultat :
# 🧪 Test de la fonction test_user_creation...
# tests/test_models.py::TestUser::test_user_creation PASSED
# ========== 1 passed in 0.45s ==========
```

### **Scénario 4 : Tests avec filtres**

```bash
# Tests unitaires d'un fichier spécifique
python -m pytest tests/test_models.py -m "unit" -v

# Tests d'intégration mais pas les lents
python -m pytest tests/ -m "integration and not slow" -v

# Tests avec base de données
python -m pytest tests/ -m "database" -v
```

---

## 📚 Bonnes pratiques

### **1. Organisation des tests**

```python
# ✅ Bon : Test bien organisé
@pytest.mark.unit
def test_user_creation():
    """Test de création d'un utilisateur."""
    # Arrange
    email = "test@example.com"
    nom = "Test User"
    
    # Act
    user = User(email=email, nom_complet=nom)
    
    # Assert
    assert user.email == email
    assert user.nom_complet == nom

# ❌ Mauvais : Test mal organisé
def test_user():
    user = User("test@example.com", "Test User")
    assert user.email == "test@example.com"
    assert user.nom_complet == "Test User"
    # Pas de documentation, pas de marqueur
```

### **2. Utilisation des marqueurs**

```python
# ✅ Bon : Marqueurs appropriés
@pytest.mark.unit
def test_calcul_simple():
    """Test unitaire simple."""
    pass

@pytest.mark.integration
@pytest.mark.database
def test_crud_complet():
    """Test d'intégration avec DB."""
    pass

@pytest.mark.slow
@pytest.mark.integration
def test_performance():
    """Test de performance."""
    pass

# ❌ Mauvais : Marqueurs inappropriés
@pytest.mark.unit  # Erreur : test d'intégration marqué comme unitaire
def test_with_database(test_session):
    user = User(email="test@example.com")
    test_session.add(user)  # Utilise la vraie DB !
    test_session.commit()
```

### **3. Nettoyage des tests**

```python
# ✅ Bon : Nettoyage automatique
@pytest.mark.integration
@pytest.mark.database
def test_user_crud(test_session):
    """Test avec nettoyage automatique."""
    # Le fixture test_session nettoie automatiquement
    user = User(email="test@example.com")
    test_session.add(user)
    test_session.commit()
    # Pas besoin de nettoyer manuellement

# ❌ Mauvais : Pas de nettoyage
@pytest.mark.integration
def test_user_crud():
    session = get_session()  # Session réelle !
    user = User(email="test@example.com")
    session.add(user)
    session.commit()
    # Oubli de nettoyer - pollue la DB !
```

### **4. Documentation des tests**

```python
# ✅ Bon : Documentation complète
@pytest.mark.unit
def test_user_creation_with_valid_data():
    """
    Test de création d'un utilisateur avec des données valides.
    
    Vérifie que :
    - L'utilisateur est créé avec succès
    - Les champs obligatoires sont remplis
    - Les valeurs par défaut sont correctes
    """
    user = User(
        email="test@example.com",
        nom_complet="Test User",
        mot_de_passe_hash="hashed_password"
    )
    
    assert user.email == "test@example.com"
    assert user.nom_complet == "Test User"
    assert user.actif is True  # Valeur par défaut

# ❌ Mauvais : Pas de documentation
def test_user():
    user = User("test@example.com", "Test User")
    assert user.email == "test@example.com"
```

---

## 🎯 Résumé des commandes

### **Workflow de développement :**

```bash
# 1. Développement quotidien
make test-unit        # Tests rapides
make test-fast        # Tests essentiels

# 2. Avant un commit
make test-full        # Tests complets + couverture
make lint             # Vérification du code

# 3. Avant un déploiement
make test-integration # Tests d'intégration
make test-coverage    # Tests + couverture
```

### **Tests spécifiques :**

```bash
# Test d'un fichier
make test-file FILE=test_models.py

# Test d'une classe
make test-class CLASS=TestUser

# Test d'une fonction
make test-func FUNC=test_user_creation

# Tests avec couverture
make test-file-cov FILE=test_models.py
make test-class-cov CLASS=TestUser
make test-func-cov FUNC=test_user_creation
```

### **Filtres par marqueurs :**

```bash
# Tests unitaires uniquement
pytest -m "unit"

# Tests d'intégration uniquement
pytest -m "integration"

# Tests rapides (sans les lents)
pytest -m "not slow"

# Tests avec base de données
pytest -m "database"

# Combinaisons
pytest -m "unit and not slow"      # Tests unitaires rapides
pytest -m "integration and database"  # Tests d'intégration avec DB
pytest -m "unit or integration"    # Tests unitaires ou d'intégration
```

---

## 🔍 Débogage des tests

### **Mode debug :**

```bash
# Arrêter au premier échec
pytest tests/test_models.py -x -v

# Mode interactif en cas d'échec
pytest tests/test_models.py --pdb -v

# Afficher les prints
pytest tests/test_models.py -s -v

# Mode très verbeux
pytest tests/test_models.py -vv
```

### **Vérification des tests :**

```bash
# Lister tous les tests sans les exécuter
pytest tests/ --collect-only

# Vérifier les marqueurs
pytest --markers

# Vérifier la configuration
pytest --version
```

---

## 📞 Support et ressources

- **Documentation pytest :** https://docs.pytest.org/
- **Documentation coverage :** https://coverage.readthedocs.io/
- **Guide des tests dans le projet :** `tests/README.md`
- **Configuration :** `pytest.ini` et `Makefile`

---

*Dernière mise à jour : $(date)*
*Version du projet : LIA WEB v1.0*
