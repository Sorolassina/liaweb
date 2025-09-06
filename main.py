"""
Application principale LIA Coaching
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


from .core.config import settings
from .core.database import create_db_and_tables, test_db_connection
from .core.middleware import setup_all_middlewares
from .services import UserService
from .services.database_migration import DatabaseMigrationService
from .routers import router_configs

from .core.database import get_session
from sqlmodel import Session
from fastapi import Depends

import uuid 

from starlette.exceptions import HTTPException as StarletteHTTPException

# ----------------------------
# Chemins project/ressources
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent               # .../app
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Script SQL d'init (recommandé: app/core/init_postgres.sql)
SQL_INIT_FILE = (BASE_DIR / "core" / "init_postgres.sql").resolve()
DB_BOOTSTRAP_SENTINEL = (BASE_DIR / ".db_bootstrapped").resolve()

logger = logging.getLogger("uvicorn.error")
logger.info("📁 BASE_DIR        = %s", BASE_DIR)
logger.info("📄 SQL_INIT_FILE   = %s (exists=%s)", SQL_INIT_FILE, SQL_INIT_FILE.exists())
logger.info("🔖 SENTINEL        = %s (exists=%s)", DB_BOOTSTRAP_SENTINEL, DB_BOOTSTRAP_SENTINEL.exists())

# ----------------------------
# App FastAPI
# ----------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="Application de gestion de coaching LIA",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    root_path=getattr(settings, "ROOT_PATH", ""),
)

# Settings accessibles partout
app.state.settings = settings

# ----------------------------
# Middlewares "maison"
# ----------------------------
setup_all_middlewares(
    app,
    allowed_hosts=getattr(settings, "ALLOWED_HOSTS", ["localhost", "127.0.0.1"]),
    secret_key=settings.SECRET_KEY,
)

# ----------------------------
# CORS
# ----------------------------
cors_origins = getattr(settings, "CORS_ORIGINS", [])
if settings.DEBUG and not cors_origins:
    cors_origins = ["*"]

"""app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""
# ----------------------------
# Static & Templates
# ----------------------------
if settings.DEBUG:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)
    theme_css = STATIC_DIR / "css" / "theme.css"
    if not theme_css.exists():
        theme_css.write_text(
            """/* Thème LIA Coaching (dev) */
:root { --primary-color: rgb(255,211,0); --secondary-color:#000; --white-color:#fff; --gray-light:#f8f9fa; --gray-dark:#343a40; }
body { font-family:Segoe UI, Tahoma, Geneva, Verdana, sans-serif; background:var(--gray-light); }
.navbar-brand { color: var(--primary-color) !important; font-weight:700; }
.btn-primary { background:var(--primary-color); border-color:var(--primary-color); color:var(--secondary-color); }
.btn-primary:hover { background:#e6b800; border-color:#e6b800; color:var(--secondary-color); }
.card { border:none; box-shadow:0 0.125rem 0.25rem rgba(0,0,0,.075); }
.card-header { background:var(--primary-color); color:var(--secondary-color); font-weight:700; }
.text-primary { color:var(--primary-color) !important; }
.bg-primary { background:var(--primary-color) !important; color:var(--secondary-color) !important; }
"""
        )

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=True), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.auto_reload = bool(settings.DEBUG)
templates.env.globals.update(
    app_name=settings.APP_NAME,
    app_version=settings.VERSION,
    is_debug=settings.DEBUG,
)

Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")

# ----------------------------
# Bootstrap SQL via psql (idempotent)
# ----------------------------
def maybe_bootstrap_database() -> None:
    """
    Exécute init_postgres.sql via psql si présent et non déjà exécuté (sentinelle).
    Forcer via settings.DB_INIT_ALWAYS=True pour rejouer à chaque démarrage.
    """
    run_always = bool(getattr(settings, "DB_INIT_ALWAYS", False))

    if not SQL_INIT_FILE.exists():
        logger.info("⏭️ Aucun fichier SQL d'init trouvé (%s) — on passe.", SQL_INIT_FILE)
        return
    if DB_BOOTSTRAP_SENTINEL.exists() and not run_always:
        logger.info("✅ Bootstrap DB déjà effectué (sentinelle trouvée).")
        return

    psql = shutil.which("psql")
    if not psql:
        logger.warning("⚠️ psql introuvable dans le PATH — impossible d'exécuter le SQL.")
        return

    # Connexion superuser (settings > env > défauts)
    PGHOST = getattr(settings, "PGHOST", os.getenv("PGHOST", "localhost"))
    PGPORT = str(getattr(settings, "PGPORT", os.getenv("PGPORT", "5432")))
    PGSUPERUSER = getattr(settings, "PGSUPERUSER", os.getenv("PGSUPERUSER", "postgres"))
    PGSUPERPASS = getattr(settings, "PGSUPERPASS", os.getenv("PGSUPERPASS", "postgres"))

    # Base applicative cible (settings > env > défauts)
    APP_DBNAME = getattr(settings, "PGDATABASE", os.getenv("PGDATABASE", "liacoaching"))
    APP_DBUSER = getattr(settings, "PGUSER", os.getenv("PGUSER", "liauser"))
    APP_DBPASS = getattr(settings, "PGPASSWORD", os.getenv("PGPASSWORD", "liapass123"))

    env = os.environ.copy()
    env["PGOPTIONS"] = "-c client_encoding=UTF8 -c lc_messages=C"
    env["PGPASSWORD"] = PGSUPERPASS  # évite le prompt

    cmd = [
        psql,
        "-U",
        PGSUPERUSER,
        "-h",
        PGHOST,
        "-p",
        PGPORT,
        "-d",
        "postgres",
        "-v",
        f"dbname={APP_DBNAME}",
        "-v",
        f"appuser={APP_DBUSER}",
        "-v",
        f"apppass={APP_DBPASS}",
        "-f",
        str(SQL_INIT_FILE),
    ]

    logger.info("🛠️ Exécution du bootstrap SQL: %s", SQL_INIT_FILE)
    try:
        res = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        if res.stdout:
            logger.info("psql stdout:\n%s", res.stdout.strip())
        if res.stderr:
            logger.info("psql stderr:\n%s", res.stderr.strip())
        DB_BOOTSTRAP_SENTINEL.write_text(datetime.now(timezone.utc).isoformat() + "Z")
        logger.info("🎉 Bootstrap DB OK (sentinelle créée: %s)", DB_BOOTSTRAP_SENTINEL)
    except subprocess.CalledProcessError as e:
        logger.error("❌ Échec bootstrap SQL (code=%s)", e.returncode)
        logger.error("cmd: %s", " ".join(cmd))
        if e.stdout:
            logger.error("stdout:\n%s", e.stdout)
        if e.stderr:
            logger.error("stderr:\n%s", e.stderr)
        # à toi de décider si tu veux raise pour stopper l'app

def ensure_admin_user():
    """Vérifie et crée l'administrateur si nécessaire"""
    try:
        from .core.database import get_session
        session = next(get_session())
        
        success = UserService.ensure_admin_exists(session)
        
        if success:
            logger.info("✅ Vérification de l'administrateur terminée")
        else:
            logger.warning("⚠️ Problème avec la vérification de l'administrateur")
        
        session.close()
        return success
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification de l'administrateur: {e}")
        return False

# ----------------------------
# Routers API & Web
# ----------------------------
# Inclure tous les routers depuis la configuration organisée

from fastapi.exceptions import HTTPException

for router, prefix, tags in router_configs:
    app.include_router(router, prefix=prefix, tags=tags)

# ----------------------------
# Lifecycle
# ----------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("🚀 Démarrage de %s v%s", settings.APP_NAME, settings.VERSION)
    logger.info("📊 Base de données: %s", settings.DATABASE_URL)

    # Bootstrap SQL avant la création des tables ORM
    maybe_bootstrap_database()

    print("✅",settings.DATABASE_URL)
    try :
        test_db_connection()
    except Exception as e:
        logger.error(f"❌ Erreur lors de la connexion à la base de données: {e}")
        logger.info("💡 Merci de que votre base de données soit configurée correctement...")

    create_db_and_tables()
    logger.info("✅ Base de données initialisée")
    
    # Migration automatique de la base de données
    try:
        logger.info("🔄 Début de la migration automatique...")
        session = next(get_session())
        migration_service = DatabaseMigrationService(session)
        
        # Effectuer la migration
        migration_results = migration_service.migrate_database()
        
        # Afficher les résultats
        if migration_results["enums_updated"]:
            logger.info(f"📝 Enums mis à jour: {migration_results['enums_updated']}")
        
        if migration_results["tables_created"]:
            logger.info(f"📋 Tables créées: {migration_results['tables_created']}")
            
        if migration_results["columns_added"]:
            logger.info(f"🔧 Colonnes ajoutées: {migration_results['columns_added']}")
            
        if migration_results["errors"]:
            logger.warning(f"⚠️ Erreurs de migration: {migration_results['errors']}")
        else:
            logger.info("✅ Migration automatique terminée avec succès")
            
        # Afficher le statut de la base de données
        if settings.DEBUG:
            db_status = migration_service.get_database_status()
            logger.info(f"📊 Statut de la base de données: {len(db_status.get('tables', []))} tables, {len(db_status.get('enums', {}))} enums")
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration automatique: {e}")
        logger.warning("⚠️ L'application continue sans migration automatique")
    
    # Vérifier et créer l'administrateur si nécessaire
    ensure_admin_user()

# ----------------------------
# Routes
# ----------------------------


@app.get("/")
async def root_get(request: Request):
    """Page d'accueil - affiche la page de connexion"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request, 
            "app_name": settings.APP_NAME, 
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "current_year": datetime.now().year,
            "settings": settings
        }
    )

from fastapi.exceptions import HTTPException
from fastapi import status
from .core.security import get_current_user
from .models.base import User
from .models.enums import UserRole
from .models.base import Programme, Preinscription, Inscription, Jury
from .core.database import get_session
from .schemas import UserResponse
from sqlmodel import select, func

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page d'administration"""
    # Vérifier les permissions
    if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé"
        )
    
    # KPIs
    nb_prog = session.exec(select(func.count()).select_from(Programme)).one()
    nb_pre = session.exec(select(func.count()).select_from(Preinscription)).one()
    nb_insc = session.exec(select(func.count()).select_from(Inscription)).one()
    nb_jury = session.exec(select(func.count()).select_from(Jury)).one()

    # Récupérer tous les utilisateurs depuis la base de données
    all_users = session.exec(select(User)).all()
    users_data = [UserResponse.from_orm(user) for user in all_users]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "titre": "Administration",
            "utilisateur": UserResponse.from_orm(current_user),
            "roles": [current_user.role],
            
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

@router.get("/logout")
async def logout(request: Request):
    """Déconnexion"""
    return RedirectResponse(url="/", status_code=302)

from .models.base import Programme, Preinscription, Inscription, Jury
from sqlmodel import func
from .core.security import authenticate_user, create_access_token
from .core.config import settings
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException, status

@app.post("/login", response_class=RedirectResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """Authentification utilisateur"""
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}
    )

    # Créer la réponse de redirection avec le cookie
    response = RedirectResponse(url="/accueil", status_code=302)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Aligner avec la durée du token JWT
        secure=False,  # True en production avec HTTPS
        samesite="lax"
    )
    
    return response

async def root_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False),
    session: Session = Depends(get_session)
):
    """Traitement de la connexion"""
    try:
        # Vérifier les identifiants
        if UserService.verify_admin_credentials(session, email, password):
            # Connexion réussie - rediriger vers le dashboard admin
            logger.info(f"✅ Connexion administrateur réussie: {email}")
            return RedirectResponse(url="/admin", status_code=302)
        else:
            # Identifiants incorrects
            logger.warning(f"❌ Tentative de connexion échouée: {email}")
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
        logger.error(f"❌ Erreur lors de la connexion: {e}")
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
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "time": datetime.now(timezone.utc).isoformat() + "Z",
    }

# ============================================================================
# PAGES D'ERREUR
# ============================================================================


def register_error_handlers(app):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return templates.TemplateResponse(
                "404.html",
                {"request": request, "code": 404, "message": "La page demandée est introuvable.", "path": request.url.path},
                status_code=404,
            )
        elif exc.status_code == 500:
            # ID de corrélation simple pour logs/support
            incident_id = str(uuid.uuid4())[:8]
            # Log minimal (remplace par ton logger)
            try:
                request.app.logger.error(f"[500] {incident_id} {request.method} {request.url.path} -> {exc}")
            except Exception:
                pass

            return templates.TemplateResponse(
                "500.html",
                {
                    "request": request,
                    "incident_id": incident_id,
                    "path": request.url.path,
                    "now": datetime.now().strftime("%d/%m/%Y %H:%M"),
                },
                status_code=500,
            )
        # pour les autres HTTP (ex: 403), on laisse le défaut simple
        return HTMLResponse(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # ID de corrélation simple pour logs/support
        incident_id = str(uuid.uuid4())[:8]
        # Log minimal (remplace par ton logger)
        try:
            request.app.logger.error(f"[500] {incident_id} {request.method} {request.url.path} -> {exc}")
        except Exception:
            pass

        return templates.TemplateResponse(
            "500.html",
            {
                "request": request,
                "incident_id": incident_id,
                "path": request.url.path,
                "now": datetime.now().strftime("%d/%m/%Y %H:%M"),
            },
            status_code=500,
        )
    
register_error_handlers(app)

@app.get("/500-test")
def cinq_cent_de_demo():
    """Route de test pour déclencher une erreur 500"""
    raise HTTPException(status_code=500, detail="Démo 500")

@app.get("/test-500-division")
def test_division_by_zero():
    """Test avec une division par zéro pour déclencher une vraie exception"""
    result = 1 / 0  # Cela va lever une ZeroDivisionError
    return {"result": result}

@app.get("/test-500-attribute")
def test_attribute_error():
    """Test avec une erreur d'attribut"""
    obj = None
    return obj.non_existent_attribute  # Cela va lever une AttributeError


# ----------------------------
# Entrée locale (dev)
# ----------------------------
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=bool(settings.DEBUG),
        log_level="info",
    )
