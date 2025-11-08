"""
Routers FastAPI pour l'application LIA Coaching
"""
# Routers d'authentification et web
from .auth import router as auth_router


# Routers de gestion des données
from .programmes import router as programmes_router
from .candidats import router as candidats_router
from .preinscriptions import router as preinscriptions_router
from .inscriptions import router as inscriptions_router
from .documents import router as documents_router
from .jury import router as jury_router

# Routers de dashboard et pipelines
from .dashboard import router as dashboard_router
from .pipelines import router as pipelines_router
from .pages import router as pages_router
from .accueil import router as accueil_router

# Routers spécialisés
from .admin import router as admin_router
from .rendez_vous import router as rendez_vous_router
from .password_recovery import router as password_recovery_router
from .seminaire import router as seminaire_router
from .event import router as event_router
from .codev import router as codev_router
from .elearning import router as elearning_router
from .suivi_mensuel import router as suivi_mensuel_router
from .admin_schemas import router as admin_schemas_router
from .directeur_technique import router as directeur_technique_router
from .messages import router as messages_router

# Configuration des routers avec préfixes et tags
router_configs = [
    # Authentification et pages web
    (auth_router, "/auth", ["authentification"]),
    (pages_router, "/pages", ["pages"]),
    (accueil_router,"/accueil",  ["accueil"]),
    (inscriptions_router, "/inscriptions", ["inscriptions"]),
    (admin_router, "/admin", ["admin"]),
    (rendez_vous_router, "/rendez_vous", ["rendez_vous"]),
    (password_recovery_router, "/password_recovery", ["password_recovery"]),
    (seminaire_router, "/seminaires", ["seminaires"]),
    (event_router, "/events", ["events"]),
    (codev_router, "/codev", ["codev"]),
    (elearning_router, "/elearning", ["e-learning"]),
    (suivi_mensuel_router, "/suivi-mensuel", ["suivi_mensuel"]),
    (admin_schemas_router, "/admin/schemas", ["admin_schemas"]),
    (directeur_technique_router, "/directeur-technique", ["directeur_technique"]),
    (messages_router, "/api/v1/messages", ["messages"]),
    
    # Gestion des données principales
    (programmes_router, "/programmes", ["programmes"]),
    (candidats_router, "/candidats", ["candidats"]),
    (preinscriptions_router, "/preinscriptions", ["preinscriptions"]),
    (documents_router, "/documents", ["documents"]),
    (jury_router, "/jury", ["jury"]),
    
    # Dashboard et pipelines
    (dashboard_router, "/dashboard", ["dashboard"]),
    (pipelines_router, "/pipelines", ["pipelines"]),
    
    # Routers spéciaux (fusionnés dans rendez_vous_router)
]

# Export des routers individuels pour utilisation spécifique
__all__ = [
    "auth_router",
    "accueil_router",
    "programmes_router",
    "candidats_router",
    "preinscriptions_router",
    "inscriptions_router",
    "documents_router",
    "jury_router",
    "dashboard_router",
    "pipelines_router",
    "admin_router",
    "rendez_vous_router",
    "password_recovery_router",
    "seminaire_router",
    "event_router",
    "codev_router",
    "elearning_router",
    "suivi_mensuel_router",
    "admin_schemas_router",
    "directeur_technique_router",
    "router_configs",
]
