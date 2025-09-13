"""
Configuration des templates Jinja2
"""
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from core.config import settings
except ImportError:
    # Fallback si l'import échoue
    settings = None

# Configuration des templates
if settings:
    TEMPLATES_DIR = settings.TEMPLATE_DIR
else:
    # Fallback si settings n'est pas disponible
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    TEMPLATES_DIR = BASE_DIR / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Configuration globale des templates
if settings:
    templates.env.auto_reload = bool(settings.DEBUG)
    templates.env.globals.update(
        app_name=settings.APP_NAME,
        app_version=settings.VERSION,
        is_debug=settings.DEBUG,
        theme_primary=settings.THEME_PRIMARY,
        theme_secondary=settings.THEME_SECONDARY,
        theme_white=settings.THEME_WHITE,
    )


# Filtres personnalisés pour Jinja2
def format_date(value):
    """Formate une date"""
    if value:
        return value.strftime("%d/%m/%Y")
    return "Non renseigné"

def format_datetime(value):
    """Formate une date et heure"""
    if value:
        return value.strftime("%d/%m/%Y à %H:%M")
    return "Non renseigné"

def statut_color(statut):
    """Retourne la couleur CSS pour un statut"""
    colors = {
        'SOUMIS': 'warning',
        'EN_EXAMEN': 'info',
        'VALIDE': 'success',
        'REJETE': 'danger',
        'EN_ATTENTE': 'secondary'
    }
    return colors.get(statut, 'secondary')

def action_color(action_type):
    """Retourne la couleur CSS pour un type d'action"""
    colors = {
        'preinscription': 'primary',
        'inscription': 'success',
        'jury': 'info',
        'document': 'warning'
    }
    return colors.get(action_type, 'secondary')

# Ajout des filtres au template
templates.env.filters["format_date"] = format_date
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["statut_color"] = statut_color
templates.env.filters["action_color"] = action_color
