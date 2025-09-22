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
from app_lia_web.core.config import settings, BASE_DIR  # Configuration globale de l'app
from app_lia_web.core.path_config import path_config  # Configuration centralisée des chemins
from app_lia_web.core.enum_middleware import add_enum_validation_middleware  # Validation des enums
from app_lia_web.core.database import create_db_and_tables, test_db_connection  # Gestion DB
from app_lia_web.core.middleware import setup_all_middlewares  # Middlewares personnalisés
from app_lia_web.app.services import UserService  # Service de gestion des utilisateurs
from app_lia_web.app.services.database_migration import DatabaseMigrationService  # Migrations DB
from app_lia_web.app.routers import router_configs  # Configuration des routes
from app_lia_web.core.program_schema_integration import setup_program_schemas, ProgramSchemaManager  # Schémas par programme

# === IMPORTS INTERNES - BASE DE DONNÉES ===
from app_lia_web.core.database import get_session  # Session de base de données
from sqlmodel import Session  # ORM SQLModel
from fastapi import Depends  # Injection de dépendances

# === IMPORTS INTERNES - MODÈLES ===
from app_lia_web.app.models.base import Programme, Preinscription, Inscription, Jury  # Modèles principaux
from sqlmodel import func  # Fonctions SQL (COUNT, etc.)
from app_lia_web.core.security import authenticate_user, create_access_token  # Authentification
from app_lia_web.core.config import settings  # Configuration (réimport)
from fastapi.security import OAuth2PasswordRequestForm  # Formulaire d'authentification OAuth2
from fastapi import Depends, HTTPException, status  # Gestion des erreurs HTTP

import uuid  # Génération d'identifiants uniques

from app_lia_web.app.templates import templates # Import du système de templates Jinja2

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

# Configuration du système de schémas par programme
# Cette fonction configure le middleware et les routes pour la gestion des schémas
# DOIT être appelé AVANT setup_all_middlewares pour que SessionMiddleware soit disponible
setup_program_schemas(app)

# Configuration de tous les middlewares personnalisés de l'application
# Ces middlewares gèrent la sécurité, les logs, la validation, etc.
setup_all_middlewares(
    app,  # Instance de l'application FastAPI
    allowed_hosts=getattr(settings, "ALLOWED_HOSTS", ["localhost", "127.0.0.1"]),  # Hôtes autorisés
    secret_key=settings.SECRET_KEY,  # Clé secrète pour les sessions/tokens
)

# Ajout du middleware de validation des enums au démarrage
# Ce middleware valide automatiquement les valeurs d'enum dans les requêtes
enum_middleware = add_enum_validation_middleware(app)

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
        from app_lia_web.core.database import get_session
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
# ROUTE GLOBALE POUR SERVIR LES FICHIERS UPLOADÉS
# ============================================================================

@app.get("/media/{file_path:path}", name="serve_uploaded_file")
async def serve_uploaded_file(file_path: str):
    """
    Route globale pour servir les fichiers uploadés (photos de profil, documents, etc.).
    Cette route gère la sécurité et le type MIME des fichiers.
    """
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    import mimetypes
    
    # Construire le chemin complet vers le fichier
    full_path = Path(settings.UPLOAD_DIR) / file_path
    
    # Vérifier que le fichier existe
    if not full_path.exists():
        print(f"🔍 Fichier non trouvé: {full_path}")
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    # Vérifier que le fichier est dans le dossier uploads (sécurité contre path traversal)
    try:
        full_path.resolve().relative_to(Path(settings.UPLOAD_DIR).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Déterminer le type MIME du fichier
    mime_type, _ = mimetypes.guess_type(str(full_path))
    
    # Retourner le fichier avec le bon type MIME
    return FileResponse(
        path=str(full_path),
        media_type=mime_type or "application/octet-stream",
        filename=full_path.name
    )

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
    4. Migration automatique
    5. Vérification administrateur
    6. Création des schémas par programme
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

    # === ÉTAPE 3: CRÉATION DES TABLES ORM DANS LE SCHÉMA PUBLIC ===
    print("📋 ÉTAPE 3: Création des tables ORM")
    create_db_and_tables()  # Créer toutes les tables SQLModel
    print("✅ ÉTAPE 3 TERMINÉE: Tables ORM créées")
    
    # === ÉTAPE 4: MIGRATION AUTOMATIQUE DE LA BASE DE DONNÉES ===
    print("📋 ÉTAPE 4: Migration automatique")
    try:
        # Créer une session et le service de migration
        session = next(get_session())
        migration_service = DatabaseMigrationService(session)
        
        # Effectuer la migration automatique
        migration_results = migration_service.migrate_database()
        
        # Afficher les résultats de la migration
        if migration_results["enums_updated"]:
            print(f"📝 Enums mis à jour: {migration_results['enums_updated']}")
        if migration_results["tables_created"]:
            print(f"📋 Tables créées: {migration_results['tables_created']}")
        if migration_results["columns_added"]:
            print(f"🔧 Colonnes ajoutées: {migration_results['columns_added']}")
        if migration_results["errors"]:
            print(f"⚠️ Erreurs de migration: {migration_results['errors']}")
        else:
            print("✅ Migration automatique terminée avec succès")
            
        print("✅ ÉTAPE 4 TERMINÉE: Migration automatique")
            
    except Exception as e:
        print(f"❌ ÉTAPE 4 ÉCHEC: Migration automatique - {e}")
        pass  # Continuer même en cas d'erreur
    
    # === ÉTAPE 5: VÉRIFICATION ET CRÉATION DE L'ADMINISTRATEUR ===
    print("📋 ÉTAPE 5: Vérification administrateur")
    ensure_admin_user()  # S'assurer qu'un admin existe
    print("✅ ÉTAPE 5 TERMINÉE: Administrateur vérifié")
    
    # === ÉTAPE 6: CRÉATION DES SCHÉMAS PAR PROGRAMME ===
    print("📋 ÉTAPE 6: Création des schémas par programme")
    try:
        print("🚀 Début de l'initialisation des schémas par programme")
        
        # ÉTAPE 6.1: Créer une session et un manager
        print("📋 ÉTAPE 6.1: Création session et manager")
        session = next(get_session())
        manager = ProgramSchemaManager()  # Manager pour les schémas
        manager.session = session
        print("✅ ÉTAPE 6.1 TERMINÉE: Session et manager créés")
        
        # ÉTAPE 6.2: Récupérer les programmes actifs
        print("📋 ÉTAPE 6.2: Récupération des programmes actifs")
        from app_lia_web.app.models.base import Programme
        from sqlmodel import select
        programmes = session.exec(
            select(Programme).where(Programme.actif == True)  # Seulement les programmes actifs
        ).all()
        print(f"📋 Programmes trouvés: {[p.code for p in programmes]}")
        print("✅ ÉTAPE 6.2 TERMINÉE: Programmes récupérés")
        
        # ÉTAPE 6.3: Créer les schémas pour chaque programme
        print("📋 ÉTAPE 6.3: Création des schémas individuels")
        for programme in programmes:
            print(f"🔍 Traitement du programme: {programme.code}")
            
            # ÉTAPE 6.3.1: Vérifier si le schéma existe
            print(f"📋 ÉTAPE 6.3.1: Vérification existence schéma {programme.code}")
            schema_exists = manager.schema_exists(programme.code)
            
            if not schema_exists:
                print(f"🔨 Création du schéma pour le programme {programme.code}")
                success = manager.create_program_schema(programme.code)
                if success:
                    print(f"✅ Schéma {programme.code} créé avec succès")
                else:
                    print(f"❌ Échec de création du schéma {programme.code}")
            else:
                print(f"ℹ️ Schéma {programme.code} existe déjà")
                print(f"🔨 Vérification et création des tables dans le schéma {programme.code}")
                # Créer les tables même si le schéma existe déjà
                manager._create_tables_in_schema(programme.code.lower())
        
        print("✅ ÉTAPE 6.3 TERMINÉE: Schémas individuels traités")
        
        # ÉTAPE 6.4: Fermer la session
        print("📋 ÉTAPE 6.4: Fermeture de la session")
        session.close()
        print("✅ ÉTAPE 6.4 TERMINÉE: Session fermée")
        
        print("🎉 Initialisation des schémas par programme terminée")
        print("✅ ÉTAPE 6 TERMINÉE: Création des schémas par programme")
        
    except Exception as e:
        print(f"❌ ÉTAPE 6 ÉCHEC: Création des schémas - {e}")
        import traceback
        print(traceback.format_exc())
    
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
        "login.html",  # Template de connexion
        {
            "request": request, 
            "app_name": settings.APP_NAME, 
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "current_year": datetime.now().year,
            "settings": settings
        }
    )

# === IMPORTS POUR LES ROUTES D'AUTHENTIFICATION ===
from fastapi.exceptions import HTTPException
from fastapi import status
from app_lia_web.core.security import get_current_user
from app_lia_web.app.models.base import User
from app_lia_web.app.models.enums import UserRole
from app_lia_web.app.models.base import Programme, Preinscription, Inscription, Jury
from app_lia_web.core.database import get_session
from app_lia_web.app.schemas import UserResponse
from sqlmodel import select, func

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Page d'administration - Dashboard principal pour les administrateurs.
    Cette route affiche les KPIs et la liste des utilisateurs.
    """
    # Vérifier les permissions - seuls les admins et directeurs techniques peuvent accéder
    if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé"
        )
    
    # === CALCUL DES KPIs (Key Performance Indicators) ===
    nb_prog = session.exec(select(func.count()).select_from(Programme)).one()  # Nombre de programmes
    nb_pre = session.exec(select(func.count()).select_from(Preinscription)).one()  # Nombre de préinscriptions
    nb_insc = session.exec(select(func.count()).select_from(Inscription)).one()  # Nombre d'inscriptions
    nb_jury = session.exec(select(func.count()).select_from(Jury)).one()  # Nombre de jurys

    # === RÉCUPÉRATION DES UTILISATEURS ===
    # Récupérer tous les utilisateurs depuis la base de données
    all_users = session.exec(select(User)).all()
    users_data = [UserResponse.from_orm(user) for user in all_users]

    # Retourner le template admin avec toutes les données
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "titre": "Administration",
            "utilisateur": UserResponse.from_orm(current_user),
            "roles": [current_user.role],
            
            # KPIs pour le dashboard
            "kpi": {
                "programmes": nb_prog,
                "preinscriptions": nb_pre,
                "inscriptions": nb_insc,
                "jurys": nb_jury,
            },
            "users": users_data,  # Liste réelle des utilisateurs
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "current_year": datetime.now().year,
            "settings": settings
        }
    )

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
            "login.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                "current_year": datetime.now().year,
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
                "login.html",
                {
                    "request": request,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    "current_year": datetime.now().year,
                    "settings": settings,
                    "error": "Email ou mot de passe incorrect"
                }
            )
    except Exception as e:
        # En cas d'erreur système - afficher le template avec erreur générique
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                "current_year": datetime.now().year,
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
        "app_lia_web.app.main:app",  # Module et application FastAPI
        host="0.0.0.0",             # Écouter sur toutes les interfaces
        port=8000,                  # Port par défaut
        reload=bool(settings.DEBUG), # Rechargement automatique en mode debug
        log_level="info",           # Niveau de log
    )
   
