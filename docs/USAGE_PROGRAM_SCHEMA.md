# Guide d'usage des schémas par programme

## Principe de base

Le système de schémas par programme utilise `request.state.program_schema` comme source unique de vérité pour le schéma actuel.

## Fonctions utilitaires disponibles

### Dans les routes FastAPI

```python
from app_lia_web.core.program_schema_integration import (
    get_current_program_schema,
    get_current_program_code,
    get_schema_routing_service
)

@router.get("/ma-route")
def ma_route(
    request: Request,
    schema_routing_service = Depends(get_schema_routing_service)
):
    # Le schéma est automatiquement configuré
    current_schema = get_current_program_schema(request)  # ex: "acd"
    current_program = get_current_program_code(request)   # ex: "ACD"
    
    # Utiliser le service de routage
    result = schema_routing_service.execute_in_schema(
        "SELECT * FROM candidats WHERE id = :id",
        {"id": 123}
    )
```

### Dans les templates

```python
from app_lia_web.core.program_schema_integration import get_current_program_code

def render_template(request):
    programme_code = get_current_program_code(request)
    # Utiliser programme_code dans le template
```

## Bonnes pratiques

### ✅ À FAIRE

1. **Utiliser `request.state.program_schema`** comme source de vérité
2. **Utiliser les fonctions utilitaires** : `get_current_program_schema()`, `get_current_program_code()`
3. **Laisser le middleware gérer** la détection et configuration du schéma
4. **Utiliser `schema_routing_service`** pour les requêtes SQL

### ❌ À ÉVITER

1. **Ne pas calculer manuellement** le schéma avec `.lower()`
2. **Ne pas extraire manuellement** le programme depuis `request.query_params`
3. **Ne pas utiliser `set_schema()` manuellement** sauf cas très spéciaux
4. **Ne pas hardcoder** des codes de programme

## Exemples de migration

### Avant (❌)
```python
# Route
programme_code = request.query_params.get('programme', 'ACD')
schema_routing_service.set_schema(programme_code.lower())

# Template
programme = request.query_params.get('programme', 'PUBLIC')
```

### Après (✅)
```python
# Route
current_schema = get_current_program_schema(request)
# schema_routing_service est déjà configuré par le middleware

# Template  
programme = get_current_program_code(request)
```

## Architecture

Le middleware `ProgramSchemaMiddleware` :
1. Détecte le programme depuis l'URL, query params, headers ou formulaires
2. Crée automatiquement le schéma si nécessaire
3. Configure `request.state.program_schema`
4. Met à disposition `request.state.schema_routing_service`

Toutes les autres parties du code doivent utiliser ces valeurs préconfigurées.
