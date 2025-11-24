"""
Application principale LIA Coaching
Point d'entrée de l'application FastAPI avec gestion complète du cycle de vie
"""
from __future__ import annotations  # Permet l'utilisation de types forward references

# === IMPORTS STANDARD ===
import logging  # Système de logs Python
import os  # Interface avec le système d'exploitation
import shutil  # Utilitaires pour manipulation de fichiers/dossiers
import subprocess  # Exécution de processus externes (psql)
from datetime import datetime, timezone  # Gestion des dates et heures
from pathlib import Path  # Manipulation des chemins de fichiers

# === IMPORTS FASTAPI ===
import uvicorn  # Serveur ASGI pour FastAPI
from fastapi import FastAPI, Request, Form  # Framework web principal
from fastapi.responses import HTMLResponse, RedirectResponse  # Types de réponses HTTP
from fastapi.middleware.cors import CORSMiddleware  # Middleware pour CORS
from fastapi.staticfiles import StaticFiles  # Servir les fichiers statiques
from fastapi.templating import Jinja2Templates  # Moteur de templates

# === IMPORTS INTERNES - CONFIGURATION ===
from .core.config import settings, BASE_DIR  # Configuration globale de l'app
from .core.path_config import path_config  # Configuration centralisée des chemins
from .core.enum_middleware import add_enum_validation_middleware  # Validation des enums
from .core.database import create_db_and_tables, test_db_connection  # Gestion DB
from .core.middleware import setup_all_middlewares  # Middlewares personnalisés
from .services import UserService  # Service de gestion des utilisateurs
from .routers import router_configs  # Configuration des routes
from .core.program_schema_integration import ProgramSchemaManager  # Schémas par programme

# === IMPORTS INTERNES - BASE DE DONNÉES ===
from .core.database import get_session  # Session de base de données
from sqlmodel import Session  # ORM SQLModel
from fastapi import Depends  # Injection de dépendances

# === IMPORTS INTERNES - MODÈLES ===
from .models.base import Programme  # Modèles principaux
from .models.preinscription import Preinscription
from .models.jury import Jury
from sqlmodel import func  # Fonctions SQL (COUNT, etc.)
from .core.security import authenticate_user, create_access_token  # Authentification
from .core.config import settings  # Configuration (réimport)
from fastapi.security import OAuth2PasswordRequestForm  # Formulaire d'authentification OAuth2
from fastapi import Depends, HTTPException, status  # Gestion des erreurs HTTP

import uuid  # Génération d'identifiants uniques

from .templates import templates # Import du système de templates Jinja2

from starlette.exceptions import HTTPException as StarletteHTTPException  # Exceptions HTTP Starlette

# ============================================================================
# CONFIGURATION DES CHEMINS ET RESSOURCES
# ============================================================================

# Créer les dossiers nécessaires au démarrage de l'application
# Cette fonction s'assure que tous les dossiers requis existent
settings.ensure_directories()

# Récupération des chemins depuis la configuration centralisée
STATIC_DIR = settings.STATIC_DIR  # Dossier des fichiers statiques (CSS, JS, images)
TEMPLATES_DIR = settings.TEMPLATE_DIR  # Dossier des templates Jinja2
STATIC_MAPS_DIR = settings.STATIC_MAPS_DIR  # Dossier des cartes statiques
STATIC_IMAGES_DIR = settings.STATIC_IMAGES_DIR  # Dossier des images statiques
FICHIERS_DIR = settings.FICHIERS_DIR  # Dossier des fichiers uploadés
MEDIA_ROOT = settings.MEDIA_ROOT  # Dossier racine des médias

# Configuration du logger pour les erreurs uvicorn
logger = logging.getLogger("uvicorn.error")

# === CONFIGURATION SQL D'INITIALISATION ===
# Script SQL d'initialisation de la base de données (recommandé: app/core/init_postgres.sql)
SQL_INIT_FILE = (BASE_DIR / "core" / "init_postgres.sql").resolve()
# Fichier sentinelle pour éviter de réexécuter le bootstrap SQL plusieurs fois
DB_BOOTSTRAP_SENTINEL = (BASE_DIR / ".db_bootstrapped").resolve()

# ============================================================================
# CRÉATION DE L'APPLICATION FASTAPI
# ============================================================================

# Instance principale de l'application FastAPI avec configuration complète
app = FastAPI(
    title=settings.APP_NAME,  # Nom de l'application depuis la config
    description="Application de gestion de coaching LIA",  # Description de l'API
    version=settings.VERSION,  # Version de l'application
    docs_url="/docs" if settings.DEBUG else None,  # Documentation Swagger (dev seulement)
    redoc_url="/redoc" if settings.DEBUG else None,  # Documentation ReDoc (dev seulement)
    openapi_url="/openapi.json" if settings.DEBUG else None,  # Schema OpenAPI (dev seulement)
    root_path=getattr(settings, "ROOT_PATH", ""),  # Chemin racine pour reverse proxy
)

# Rendre les settings accessibles dans toute l'application via app.state
app.state.settings = settings

# ============================================================================
# CONFIGURATION DES MIDDLEWARES
# ============================================================================
# Configuration de tous les middlewares personnalisés de l'application
# Ces middlewares gèrent la sécurité, les logs, la validation, etc.

setup_all_middlewares(
    app,  # Instance de l'application FastAPI
    allowed_hosts=getattr(settings, "ALLOWED_HOSTS", ["localhost", "127.0.0.0.1"]),  # Hôtes autorisés
    secret_key=settings.SECRET_KEY,  # Clé secrète pour les sessions/tokens
)

# ============================================================================
# CONFIGURATION CORS (Cross-Origin Resource Sharing)
# ============================================================================

# Configuration des origines autorisées pour les requêtes cross-origin
cors_origins = getattr(settings, "CORS_ORIGINS", [])
# En mode debug, autoriser toutes les origines si aucune n'est spécifiée
if settings.DEBUG and not cors_origins:
    cors_origins = ["*"]

# Middleware CORS commenté - peut être activé si nécessaire
"""app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""

# ============================================================================
# CONFIGURATION DES FICHIERS STATIQUES ET TEMPLATES
# ============================================================================

# Configuration spécifique au mode développement
if settings.DEBUG:
    # Créer automatiquement les sous-dossiers CSS et JS s'ils n'existent pas
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)
    
    # Génération automatique du fichier CSS de thème en mode dev
    theme_css = STATIC_DIR / "css" / "theme.css"
    if not theme_css.exists():
        # Créer un fichier CSS avec les variables de thème depuis la configuration
        theme_css.write_text(
            f"""/* Thème LIA Coaching (dev) */
:root {{ 
    --primary-color: {settings.THEME_PRIMARY}; 
    --secondary-color: {settings.THEME_SECONDARY}; 
    --white-color: {settings.THEME_WHITE}; 
    --gray-light: #f8f9fa; 
    --gray-dark: #343a40; 
}}
body {{ font-family: Segoe UI, Tahoma, Geneva, Verdana, sans-serif; background: var(--gray-light); }}
.navbar-brand {{ color: var(--primary-color) !important; font-weight: 700; }}
.btn-primary {{ background: var(--primary-color); border-color: var(--primary-color); color: var(--secondary-color); }}
.btn-primary:hover {{ background: #e6b800; border-color: #e6b800; color: var(--secondary-color); }}
.card {{ border: none; box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,.075); }}
.card-header {{ background: var(--primary-color); color: var(--secondary-color); font-weight: 700; }}
.text-primary {{ color: var(--primary-color) !important; }}
.bg-primary {{ background: var(--primary-color) !important; color: var(--secondary-color) !important; }}
"""
        )

# ============================================================================
# MONTAGE DES DOSSIERS DE FICHIERS STATIQUES (CONFIGURATION CENTRALISÉE)
# ============================================================================
# Configuration automatique des montures depuis path_config
for mount_name, config in path_config.MOUNT_CONFIGS.items():
    # S'assurer que le répertoire existe
    path_config.ensure_directory_exists(mount_name)
    
    # Monter le répertoire
    app.mount(
        config["path"], 
        StaticFiles(directory=config["directory"], check_dir=True), 
        name=config["name"]
    )
    print(f"✅ Monté: {config['path']} → {config['directory']} (nom: {config['name']})")

# ============================================================================
# FONCTION DE BOOTSTRAP SQL VIA PSQL (IDEMPOTENT)
# ============================================================================

def maybe_bootstrap_database() -> None:
    """
    Exécute init_postgres.sql via psql si présent et non déjà exécuté (sentinelle).
    Cette fonction est idempotente : elle ne s'exécute qu'une seule fois.
    Forcer via settings.DB_INIT_ALWAYS=True pour rejouer à chaque démarrage.
    """
    # Vérifier si on doit forcer l'exécution à chaque démarrage
    run_always = bool(getattr(settings, "DB_INIT_ALWAYS", False))

    # Vérifier si le fichier SQL d'initialisation existe
    if not SQL_INIT_FILE.exists():
        return  # Pas de fichier SQL d'init trouvé, on passe
    
    # Vérifier si le bootstrap a déjà été effectué (fichier sentinelle)
    if DB_BOOTSTRAP_SENTINEL.exists() and not run_always:
        return  # Bootstrap déjà effectué

    # Vérifier que psql est disponible dans le PATH
    psql = shutil.which("psql")
    if not psql:
        return  # psql introuvable, impossible d'exécuter le SQL

# === CONFIGURATION DE LA CONNEXION POSTGRESQL ===
    # Connexion superuser (settings > env > défauts)
    PGHOST = settings.PGHOST
    PGPORT = str(settings.PGPORT)
    PGSUPERUSER = settings.PGSUPERUSER
    PGSUPERPASS = settings.PGSUPERPASS

    # Base applicative cible (settings > env > défauts)
    APP_DBNAME = settings.PGDATABASE
    APP_DBUSER = settings.PGUSER
    APP_DBPASS = settings.PGPASSWORD

    # Configuration de l'environnement pour psql
    env = os.environ.copy()
    env["PGOPTIONS"] = "-c client_encoding=UTF8 -c lc_messages=C"  # Encodage UTF-8
    env["PGPASSWORD"] = PGSUPERPASS  # Évite le prompt de mot de passe

    # Construction de la commande psql
    cmd = [
        psql,
        "-U", PGSUPERUSER,  # Utilisateur superuser
        "-h", PGHOST,       # Hôte PostgreSQL
        "-p", PGPORT,       # Port PostgreSQL
        "-d", "postgres",   # Base de données cible (postgres par défaut)
        "-v", f"dbname={APP_DBNAME}",    # Variable pour le nom de la DB app
        "-v", f"appuser={APP_DBUSER}",   # Variable pour l'utilisateur app
        "-v", f"apppass={APP_DBPASS}",   # Variable pour le mot de passe app
        "-f", str(SQL_INIT_FILE),        # Fichier SQL à exécuter
    ]

    # Exécution de la commande psql
    try:
        res = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        # Créer le fichier sentinelle pour marquer que le bootstrap est terminé
        DB_BOOTSTRAP_SENTINEL.write_text(datetime.now(timezone.utc).isoformat() + "Z")
    except subprocess.CalledProcessError as e:
        # En cas d'erreur, on peut décider de lever une exception ou continuer
        pass

# ============================================================================
# FONCTION DE VÉRIFICATION DE L'ADMINISTRATEUR
# ============================================================================

def ensure_admin_user():
    """
    Vérifie et crée l'administrateur par défaut si nécessaire.
    Cette fonction s'assure qu'il existe au moins un utilisateur administrateur.
    """
    try:
        # Créer une session de base de données
        from .core.database import get_session
        session = next(get_session())
        
        # Utiliser le service utilisateur pour vérifier/créer l'admin
        success = UserService.ensure_admin_exists(session)
        
        # Fermer la session
        session.close()
        return success
        
    except Exception as e:
        # En cas d'erreur, retourner False
        return False

# ============================================================================
# CONFIGURATION DES SCHÉMAS PAR PROGRAMME (AVANT STARTUP)
# ============================================================================

# ============================================================================
# CONFIGURATION DES ROUTERS API & WEB
# ============================================================================

# Import des exceptions HTTP pour la gestion d'erreurs
from fastapi.exceptions import HTTPException

# Inclusion de tous les routers depuis la configuration organisée
# Chaque router est inclus avec son préfixe et ses tags
for router, prefix, tags in router_configs:
    app.include_router(router, prefix=prefix, tags=tags)

# ============================================================================
# ROUTE DEBUG POUR AFFICHER TOUS LES ROUTERS
# ============================================================================

@app.get("/debug/routers")
def debug_routers():
    """Affiche tous les routers inclus dans l'application"""
    routers_info = []
    for router, prefix, tags in router_configs:
        router_name = router.__class__.__name__
        routes = []
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, 'name', None)
                })
        
        routers_info.append({
            "router_name": router_name,
            "prefix": prefix,
            "tags": tags,
            "routes": routes,
            "routes_count": len(routes)
        })
    
    return {
        "total_routers": len(router_configs),
        "routers": routers_info
    }

# ============================================================================
# ROUTE GLOBALE POUR SERVIR LES FICHIERS UPLOADÉS
# ============================================================================

@app.get("/media/{file_path:path}", name="serve_uploaded_file")
async def serve_uploaded_file(file_path: str):
    """
    Route globale pour servir les fichiers uploadés et médias.
    - Les fichiers (PDF, Word, etc.) sont dans uploads/
    - Les médias (images, vidéos, MP3, etc.) sont dans media/
    Utilise FileUploadService qui gère path_config de manière centralisée.
    Supporte les anciens et nouveaux formats de chemin.
    """
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    import mimetypes
    
    # Normaliser les séparateurs de chemin (Windows utilise \ mais on stocke avec /)
    file_path = file_path.replace('\\', '/')
    
    # Utiliser FileUploadService pour servir les fichiers
    from .services.file_upload_service import FileUploadService
    
    # Essayer d'abord de servir depuis media/ (nouveaux médias)
    try:
        return FileUploadService.serve_media_file(file_path)
    except HTTPException as e:
        # Si le fichier n'existe pas dans media/, essayer uploads/ (anciens fichiers)
        if e.status_code == 404:
            try:
                return FileUploadService.serve_file(file_path)
            except HTTPException as e2:
                # Si toujours pas trouvé, essayer l'ancien format (media_root)
                if e2.status_code == 404:
                    media_root = settings.MEDIA_ROOT
                    if media_root and media_root.exists():
                        # Essayer avec le chemin direct dans media_root
                        old_path = media_root / file_path
                        if old_path.exists():
                            # Vérifier la sécurité
                            try:
                                old_path.resolve().relative_to(media_root.resolve())
                            except ValueError:
                                raise HTTPException(status_code=403, detail="Accès non autorisé")
                            
                            # Déterminer le type MIME
                            mime_type, _ = mimetypes.guess_type(str(old_path))
                            
                            print(f"✅ Fichier trouvé dans l'ancien emplacement: {old_path}")
                            return FileResponse(
                                path=str(old_path),
                                media_type=mime_type or "application/octet-stream",
                                filename=old_path.name
                            )
                        else:
                            # Essayer une recherche récursive par nom de fichier dans media_root/Preinscrits
                            parts = file_path.split('/')
                            if len(parts) >= 3 and parts[0] == 'Preinscrits':
                                search_dir = media_root / "Preinscrits"
                                if search_dir.exists():
                                    filename = parts[-1]  # Nom du fichier
                                    # Chercher récursivement
                                    for found_file in search_dir.rglob(filename):
                                        if found_file.is_file():
                                            # Vérifier la sécurité
                                            try:
                                                found_file.resolve().relative_to(media_root.resolve())
                                            except ValueError:
                                                continue
                                            
                                            # Déterminer le type MIME
                                            mime_type, _ = mimetypes.guess_type(str(found_file))
                                            
                                            print(f"✅ Fichier trouvé dans l'ancien emplacement (recherche récursive): {found_file}")
                                            return FileResponse(
                                                path=str(found_file),
                                                media_type=mime_type or "application/octet-stream",
                                                filename=found_file.name
                                            )
                    
                    # Si toujours pas trouvé, afficher les logs de debug
                    print(f"🔍 Fichier non trouvé dans media/: {path_config.MEDIA_DIR / file_path}")
                    print(f"🔍 Fichier non trouvé dans uploads/: {path_config.UPLOAD_DIR / file_path}")
                    print(f"🔍 Chemin recherché: {file_path}")
                    print(f"🔍 MEDIA_DIR: {path_config.MEDIA_DIR}")
                    print(f"🔍 UPLOAD_DIR: {path_config.UPLOAD_DIR}")
                    print(f"🔍 MEDIA_ROOT: {media_root}")
                    raise HTTPException(status_code=404, detail="Fichier non trouvé")
                else:
                    # Répercuter les autres erreurs HTTP (403, etc.)
                    raise
        else:
            # Répercuter les autres erreurs HTTP (403, etc.)
            raise

# ============================================================================
# GESTION DU CYCLE DE VIE DE L'APPLICATION (STARTUP)
# ============================================================================

@app.on_event("startup")
async def on_startup():
    """
    Fonction appelée au démarrage de l'application FastAPI.
    Cette fonction orchestre toutes les étapes d'initialisation :
    1. Bootstrap SQL
    2. Test de connexion DB
    3. Création des tables ORM
    4. Création des schémas par programme et leurs tables
    5. Migration automatique (ajout des colonnes manquantes)
    6. Vérification administrateur
    """
    print("=" * 60)
    print("🚀 DÉMARRAGE DE L'APPLICATION")
    print("=" * 60)
    
    # === ÉTAPE 1: BOOTSTRAP SQL AVANT LA CRÉATION DES TABLES ORM ===
    print("📋 ÉTAPE 1: Bootstrap SQL")
    maybe_bootstrap_database()  # Exécuter le script SQL d'initialisation
    print("✅ ÉTAPE 1 TERMINÉE: Bootstrap SQL")

    # === ÉTAPE 2: TEST DE CONNEXION À LA BASE DE DONNÉES ===
    print("📋 ÉTAPE 2: Test de connexion DB")
    print("✅", settings.DATABASE_URL)  # Afficher l'URL de connexion
    try:
        test_db_connection()  # Tester la connexion à PostgreSQL
        print("✅ ÉTAPE 2 TERMINÉE: Connexion DB OK")
    except Exception as e:
        print(f"❌ ÉTAPE 2 ÉCHEC: Connexion DB - {e}")
        pass  # Continuer même en cas d'erreur

    # === ÉTAPE 3: CRÉATION DES TABLES ORM DANS LE SCHÉMA PUBLIC (AVEC MIGRATION) ===
    print("📋 ÉTAPE 3: Création des tables ORM et migration automatique")
    try:
        create_db_and_tables()  # Créer toutes les tables SQLModel du schéma public et migrer les colonnes
    except Exception as e:
        print(f"❌ ÉTAPE 3 ÉCHEC: Création des tables ORM - {e}")
        import traceback
        print(traceback.format_exc())

    print("✅ ÉTAPE 3 TERMINÉE: Tables ORM créées et migrées")
    
    # === ÉTAPE 4: CRÉATION DES SCHÉMAS PAR PROGRAMME ET LEURS TABLES ===
    print("📋 ÉTAPE 4: Création des schémas par programme et leurs tables")
    try:
        from .core.database import create_program_schemas_and_tables
        create_program_schemas_and_tables()  # Créer les schémas et tables pour chaque programme
        print("✅ ÉTAPE 4 TERMINÉE: Schémas par programme créés")
    except Exception as e:
        print(f"❌ ÉTAPE 4 ÉCHEC: Création des schémas par programme - {e}")
        import traceback
        print(traceback.format_exc())
    
    # === ÉTAPE 5: VÉRIFICATION ET CRÉATION DE L'ADMINISTRATEUR ===
    print("📋 ÉTAPE 5: Vérification administrateur")
    ensure_admin_user()  # S'assurer qu'un admin existe
    print("✅ ÉTAPE 5 TERMINÉE: Administrateur vérifié")
    
    print("=" * 60)
    print("🎉 DÉMARRAGE DE L'APPLICATION TERMINÉ")
    print("=" * 60)

# ============================================================================
# ROUTES PRINCIPALES DE L'APPLICATION
# ============================================================================

@app.get("/")
async def root_get(request: Request):
    """
    Page d'accueil - affiche la page de connexion.
    Cette route sert le template de login avec les informations de l'application.
    """
    print("✅", TEMPLATES_DIR)  # Debug: afficher le chemin des templates
    return templates.TemplateResponse(
        "auth/login.html",  # Template de connexion
        {
            "request": request, 
            "app_name": settings.APP_NAME, 
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "settings": settings
        }
    )

# === IMPORTS POUR LES ROUTES D'AUTHENTIFICATION ===
from fastapi.exceptions import HTTPException
from fastapi import status
from .core.security import get_current_user
from .models.base import User, Programme
from .models.enums import UserRole
from .models.preinscription import Preinscription
from .models.jury import Jury
from .core.database import get_session
from .schemas import UserResponse
from sqlmodel import select, func


@app.get("/auth/logout")
async def logout(request: Request):
    """
    Route de déconnexion - supprime le cookie d'authentification.
    Redirige vers la page de connexion après déconnexion.
    """
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="access_token")  # Supprimer le cookie d'authentification
    return response

@app.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """
    Authentification utilisateur - traitement du formulaire de connexion.
    Cette route gère l'authentification et la création du token d'accès.
    """
    # Authentifier l'utilisateur avec email et mot de passe
    user = authenticate_user(session, form_data.username, form_data.password)
    
    if not user:
        # Identifiants incorrects - retourner le template avec message d'erreur
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                # current_year est déjà défini comme fonction globale dans templates
                "settings": settings,
                "error": "Email ou mot de passe incorrect"
            }
        )
    
    # Créer le token d'accès JWT avec les informations utilisateur
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}
    )

    # Récupérer le paramètre "remember" depuis les données du formulaire
    form_data_dict = await request.form()
    remember_me = form_data_dict.get("remember-me") == "on"
    
    # === GESTION DE LA DURÉE DU COOKIE ===
    if remember_me:
        # Cookie persistant pour 30 jours
        max_age = 30 * 24 * 60 * 60  # 30 jours en secondes
    else:
        # Cookie de session (expire à la fermeture du navigateur)
        max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # Créer la réponse de redirection avec le cookie d'authentification
    response = RedirectResponse(url="/accueil", status_code=302)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,  # Cookie accessible seulement via HTTP (sécurité)
        max_age=max_age,
        secure=False,  # True en production avec HTTPS
        samesite="lax"  # Protection CSRF
    )
    
    return response

async def root_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False),
    session: Session = Depends(get_session)
):
    """
    Traitement de la connexion (route alternative).
    Cette fonction utilise le UserService pour vérifier les identifiants admin.
    """
    try:
        # Vérifier les identifiants administrateur
        if UserService.verify_admin_credentials(session, email, password):
            # Connexion réussie - rediriger vers le dashboard admin
            return RedirectResponse(url="/admin", status_code=302)
        else:
            # Identifiants incorrects - afficher le template avec erreur
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    # current_year est déjà défini comme fonction globale dans templates
                    "settings": settings,
                    "error": "Email ou mot de passe incorrect"
                }
            )
    except Exception as e:
        # En cas d'erreur système - afficher le template avec erreur générique
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                # current_year est déjà défini comme fonction globale dans templates
                "settings": settings,
                "error": "Erreur lors de la connexion"
            }
        )

@app.get("/health")
async def health_check():
    """
    Route de vérification de santé de l'application.
    Cette route est utilisée pour les health checks et monitoring.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "time": datetime.now(timezone.utc).isoformat() + "Z",
    }

# ============================================================================
# GESTIONNAIRES D'ERREURS ET PAGES D'ERREUR
# ============================================================================

def register_error_handlers(app):
    """
    Enregistre les gestionnaires d'erreurs personnalisés pour l'application.
    Ces gestionnaires interceptent les erreurs HTTP et les exceptions non gérées.
    """
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Gestionnaire pour les erreurs HTTP (404, 500, etc.).
        Affiche des pages d'erreur personnalisées avec des templates.
        """
        if exc.status_code == 404:
            # Page 404 - Ressource non trouvée
            return templates.TemplateResponse(
                "404.html",
                {
                    "request": request, 
                    "code": 404, 
                    "message": "La page demandée est introuvable.", 
                    "path": request.url.path
                },
                status_code=404,
            )
        elif exc.status_code == 500:
            # Page 500 - Erreur serveur interne
            # Générer un ID de corrélation pour le support technique
            incident_id = str(uuid.uuid4())[:8]
            
            return templates.TemplateResponse(
                "500.html",
                {
                    "request": request,
                    "incident_id": incident_id,  # ID pour le support
                    "path": request.url.path,
                    "now": datetime.now().strftime("%d/%m/%Y %H:%M"),
                },
                status_code=500,
            )
        # Pour les autres erreurs HTTP (403, etc.), utiliser la réponse par défaut
        return HTMLResponse(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        Gestionnaire pour les exceptions non gérées.
        Capture toutes les erreurs non interceptées et affiche une page 500.
        """
        # Générer un ID de corrélation pour le support technique
        incident_id = str(uuid.uuid4())[:8]

        return templates.TemplateResponse(
            "500.html",
            {
                "request": request,
                "incident_id": incident_id,  # ID pour le support
                "path": request.url.path,
                "now": datetime.now().strftime("%d/%m/%Y %H:%M"),
            },
            status_code=500,
        )
    
# Enregistrer les gestionnaires d'erreurs
register_error_handlers(app)


# ============================================================================
# CONFIGURATION DU SERVEUR DE DÉVELOPPEMENT
# ============================================================================

# Configuration Cloudflare Tunnel (commentée)
# from cloudflare_tunnel import start_cloudflared
# start_cloudflared()

# Point d'entrée pour l'exécution locale en mode développement
if __name__ == "__main__":
    """
    Configuration du serveur uvicorn pour le développement local.
    Cette section ne s'exécute que si le fichier est lancé directement.
    """
    uvicorn.run(
        "app.main:app",  # Module et application FastAPI (relatif depuis app_lia_web)
        host="0.0.0.0",             # Écouter sur toutes les interfaces
        port=8000,                  # Port par défaut
        reload=False, #bool(settings.DEBUG), # Rechargement automatique en mode debug
        log_level="info",           # Niveau de log
    )
   
