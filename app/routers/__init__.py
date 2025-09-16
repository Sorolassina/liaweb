"""
Routers FastAPI pour l'application LIA Coaching
"""
# Routers d'authentification et web
from .auth import router as auth_router


# Routers de gestion des données
from .programmes import router as programmes_router
from .candidats import router as candidats_router
from .ACD.preinscriptions import router as preinscriptions_router
from .inscriptions import router as inscriptions_router
from .documents import router as documents_router
from .jury import router as jury_router

# Routers de dashboard et pipelines
from .dashboard import router as dashboard_router
from .pipelines import router as pipelines_router
from .pages import router as pages_router
from .accueil import router as accueil_router
from .ACD.ACD import router as ACD_router
from .ACD.preinscriptions import router as ACD_preinscriptions_router
from .ACD.inscriptions import router as ACD_inscriptions_router
from .ACD.admin import router as ACD_admin_router
from .ACD.jury_decisions import router as ACD_jury_decisions_router
from .ACD.route_qpv import router as ACD_qpv_router
from .ACD.route_siret_pappers import router as ACD_siret_router
from .rendez_vous import router as rendez_vous_router
from .video_router import router as video_router
from .emargement_router import router as emargement_router
from .candidat_email_update import router as candidat_email_router
from .password_recovery import router as password_recovery_router
from .seminaire import router as seminaire_router
from .event import router as event_router
from .codev import router as codev_router

# Configuration des routers avec préfixes et tags
router_configs = [
    # Authentification et pages web
    (auth_router, "/auth", ["authentification"]),
    (pages_router, "/pages", ["pages"]),
    (accueil_router,"/accueil",  ["accueil"]),
    (ACD_router,"/ACD",  ["ACD"]),
    (ACD_preinscriptions_router, "/ACD", ["ACD_preinscriptions"]),
    (ACD_inscriptions_router, "/ACD", ["ACD_inscriptions"]),
    (ACD_admin_router, "/admin", ["Admin"]),
    (ACD_jury_decisions_router, "/ACD", ["ACD_jury_decisions"]),
    (ACD_qpv_router, "/ACD", ["ACD_qpv"]),
    (ACD_siret_router, "/ACD", ["ACD_siret"]),
    (rendez_vous_router, "", ["rendez_vous"]),
    (video_router, "", ["video_rdv"]),
    (candidat_email_router, "", ["candidat_email"]),
    (password_recovery_router, "", ["password_recovery"]),
    (seminaire_router, "/seminaires", ["seminaires"]),
    (event_router, "/events", ["events"]),
    (codev_router, "/codev", ["codev"]),

    
    # Gestion des données principales
    (programmes_router, "/programmes", ["programmes"]),
    (candidats_router, "/candidats", ["candidats"]),
    (preinscriptions_router, "/preinscriptions", ["preinscriptions"]),
    (inscriptions_router, "/inscriptions", ["inscriptions"]),
    (documents_router, "/documents", ["documents"]),
    (jury_router, "/jury", ["jury"]),
    
    # Dashboard et pipelines
    (dashboard_router, "/dashboard", ["dashboard"]),
    (pipelines_router, "/pipelines", ["pipelines"]),
    
    # Routers spéciaux (sans préfixe)
    (video_router, "", ["video"]),
    (emargement_router, "", ["emargement"]),
    (password_recovery_router, "", ["password_recovery"]),
]

# Export des routers individuels pour utilisation spécifique
__all__ = [
    "auth_router",
    "web_router", 
    "accueil_router",
    "programmes_router",
    "candidats_router",
    "preinscriptions_router",
    "inscriptions_router", 
    "documents_router",
    "jury_router",
    "dashboard_router",
    "pipelines_router",
    "ACD_qpv_router",
    "ACD_siret_router",
    "rendez_vous_router",
    "video_router",
    "emargement_router",
    "password_recovery_router",
    "seminaire_router",
    "event_router",
    "codev_router",
    "router_configs",
]
