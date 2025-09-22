# Implémentation des Schémas par Programme - Version Simplifiée

## Vue d'ensemble
Cette solution utilise les **modèles existants** et les organise simplement dans des **schémas séparés** par programme. Pas de nouveaux modèles !

## Structure des fichiers créés

### 1. Scripts SQL
- `scripts/create_program_schemas_with_existing_models.sql` - Script de migration avec les modèles existants

### 2. Services
- `app/services/program_schema_service.py` - Service de gestion des schémas (utilise les modèles existants)

### 3. Middleware
- `core/program_schema_middleware.py` - Middleware de routage automatique
- `core/program_schema_integration.py` - Intégration dans l'application

### 4. Routes d'administration
- `app/routers/admin_schemas.py` - Routes de gestion des schémas
- `app/templates/admin/schemas.html` - Interface d'administration

## Étapes d'implémentation

### 1. Exécuter le script SQL
```bash
# Se connecter à PostgreSQL
psql -U liauser -d lia_coaching

# Exécuter le script
\i scripts/create_program_schemas_with_existing_models.sql
```

### 2. Modifier main.py
```python
# Ajouter l'import
from app_lia_web.core.program_schema_integration import setup_program_schemas

# Dans la fonction create_app()
def create_app():
    app = FastAPI(...)
    
    # Ajouter la configuration des schémas
    setup_program_schemas(app)
    
    return app
```

### 3. Ajouter les routes d'administration
```python
# Dans app/routers/__init__.py
from .admin_schemas import router as admin_schemas_router

# Dans router_configs
(admin_schemas_router, "/admin", ["admin_schemas"]),
```

### 4. Modifier les services existants pour utiliser les schémas
```python
# Exemple pour le service des candidats
from app_lia_web.core.program_schema_integration import get_program_schema_from_request

class CandidatService:
    def __init__(self, session: Session, request: Request = None):
        self.session = session
        self.program_schema = get_program_schema_from_request(request) if request else None
    
    def get_candidats(self, programme_code: str = None):
        if self.program_schema:
            # Utiliser le schéma spécifique
            schema_name = programme_code.lower() if programme_code else self.program_schema
            query = f"SELECT * FROM {schema_name}.candidats"
            result = self.session.execute(text(query))
            return result.fetchall()
        else:
            # Utiliser le schéma public (comportement existant)
            return self.session.exec(select(Candidat)).all()
```

### 5. Modifier les routes existantes
```python
# Exemple pour les routes d'inscriptions
@router.get("/form", name="form_inscriptions_display")
def inscriptions_ui(
    request: Request,
    programme: str = Query("ACD"),
    # ... autres paramètres
):
    # Le middleware aura déjà configuré request.state.program_schema
    program_schema = get_program_schema_from_request(request)
    
    # Utiliser le service avec le schéma approprié
    candidat_service = CandidatService(session, request)
    # ...
```

## Avantages de cette approche

### 1. Simplicité
- Utilise les modèles existants
- Pas de nouveaux modèles à maintenir
- Migration progressive possible

### 2. Isolation des données
- Chaque programme a ses propres tables
- Pas de confusion entre candidats de différents programmes
- Sécurité renforcée

### 3. Compatibilité
- Compatible avec le système existant
- Pas de breaking changes
- Rollback possible

## Gestion des données existantes

### Option 1: Migration complète
```sql
-- Décommenter dans create_program_schemas_with_existing_models.sql
PERFORM migrate_existing_data_to_schemas();
```

### Option 2: Migration progressive
- Créer les schémas vides
- Migrer les données par programme via l'interface admin
- Tester chaque migration

### Option 3: Système hybride
- Garder les données existantes dans `public`
- Nouvelles données dans les schémas spécifiques
- Migration progressive

## Surveillance et maintenance

### 1. Interface d'administration
- Accès via `/admin/schemas`
- Création/suppression de schémas
- Migration des données existantes
- Sauvegarde en Excel
- Statistiques détaillées

### 2. Logs
- Création de schémas
- Erreurs de migration
- Opérations d'administration

### 3. Sauvegarde
- Automatique avant suppression
- Export Excel par table
- Sauvegarde complète par programme

## Tests recommandés

### 1. Tests unitaires
- Création de schémas
- Migration de données
- Routage automatique

### 2. Tests d'intégration
- Workflow complet par programme
- Isolation des données
- Performance

### 3. Tests de régression
- Compatibilité avec le système existant
- Fonctionnalités existantes
- Migration des données

## Rollback

En cas de problème, il est possible de revenir au système existant :

1. Désactiver le middleware
2. Utiliser les modèles originaux
3. Restaurer les données depuis les sauvegardes

## Support

Pour toute question ou problème :
1. Vérifier les logs
2. Consulter l'interface d'administration
3. Tester avec un programme de test
4. Sauvegarder avant toute modification
