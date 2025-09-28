# Makefile pour LIA WEB - Tests et développement

.PHONY: help install test test-unit test-integration test-coverage test-fast clean lint format

# Aide
help:
	@echo "🚀 LIA WEB - Commandes disponibles:"
	@echo ""
	@echo "📦 Installation:"
	@echo "  make install          Installer les dépendances"
	@echo ""
	@echo "🧪 Tests:"
	@echo "  make test             Exécuter tous les tests"
	@echo "  make test-unit        Tests unitaires uniquement"
	@echo "  make test-integration Tests d'intégration"
	@echo "  make test-coverage    Tests avec rapport de couverture"
	@echo "  make test-fast        Tests rapides (sans les tests lents)"
	@echo "  make test-full        Tests avec toutes les options (comme pytest.ini)"
	@echo ""
	@echo "🎯 Tests spécifiques:"
	@echo "  make test-file FILE=test_models.py    Test d'un fichier"
	@echo "  make test-class CLASS=TestUser        Test d'une classe"
	@echo "  make test-func FUNC=test_user_creation Test d'une fonction"
	@echo "  make test-method CLASS=TestUser METHOD=test_creation Test d'une méthode"
	@echo "  make test-performance                Tests de performance"
	@echo "  make test-load                       Tests de charge"
	@echo "  make test-security                   Tests de sécurité"
	@echo "  make test-validation                 Tests de validation"
	@echo "  make test-fonctionnels-common        Tests fonctionnels des composants communs"
	@echo "  make test-preinscription             Tests des préinscriptions"
	@echo ""
	@echo "📊 Tests avec couverture:"
	@echo "  make test-file-cov FILE=test_models.py    Test fichier + couverture"
	@echo "  make test-class-cov CLASS=TestUser        Test classe + couverture"
	@echo "  make test-func-cov FUNC=test_user_creation Test fonction + couverture"
	@echo "  make test-method-cov CLASS=TestUser METHOD=test_creation Test méthode + couverture"
	@echo "  make test-method-cov-module CLASS=TestUser METHOD=test_creation MODULE=app.services Test méthode + couverture module"
	@echo ""
	@echo "🔧 Développement:"
	@echo "  make lint             Vérifier le code avec flake8"
	@echo "  make format           Formater le code avec black"
	@echo "  make clean            Nettoyer les fichiers temporaires"

# Installation des dépendances
install:
	@echo "📦 Installation des dépendances..."
	pip install pytest pytest-asyncio pytest-cov flake8 black
	@echo "✅ Installation terminée"

# Tests
test:
	@echo "🧪 Exécution de tous les tests..."
	python -m pytest tests/ -v -s

test-unit:
	@echo "🧪 Tests unitaires..."
	python -m pytest tests/ -m "not integration and not database" -v -s

test-integration:
	@echo "🧪 Tests d'intégration..."
	python -m pytest tests/ -m "integration" -v -s

test-coverage:
	@echo "🧪 Tests avec couverture..."
	python -m pytest tests/ --cov=app --cov-report=html --cov-report=term-missing --cov-fail-under=80 -v -s

test-fast:
	@echo "🧪 Tests rapides..."
	python -m pytest tests/ -m "not slow" -v -s

test-full:
	@echo "🧪 Tests avec toutes les options (pytest.ini)..."
	python -m pytest tests/ -v -s --tb=short --strict-markers --disable-warnings --cov=app --cov-report=html --cov-report=term-missing --cov-fail-under=80

# Tests spécifiques
test-file:
	@echo "🧪 Test du fichier $(FILE)..."
	python -m pytest $(FILE) -v -s

test-class:
	@echo "🧪 Test de la classe $(CLASS)..."
	python -m pytest . -k "$(CLASS)" -v -s

test-func:
	@echo "🧪 Test de la fonction $(FUNC)..."
	python -m pytest . -k "$(FUNC)" -v -s

test-method:
	@echo "🧪 Test de la méthode $(CLASS)::$(METHOD)..."
	python -m pytest . -k "$(CLASS) and $(METHOD)" -v -s

# Tests spécifiques avec couverture
test-file-cov:
	@echo "🧪 Test du fichier $(FILE) avec couverture..."
	python -m pytest $(FILE) --cov=../app --cov-report=html --cov-report=term-missing -v -s

test-class-cov:
	@echo "🧪 Test de la classe $(CLASS) avec couverture..."
	python -m pytest . -k "$(CLASS)" --cov=../app --cov-report=html --cov-report=term-missing -v -s

test-func-cov:
	@echo "🧪 Test de la fonction $(FUNC) avec couverture..."
	python -m pytest . -k "$(FUNC)" --cov=../app --cov-report=html --cov-report=term-missing -v -s

test-method-cov:
	@echo "🧪 Test de la méthode $(CLASS)::$(METHOD) avec couverture..."
	python -m pytest . -k "$(CLASS) and $(METHOD)" --cov=../app --cov-report=html --cov-report=term-missing -v -s

test-method-cov-module:
	@echo "🧪 Test de la méthode $(CLASS)::$(METHOD) avec couverture du module $(MODULE)..."
	python -m pytest . -k "$(CLASS) and $(METHOD)" --cov=app_lia_web.$(MODULE) --cov-report=html --cov-report=term-missing -v -s

# Qualité du code
lint:
	@echo "🔍 Vérification du code..."
	flake8 app/ tests/ --max-line-length=100 --ignore=E203,W503

format:
	@echo "🎨 Formatage du code..."
	black app/ tests/ --line-length=100

# Nettoyage
clean:
	@echo "🧹 Nettoyage..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	@echo "✅ Nettoyage terminé"

# Test de configuration
test-config:
	@echo "⚙️  Test de configuration..."
	python -m pytest tests/test_config.py -v -s

# Tests de performance
test-performance:
	@echo "⚡ Tests de performance..."
	python -m pytest tests/test_preinscription/test_performance_metrics_preinscriptions.py -v -s -m "performance"

# Tests de charge
test-load:
	@echo "📈 Tests de charge..."
	python -m pytest tests/test_preinscription/test_load_metrics_preinscriptions.py -v -s -m "load"

# Tests de sécurité
test-security:
	@echo "🔒 Tests de sécurité..."
	python -m pytest tests/test_preinscription/test_security_metrics_preinscriptions.py -v -s -m "security"

# Tests de validation
test-validation:
	@echo "✅ Tests de validation..."
	python -m pytest tests/test_preinscription/test_validation_metrics_preinscriptions.py -v -s -m "validation"

# Tests fonctionnels des composants communs
test-fonctionnels-common:
	@echo "🔧 Tests fonctionnels des composants communs..."
	python -m pytest tests/test_fonctionnels_metrics_common.py -v -s -m "integration"

# Tests des préinscriptions
test-preinscription:
	@echo "📋 Tests des préinscriptions..."
	python -m pytest tests/test_preinscription/test_*metrics_preinscriptions.py -v -s

# Démarrage de l'application
run:
	@echo "🚀 Démarrage de l'application..."
	uvicorn main:app --reload --host 0.0.0.0 --port 8000
