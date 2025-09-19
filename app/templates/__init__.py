"""
Configuration des templates Jinja2
"""
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import os
from datetime import datetime

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

# Ajouter la fonction now() au contexte global
templates.env.globals['now'] = datetime.now



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

def format_candidat_name(nom, prenom=None, max_length=15):
    """Formate le nom du candidat intelligemment"""
    # Si appelé comme filtre avec un seul paramètre, on suppose que c'est le nom
    if prenom is None:
        return nom  # Retourner tel quel si pas de prénom
    
    if not nom or not prenom:
        return f"{prenom or ''} {nom or ''}".strip()
    
    # Construire le nom complet
    full_name = f"{nom} {prenom}"
    
    # Si le nom complet fait moins de max_length caractères, on le retourne tel quel
    if len(full_name) <= max_length:
        return full_name
    
    # Séparer les prénoms
    prenoms = prenom.split()
    
    # Si on a un seul prénom et qu'il est trop long
    if len(prenoms) == 1:
        if len(f"{nom} {prenoms[0]}") > max_length:
            # Tronquer le prénom
            available_space = max_length - len(nom) - 1  # -1 pour l'espace
            if available_space > 3:  # Au moins 3 caractères pour le prénom
                truncated_prenom = prenoms[0][:available_space-3] + "..."
                return f"{nom} {truncated_prenom}"
            else:
                return f"{nom}..."
        return f"{nom} {prenoms[0]}"
    
    # Si on a plusieurs prénoms
    # Essayer d'abord avec le premier prénom complet et les autres en initiales
    first_prenom = prenoms[0]
    other_initials = " ".join([p[0] + "." for p in prenoms[1:]])
    name_with_initials = f"{nom} {first_prenom} {other_initials}"
    
    if len(name_with_initials) <= max_length:
        return name_with_initials
    
    # Si c'est encore trop long, tronquer le premier prénom
    available_space = max_length - len(nom) - len(other_initials) - 2  # -2 pour les espaces
    if available_space > 3:
        truncated_first = first_prenom[:available_space-3] + "..."
        return f"{nom} {truncated_first} {other_initials}"
    
    # Dernière option : juste le nom avec des initiales
    initials_only = " ".join([p[0] + "." for p in prenoms])
    initials_name = f"{nom} {initials_only}"
    
    if len(initials_name) <= max_length:
        return initials_name
    
    # Si même les initiales sont trop longues, tronquer
    return f"{nom}..."

def format_candidat_name_filter(nom, prenom, max_length=15):
    """Version filtre de format_candidat_name pour Jinja2"""
    return format_candidat_name(nom, prenom, max_length)

def format_email(email, max_length=25):
    """Formate l'email si trop long"""
    if not email:
        return ""
    
    if len(email) <= max_length:
        return email
    
    # Séparer le nom d'utilisateur et le domaine
    if '@' in email:
        username, domain = email.split('@', 1)
        
        # Si le domaine est trop long, le tronquer
        if len(domain) > 15:
            domain = domain[:12] + "..."
        
        # Calculer l'espace disponible pour le nom d'utilisateur
        available_space = max_length - len(domain) - 1  # -1 pour le @
        
        if available_space > 3:
            truncated_username = username[:available_space-3] + "..."
            return f"{truncated_username}@{domain}"
        else:
            return f"...@{domain}"
    
    # Si pas d'@, tronquer simplement
    return email[:max_length-3] + "..."

def get_current_programme_title(request):
    """Extrait le titre du programme depuis l'URL ou retourne le titre par défaut"""
    if not request:
        return "LIA-Gestion coaching"
    
    # Extraire le programme depuis l'URL
    path = request.url.path
    if '/ACD/' in path:
        return "ACD"
    elif '/ACI/' in path:
        return "ACI" 
    elif '/ACT/' in path:
        return "ACT"
    else:
        return "LIA-Gestion coaching"

def format_number_french(value, decimals=2):
    """Formate un nombre avec la virgule comme séparateur décimal (format français)"""
    if value is None:
        return "0,00"
    
    try:
        # Convertir en float si nécessaire
        if isinstance(value, str):
            value = float(value)
        
        # Formater avec le nombre de décimales demandé
        if decimals == 0:
            formatted = f"{int(value):,}".replace(",", " ")
        else:
            formatted = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
        
        return formatted
    except (ValueError, TypeError):
        return "0,00"

# Ajout des filtres au template
templates.env.filters["format_date"] = format_date
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["statut_color"] = statut_color
templates.env.filters["action_color"] = action_color
templates.env.filters["format_candidat_name"] = format_candidat_name
templates.env.filters["format_email"] = format_email
templates.env.filters["format_number_french"] = format_number_french

def get_programmes():
    """Récupère tous les programmes actifs pour le menu (lazy loading)"""
    try:
        from app_lia_web.core.database import get_session
        from app_lia_web.app.models.base import Programme
        from sqlmodel import Session, select
        
        # Créer une session temporaire
        session = next(get_session())
        try:
            programmes = session.exec(select(Programme).where(Programme.actif == True).order_by(Programme.code)).all()
            return programmes
        finally:
            session.close()
    except Exception as e:
        print(f"Erreur lors de la récupération des programmes: {e}")
        return []

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
        now=datetime.now,
        format_candidat_name=format_candidat_name,
        format_email=format_email,
        get_current_programme_title=get_current_programme_title,
        programmes=get_programmes,  # ← Fonction au lieu de résultat
    )
