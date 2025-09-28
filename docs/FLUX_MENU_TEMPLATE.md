# Flux détaillé : Menu → Template avec schémas par programme

## Vue d'ensemble

Ce document explique le flux complet depuis la sélection d'un élément de menu jusqu'à l'affichage du template, en passant par les middlewares, la gestion des schémas par programme, et les variables de contexte.

## 1. Sélection dans le menu

### 1.1 Structure du menu
```html
<!-- Exemple dans base.html -->
<a href="/preinscriptions/form?programme=ACD" class="menu-item">
  <i class="fa fa-users"></i>
  <span>Préinscriptions</span>
</a>
```

### 1.2 Action utilisateur
- L'utilisateur clique sur un élément de menu
- Le navigateur envoie une requête HTTP GET vers l'URL avec le paramètre `programme`

## 2. Traitement de la requête par FastAPI

### 2.1 Réception de la requête
```
GET /preinscriptions/form?programme=ACD HTTP/1.1
Host: localhost:8000
```

### 2.2 Pipeline des middlewares
FastAPI traite la requête à travers une série de middlewares dans l'ordre suivant :

## 3. Middleware de session partagée

### 3.1 Fichier : `core/middleware.py`
```python
class SharedSessionMiddleware:
    async def dispatch(self, request: Request, call_next):
        # Création d'une session SQLAlchemy partagée
        session = SessionLocal()
        request.state.shared_session = session
        
        # Traitement de la requête
        response = await call_next(request)
        
        # Nettoyage de la session
        session.close()
        return response
```

### 3.2 Variables ajoutées à `request.state`
- `request.state.shared_session` : Session SQLAlchemy partagée

## 4. Middleware de schéma par programme

### 4.1 Fichier : `core/program_schema_integration.py`
```python
class ProgramSchemaMiddleware:
    async def dispatch(self, request: Request, call_next):
        # 1. Extraction du programme depuis l'URL
        programme_code = self.extract_programme_from_request(request)
        
        # 2. Validation du programme
        if self.is_valid_programme(programme_code):
            # 3. Configuration du schéma
            self.setup_program_schema(request, programme_code)
        
        # 4. Traitement de la requête
        response = await call_next(request)
        return response
```

### 4.2 Extraction du programme
```python
def extract_programme_from_request(self, request: Request) -> str:
    # PRIORITÉ 1: Paramètre de requête (?programme=ACD)
    programme = request.query_params.get('programme')
    if programme:
        return programme.upper()
    
    # PRIORITÉ 2: Chemin URL (/preinscriptions/form/ACD)
    path_parts = request.url.path.strip('/').split('/')
    if len(path_parts) >= 3:
        return path_parts[2].upper()
    
    # PRIORITÉ 3: Session utilisateur
    if hasattr(request, 'session'):
        return request.session.get('current_programme', 'ACD')
    
    return 'ACD'  # Valeur par défaut
```

### 4.3 Validation du programme
```python
def is_valid_programme(self, programme_code: str) -> bool:
    if not programme_code:
        return False
    
    # Vérification en base de données
    session = request.state.shared_session
    programme = session.query(Programme).filter(
        Programme.code == programme_code,
        Programme.actif == True
    ).first()
    
    return programme is not None
```

### 4.4 Configuration du schéma
```python
def setup_program_schema(self, request: Request, programme_code: str):
    # 1. Création du service de routage
    routing_service = SchemaRoutingService(request.state.shared_session)
    
    # 2. Configuration du schéma
    schema_name = programme_code.lower()  # ACD → acd
    routing_service.set_schema(schema_name)
    
    # 3. Stockage dans request.state
    request.state.program_schema = schema_name
    request.state.current_programme = programme_code
    request.state.schema_routing_service = routing_service
```

### 4.5 Variables ajoutées à `request.state`
- `request.state.program_schema` : Nom du schéma (ex: "acd")
- `request.state.current_programme` : Code du programme (ex: "ACD")
- `request.state.schema_routing_service` : Service de routage configuré

## 5. Middleware de sécurité

### 5.1 Fichier : `core/security.py`
```python
async def security_middleware(request: Request, call_next):
    # 1. Vérification de l'authentification
    user = await get_current_user(request)
    
    # 2. Vérification des permissions
    if not has_permission(user, request.url.path):
        return RedirectResponse("/login")
    
    # 3. Ajout de l'utilisateur au contexte
    request.state.current_user = user
    
    response = await call_next(request)
    return response
```

### 5.2 Variables ajoutées à `request.state`
- `request.state.current_user` : Utilisateur authentifié

## 6. Traitement de la route

### 6.1 Fichier : `app/routers/preinscriptions.py`
```python
@router.get("/form")
async def preinscriptions_form(
    request: Request,
    programme: str = Query("ACD"),
    current_user: User = Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service)
):
    # 1. Récupération des données depuis le schéma
    programmes = get_active_programmes(schema_routing_service)
    
    # 2. Préparation du contexte du template
    context = {
        "request": request,
        "current_user": current_user,
        "programmes": programmes,
        "current_programme": programme,
        # ... autres variables
    }
    
    # 3. Rendu du template
    return templates.TemplateResponse("programme/preinscriptions_form.html", context)
```

### 6.2 Récupération des données
```python
def get_active_programmes(schema_routing_service):
    # Requête dans le schéma public (tables communes)
    sql = "SELECT * FROM programme WHERE actif = true"
    result = schema_routing_service.execute_in_schema(sql)
    return result.fetchall()
```

## 7. Rendu du template

### 7.1 Fichier : `app/templates/__init__.py`
```python
# Configuration de l'environnement Jinja2
templates = Jinja2Templates(directory="app/templates")

# Ajout des fonctions globales
templates.env.globals.update({
    "get_current_programme_title": get_current_programme_title,
    "get_current_programme_from_session": get_current_programme_from_session,
    # ... autres fonctions
})
```

### 7.2 Fonctions de contexte
```python
def get_current_programme_title(request):
    """Récupère le titre du programme actuel"""
    # PRIORITÉ 1: request.state (middleware)
    if hasattr(request.state, 'program_schema') and request.state.program_schema:
        return request.state.program_schema.upper()
    
    # PRIORITÉ 2: Paramètre de requête
    programme_param = request.query_params.get('programme')
    if programme_param:
        return programme_param.upper()
    
    return "LIA-Gestion coaching"  # Fallback
```

## 8. Structure du template

### 8.1 Template principal : `base.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ get_current_programme_title(request) }} - {{ company_name }}</title>
</head>
<body>
    <!-- Sidebar avec menu -->
    <div class="sidebar">
        {% for programme in get_programmes() %}
            <a href="/preinscriptions/form?programme={{ programme.code }}" 
               class="menu-item {% if current_programme == programme.code %}active{% endif %}">
                {{ programme.nom }}
            </a>
        {% endfor %}
    </div>
    
    <!-- Contenu principal -->
    <div class="content">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

### 8.2 Template spécifique : `programme/preinscriptions_form.html`
```html
{% extends "base.html" %}

{% block content %}
<div class="container">
    <h1>Préinscriptions - {{ get_current_programme_title(request) }}</h1>
    
    <!-- Formulaire de préinscription -->
    <form method="post" action="/preinscriptions/submit">
        <input type="hidden" name="programme_code" value="{{ current_programme }}">
        <!-- ... autres champs ... -->
    </form>
</div>
{% endblock %}
```

## 9. Variables de contexte disponibles

### 9.1 Variables automatiques
- `request` : Objet Request FastAPI
- `current_user` : Utilisateur authentifié
- `current_programme` : Code du programme actuel

### 9.2 Variables depuis `request.state`
- `request.state.program_schema` : Schéma de base de données
- `request.state.current_programme` : Programme actuel
- `request.state.schema_routing_service` : Service de routage
- `request.state.shared_session` : Session SQLAlchemy

### 9.3 Fonctions globales
- `get_current_programme_title(request)` : Titre du programme
- `get_current_programme_from_session(request)` : Programme depuis la session
- `get_programmes()` : Liste des programmes actifs

## 10. Gestion des schémas de base de données

### 10.1 Schéma public (tables communes)
- `programme` : Liste des programmes
- `user` : Utilisateurs
- `partenaire` : Partenaires
- `groupe` : Groupes

### 10.2 Schéma par programme (ex: `acd`)
- `candidats` : Candidats du programme
- `preinscriptions` : Préinscriptions
- `inscriptions` : Inscriptions
- `entreprises` : Entreprises des candidats

### 10.3 Routage des requêtes
```python
class SchemaRoutingService:
    def execute_in_schema(self, sql: str, params: dict = None):
        # Ajout du préfixe de schéma
        sql_with_schema = self._add_schema_to_sql(sql, self.current_schema)
        
        # Exécution dans le bon schéma
        return self.session.execute(text(sql_with_schema), params or {})
    
    def _add_schema_to_sql(self, sql: str, schema: str) -> str:
        # Remplacement des tables par des références complètes
        # candidats → acd.candidats
        for table in self.program_tables:
            sql = re.sub(rf'\b{table}\b', f'{schema}.{table}', sql)
        return sql
```

## 11. Flux de données complet

```
1. Clic menu → URL avec paramètre programme
2. Middleware session → Création session SQLAlchemy
3. Middleware schéma → Configuration schéma + validation programme
4. Middleware sécurité → Vérification auth + permissions
5. Route handler → Récupération données + préparation contexte
6. Template engine → Rendu avec variables de contexte
7. Réponse HTML → Affichage dans le navigateur
```

## 12. Exemple concret : Préinscriptions ACD

### 12.1 URL
```
GET /preinscriptions/form?programme=ACD
```

### 12.2 Variables de contexte
```python
{
    "request": <Request object>,
    "current_user": <User object>,
    "programmes": [<Programme ACD>, <Programme XYZ>],
    "current_programme": "ACD",
    "programme_selectionne": "ACD"
}
```

### 12.3 Variables dans `request.state`
```python
request.state.program_schema = "acd"
request.state.current_programme = "ACD"
request.state.schema_routing_service = <SchemaRoutingService>
request.state.shared_session = <SQLAlchemy Session>
request.state.current_user = <User object>
```

### 12.4 Requêtes SQL exécutées
```sql
-- Dans le schéma public
SELECT * FROM programme WHERE actif = true;

-- Dans le schéma acd
SELECT * FROM acd.candidats WHERE programme_id = 1;
SELECT * FROM acd.preinscriptions WHERE programme_id = 1;
```

### 12.5 Template rendu
```html
<title>ACD - LIA-Gestion coaching</title>
<h1>Préinscriptions - ACD</h1>
<form method="post" action="/preinscriptions/submit">
    <input type="hidden" name="programme_code" value="ACD">
    <!-- ... -->
</form>
```

## 13. Points importants

### 13.1 Isolation des données
- Chaque programme a son propre schéma
- Les données sont automatiquement routées vers le bon schéma
- Pas de mélange entre les programmes

### 13.2 Performance
- Session SQLAlchemy partagée pour éviter les reconnexions
- Cache des schémas pour éviter les requêtes répétées
- Requêtes optimisées avec préfixes de schéma

### 13.3 Sécurité
- Validation du programme avant configuration du schéma
- Vérification des permissions utilisateur
- Isolation des données par programme

### 13.4 Maintenabilité
- Middleware modulaire et réutilisable
- Fonctions de contexte centralisées
- Templates avec héritage et composition
