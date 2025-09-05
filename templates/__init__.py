"""
Configuration des templates Jinja2
"""
from fastapi.templating import Jinja2Templates
from pathlib import Path

# Configuration des templates
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

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
