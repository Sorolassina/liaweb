# Guide des Décorateurs Python

## 📋 Table des matières
1. [Qu'est-ce qu'un décorateur ?](#quest-ce-quun-décorateur)
2. [Syntaxe et fonctionnement](#syntaxe-et-fonctionnement)
3. [Décorateurs intégrés](#décorateurs-intégrés)
4. [Créer ses propres décorateurs](#créer-ses-propres-décorateurs)
5. [Décorateurs avec paramètres](#décorateurs-avec-paramètres)
6. [Décorateurs de classe](#décorateurs-de-classe)
7. [Décorateurs dans pytest](#décorateurs-dans-pytest)
8. [Exemples pratiques](#exemples-pratiques)
9. [Bonnes pratiques](#bonnes-pratiques)

## 🎯 Qu'est-ce qu'un décorateur ?

Un **décorateur** est une fonction qui modifie le comportement d'une autre fonction sans changer son code source. C'est un concept fondamental en Python qui permet d'ajouter des fonctionnalités à des fonctions existantes de manière élégante.

### Analogie simple
Imaginez que vous voulez **emballer un cadeau** :
- Le **cadeau** = votre fonction originale
- Le **papier cadeau** = le décorateur
- Le **résultat** = fonction originale + nouvelles fonctionnalités

## 🔧 Syntaxe et fonctionnement

### Syntaxe de base
```python
@decorateur
def ma_fonction():
    pass

# Équivaut exactement à :
ma_fonction = decorateur(ma_fonction)
```

### Exemple simple
```python
def bold(func):
    """Décorateur qui met le texte en gras"""
    def wrapper():
        return f"**{func()}**"
    return wrapper

@bold
def hello():
    return "Hello World"

print(hello())  # **Hello World**
```

## 🏗️ Décorateurs intégrés

### 1. `@property`
Transforme une méthode en attribut accessible sans parenthèses.

```python
class Personne:
    def __init__(self, prenom, nom):
        self._prenom = prenom
        self._nom = nom
    
    @property
    def nom_complet(self):
        """Retourne le nom complet"""
        return f"{self._prenom} {self._nom}"
    
    @property
    def email(self):
        """Génère un email automatiquement"""
        return f"{self._prenom.lower()}.{self._nom.lower()}@example.com"
    
    @nom_complet.setter
    def nom_complet(self, value):
        """Permet de modifier le nom complet"""
        prenom, nom = value.split(' ', 1)
        self._prenom = prenom
        self._nom = nom

# Utilisation
p = Personne("Jean", "Dupont")
print(p.nom_complet)  # Jean Dupont (pas de parenthèses !)
print(p.email)        # jean.dupont@example.com
p.nom_complet = "Marie Martin"  # Utilise le setter
print(p._prenom)      # Marie
```

### 2. `@staticmethod`
Méthode qui appartient à la classe mais n'a pas accès à `self` ou `cls`.

```python
class MathUtils:
    @staticmethod
    def add(a, b):
        """Additionne deux nombres"""
        return a + b
    
    @staticmethod
    def multiply(a, b):
        """Multiplie deux nombres"""
        return a * b

# Utilisation sans créer d'instance
result = MathUtils.add(5, 3)  # 8
result = MathUtils.multiply(4, 7)  # 28
```

### 3. `@classmethod`
Méthode qui reçoit la classe comme premier argument au lieu de l'instance.

```python
class Personne:
    def __init__(self, nom, age):
        self.nom = nom
        self.age = age
    
    @classmethod
    def from_string(cls, personne_str):
        """Crée une instance à partir d'une chaîne"""
        nom, age = personne_str.split(',')
        return cls(nom, int(age))
    
    @classmethod
    def from_dict(cls, data):
        """Crée une instance à partir d'un dictionnaire"""
        return cls(data['nom'], data['age'])
    
    def __str__(self):
        return f"{self.nom}, {self.age} ans"

# Utilisation
p1 = Personne.from_string("Alice, 25")
p2 = Personne.from_dict({"nom": "Bob", "age": 30})
print(p1)  # Alice, 25 ans
print(p2)  # Bob, 30 ans
```

## 🛠️ Créer ses propres décorateurs

### 1. Décorateur simple (sans paramètres)
```python
def timer(func):
    """Mesure le temps d'exécution d'une fonction"""
    import time
    
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} a pris {end_time - start_time:.2f} secondes")
        return result
    
    return wrapper

@timer
def fonction_lente():
    import time
    time.sleep(1)
    return "Terminé !"

# Utilisation
result = fonction_lente()
# Sortie : fonction_lente a pris 1.00 secondes
```

### 2. Décorateur avec gestion des arguments
```python
def debug(func):
    """Affiche les arguments et le résultat d'une fonction"""
    def wrapper(*args, **kwargs):
        print(f"Appel de {func.__name__} avec args={args}, kwargs={kwargs}")
        result = func(*args, **kwargs)
        print(f"Résultat : {result}")
        return result
    return wrapper

@debug
def addition(a, b):
    return a + b

@debug
def saluer(nom, message="Bonjour"):
    return f"{message} {nom} !"

# Utilisation
result = addition(5, 3)
# Sortie : Appel de addition avec args=(5, 3), kwargs={}
#          Résultat : 8

result = saluer("Alice", message="Salut")
# Sortie : Appel de saluer avec args=('Alice',), kwargs={'message': 'Salut'}
#          Résultat : Salut Alice !
```

### 3. Décorateur avec `functools.wraps`
```python
import functools

def cache_result(func):
    """Cache le résultat d'une fonction"""
    cache = {}
    
    @functools.wraps(func)  # Préserve les métadonnées de la fonction originale
    def wrapper(*args, **kwargs):
        key = str(args) + str(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
            print(f"Calcul de {func.__name__} pour {args}")
        else:
            print(f"Cache hit pour {func.__name__} avec {args}")
        return cache[key]
    
    return wrapper

@cache_result
def fibonacci(n):
    """Calcule le n-ième nombre de Fibonacci"""
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Utilisation
print(fibonacci(10))  # Calcul
print(fibonacci(10))  # Cache hit
print(fibonacci.__name__)  # fibonacci (grâce à functools.wraps)
```

## 🎛️ Décorateurs avec paramètres

### 1. Décorateur qui accepte des paramètres
```python
def repeat(n_times):
    """Décorateur qui répète une fonction n fois"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            results = []
            for i in range(n_times):
                print(f"Exécution {i+1}/{n_times}")
                result = func(*args, **kwargs)
                results.append(result)
            return results
        return wrapper
    return decorator

@repeat(3)
def saluer(nom):
    return f"Bonjour {nom} !"

# Utilisation
results = saluer("Alice")
# Sortie : Exécution 1/3
#          Exécution 2/3
#          Exécution 3/3
# results = ["Bonjour Alice !", "Bonjour Alice !", "Bonjour Alice !"]
```

### 2. Décorateur avec paramètres conditionnels
```python
def validate_types(**expected_types):
    """Valide les types des arguments"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Validation des arguments positionnels
            for i, (arg, expected_type) in enumerate(zip(args, expected_types.values())):
                if not isinstance(arg, expected_type):
                    raise TypeError(f"Argument {i} doit être de type {expected_type.__name__}")
            
            # Validation des arguments nommés
            for key, value in kwargs.items():
                if key in expected_types:
                    if not isinstance(value, expected_types[key]):
                        raise TypeError(f"Argument '{key}' doit être de type {expected_types[key].__name__}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

@validate_types(a=int, b=str)
def process_data(a, b):
    return f"Nombre: {a}, Texte: {b}"

# Utilisation
print(process_data(42, "Hello"))  # OK
# print(process_data("42", "Hello"))  # TypeError: Argument 0 doit être de type int
```

## 🏛️ Décorateurs de classe

### 1. Décorateur qui modifie une classe
```python
def add_methods(**methods):
    """Ajoute des méthodes à une classe"""
    def decorator(cls):
        for method_name, method_func in methods.items():
            setattr(cls, method_name, method_func)
        return cls
    return decorator

@add_methods(
    to_dict=lambda self: {k: v for k, v in self.__dict__.items()},
    from_dict=lambda cls, data: cls(**data),
    __str__=lambda self: f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in self.__dict__.items())})"
)
class Personne:
    def __init__(self, nom, age):
        self.nom = nom
        self.age = age

# Utilisation
p = Personne("Alice", 25)
print(p)  # Personne(nom=Alice, age=25)
print(p.to_dict())  # {'nom': 'Alice', 'age': 25}
```

### 2. Décorateur de classe avec métaclasse
```python
def singleton(cls):
    """Décorateur qui implémente le pattern Singleton"""
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance

@singleton
class Database:
    def __init__(self):
        print("Création de la connexion DB")
        self.connected = True

# Utilisation
db1 = Database()  # Création de la connexion DB
db2 = Database()  # Pas de message, réutilise l'instance
print(db1 is db2)  # True
```

## 🧪 Décorateurs dans pytest

### 1. `@pytest.fixture`
```python
import pytest

@pytest.fixture
def mock_database():
    """Crée une base de données mock pour les tests"""
    class MockDB:
        def __init__(self):
            self.data = {}
        
        def get(self, key):
            return self.data.get(key)
        
        def set(self, key, value):
            self.data[key] = value
    
    return MockDB()

def test_database_operations(mock_database):
    """Test des opérations de base de données"""
    mock_database.set("user:1", {"nom": "Alice"})
    user = mock_database.get("user:1")
    assert user["nom"] == "Alice"
```

### 2. `@pytest.fixture` avec scope
```python
@pytest.fixture(scope="session")
def expensive_setup():
    """Setup coûteux qui ne s'exécute qu'une fois par session"""
    print("Setup coûteux...")
    return {"config": "production"}

@pytest.fixture(scope="function")
def fresh_data():
    """Données fraîches pour chaque test"""
    return {"users": [], "count": 0}

def test_with_expensive_setup(expensive_setup, fresh_data):
    """Test qui utilise le setup coûteux"""
    assert expensive_setup["config"] == "production"
    assert fresh_data["count"] == 0
```

### 3. `@pytest.mark.parametrize`
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (0, 0),
    (-1, -2)
])
def test_double(input, expected):
    """Test de la fonction double avec plusieurs valeurs"""
    assert input * 2 == expected

@pytest.mark.parametrize("user_data", [
    {"nom": "Alice", "age": 25},
    {"nom": "Bob", "age": 30},
    {"nom": "Charlie", "age": 35}
])
def test_user_creation(user_data):
    """Test de création d'utilisateur avec différents données"""
    user = User(**user_data)
    assert user.nom == user_data["nom"]
    assert user.age == user_data["age"]
```

### 4. Marqueurs personnalisés
```python
# Dans pytest.ini
markers =
    slow: marque les tests lents
    integration: marque les tests d'intégration
    unit: marque les tests unitaires

# Dans les tests
@pytest.mark.slow
def test_complex_calculation():
    """Test qui prend du temps"""
    # Calcul complexe...
    pass

@pytest.mark.integration
def test_database_integration():
    """Test d'intégration avec la base de données"""
    # Test avec vraie DB...
    pass

# Exécution sélective
# pytest -m "not slow"  # Exclut les tests lents
# pytest -m "integration"  # Seulement les tests d'intégration
```

## 💼 Exemples pratiques

### 1. Décorateur de logging
```python
import logging
from functools import wraps

def log_function_calls(logger_name="app"):
    """Log tous les appels de fonction"""
    logger = logging.getLogger(logger_name)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Appel de {func.__name__} avec args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Succès de {func.__name__}, résultat: {result}")
                return result
            except Exception as e:
                logger.error(f"Erreur dans {func.__name__}: {e}")
                raise
        return wrapper
    return decorator

@log_function_calls("business_logic")
def calculer_prix(prix_base, taux_tva):
    if taux_tva < 0:
        raise ValueError("Le taux de TVA ne peut pas être négatif")
    return prix_base * (1 + taux_tva)

# Utilisation
try:
    prix_final = calculer_prix(100, 0.20)
    print(f"Prix final: {prix_final}")
except ValueError as e:
    print(f"Erreur: {e}")
```

### 2. Décorateur de retry
```python
import time
from functools import wraps

def retry(max_attempts=3, delay=1, backoff=2):
    """Réessaie une fonction en cas d'échec"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff ** attempt)
                        print(f"Tentative {attempt + 1} échouée, réessai dans {wait_time}s...")
                        time.sleep(wait_time)
            
            raise last_exception
        return wrapper
    return decorator

@retry(max_attempts=3, delay=1, backoff=2)
def api_call():
    """Simule un appel API qui peut échouer"""
    import random
    if random.random() < 0.7:  # 70% de chance d'échec
        raise ConnectionError("Erreur de connexion API")
    return "Succès !"

# Utilisation
try:
    result = api_call()
    print(result)
except ConnectionError as e:
    print(f"Échec après 3 tentatives: {e}")
```

### 3. Décorateur de validation
```python
def validate_range(min_val=None, max_val=None):
    """Valide qu'un argument est dans une plage donnée"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Validation des arguments positionnels
            for i, arg in enumerate(args):
                if isinstance(arg, (int, float)):
                    if min_val is not None and arg < min_val:
                        raise ValueError(f"Argument {i} ({arg}) < {min_val}")
                    if max_val is not None and arg > max_val:
                        raise ValueError(f"Argument {i} ({arg}) > {max_val}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

@validate_range(min_val=0, max_val=100)
def calculer_pourcentage(valeur, total):
    """Calcule un pourcentage entre 0 et 100"""
    return (valeur / total) * 100

# Utilisation
try:
    pct = calculer_pourcentage(75, 100)
    print(f"Pourcentage: {pct}%")
except ValueError as e:
    print(f"Erreur de validation: {e}")
```

## ✅ Bonnes pratiques

### 1. Toujours utiliser `functools.wraps`
```python
# ❌ Mauvais
def bad_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# ✅ Bon
from functools import wraps

def good_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

### 2. Préserver la signature de la fonction
```python
import inspect
from functools import wraps

def preserve_signature(func):
    """Préserve la signature de la fonction originale"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Vérification de la signature
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        return func(*args, **kwargs)
    return wrapper
```

### 3. Gérer les exceptions proprement
```python
def safe_decorator(func):
    """Décorateur qui gère les exceptions"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Erreur dans {func.__name__}: {e}")
            # Optionnel : relancer l'exception ou retourner une valeur par défaut
            raise
    return wrapper
```

### 4. Documenter les décorateurs
```python
def documented_decorator(description="Description du décorateur"):
    """
    Décorateur bien documenté
    
    Args:
        description (str): Description du décorateur
    
    Returns:
        function: Fonction décorée
    
    Raises:
        ValueError: Si les paramètres sont invalides
    
    Example:
        @documented_decorator("Mon décorateur")
        def ma_fonction():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"Décorateur: {description}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## 🎯 Résumé

Les décorateurs Python sont des outils puissants qui permettent :

- **Modifier le comportement** des fonctions sans changer leur code
- **Ajouter des fonctionnalités** (logging, validation, cache, etc.)
- **Réutiliser du code** de manière élégante
- **Séparer les préoccupations** (logique métier vs aspects transversaux)
- **Améliorer la lisibilité** du code

**Concepts clés :**
- `@decorateur` = `func = decorateur(func)`
- Utiliser `functools.wraps` pour préserver les métadonnées
- Gérer les arguments avec `*args, **kwargs`
- Créer des décorateurs avec paramètres en utilisant des fonctions imbriquées

Les décorateurs sont essentiels pour écrire du code Python propre, maintenable et réutilisable ! 🚀
