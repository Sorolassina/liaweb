"""
Configuration des templates Jinja2
"""
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import os
from datetime import datetime
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from core.config import settings
    from core.path_config import path_config
    from app.services.file_upload_service import FileUploadService
except ImportError:
    # Fallback si l'import échoue
    settings = None
    path_config = None
    FileUploadService = None

# Configuration des templates
if settings:
    TEMPLATES_DIR = settings.TEMPLATE_DIR
else:
    # Fallback si settings n'est pas disponible
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    TEMPLATES_DIR = BASE_DIR / "app" / "templates"

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

def get_current_programme_from_session(request):
    """Récupère le code du programme actuel depuis request.state (middleware)"""
    if not request:
        return "PUBLIC"
    
    try:
        # Priorité 1 : Depuis request.state (middleware)
        if hasattr(request, 'state') and hasattr(request.state, 'program_schema'):
            programme = request.state.program_schema.upper()
            logger.info(f"Programme récupéré depuis request.state: {programme}")
            return programme
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération depuis request.state: {e}")
    
    try:
        # Priorité 2 : Depuis la session (fallback)
        if hasattr(request, 'session') and 'current_programme' in request.session:
            programme = request.session['current_programme']
            logger.info(f"Programme récupéré depuis session: {programme}")
            return programme
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération depuis session: {e}")
    
    logger.info("Aucun programme trouvé, utilisation de PUBLIC par défaut")
    return "PUBLIC"


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

def get_active_programmes():
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

def get_current_time():
    """Fonction pour obtenir l'heure actuelle dans les templates"""
    return datetime.now()

def get_company_logo_url():
    """Obtenir l'URL du logo de l'entreprise via path_config"""
    if path_config and settings:
        try:
            # Utiliser le chemin configuré dans settings
            logo_path = settings.COMPANY_LOGO_PATH
            # Extraire le nom du fichier depuis le chemin
            logo_filename = logo_path.split('/')[-1]  # "logo.png"
            
            # Utiliser path_config pour gérer les sous-dossiers
            return path_config.get_company_logo_url(logo_filename)
        except Exception:
            pass
    
    # Fallback vers le chemin configuré dans settings
    if settings:
        return settings.COMPANY_LOGO_PATH
    return "/static/images/logo.png"

def get_company_logo_path():
    """Obtenir le chemin physique du logo de l'entreprise"""
    if path_config and settings:
        try:
            # Utiliser le chemin configuré dans settings
            logo_path = settings.COMPANY_LOGO_PATH
            # Extraire le nom du fichier depuis le chemin
            logo_filename = logo_path.split('/')[-1]  # "logo.png"
            
            # Utiliser path_config optimisé avec sous-dossier compagnie
            return path_config.get_company_logo_path(logo_filename)
        except Exception:
            pass
    # Fallback
    return None

def company_logo_exists():
    """Vérifier si le logo de l'entreprise existe"""
    if path_config and settings:
        try:
            # Utiliser le chemin configuré dans settings
            logo_path = settings.COMPANY_LOGO_PATH
            # Extraire le nom du fichier depuis le chemin
            logo_filename = logo_path.split('/')[-1]  # "logo.png"
            
            # Utiliser path_config optimisé
            return path_config.company_file_exists(logo_filename, "compagnie")
        except Exception:
            pass
    return False

def get_company_file_url(filename: str, subfolder: str = "compagnie") -> str:
    """Obtenir l'URL d'un fichier de l'entreprise depuis le dossier media/compagnie/"""
    if path_config:
        try:
            return path_config.get_company_file_url(filename, subfolder)
        except Exception:
            pass
    return f"/media/{subfolder}/{filename}"

def get_company_file_path(filename: str, subfolder: str = "compagnie") -> str:
    """Obtenir le chemin physique d'un fichier de l'entreprise"""
    if path_config:
        try:
            return path_config.get_company_file_path(filename, subfolder)
        except Exception:
            pass
    return None

def company_file_exists(filename: str, subfolder: str = "compagnie") -> bool:
    """Vérifier si un fichier de l'entreprise existe"""
    if path_config:
        try:
            return path_config.company_file_exists(filename, subfolder)
        except Exception:
            pass
    return False

def list_company_files(subfolder: str = "compagnie") -> list:
    """Lister les fichiers dans le dossier compagnie"""
    if path_config:
        try:
            return path_config.list_company_files(subfolder)
        except Exception:
            pass
    return []

# Configuration globale des templates
if settings:
    templates.env.auto_reload = bool(settings.DEBUG)
    templates.env.globals.update(
        # === INFORMATIONS DE L'ENTREPRISE ===
        app_name=settings.APP_NAME,
        app_version=settings.VERSION,
        app_author=settings.AUTHOR,
        company_name=settings.COMPANY_NAME,
        company_description=settings.COMPANY_DESCRIPTION,
        company_address=settings.COMPANY_ADDRESS,
        company_phone=settings.COMPANY_PHONE,
        company_website=settings.COMPANY_WEBSITE,
        company_logo=get_company_logo_url,
        company_logo_exists=company_logo_exists,
        company_email=settings.ADMIN_EMAIL,
        
        # === THÈME ET DESIGN ===
        is_debug=settings.DEBUG,
        theme_primary=settings.THEME_PRIMARY,
        theme_secondary=settings.THEME_SECONDARY,
        theme_white=settings.THEME_WHITE,
        
        # === FONCTIONS UTILITAIRES ===
        now=get_current_time,
        datetime=datetime,
        format_candidat_name=format_candidat_name,
        format_email=format_email,
        get_current_programme_title=get_current_programme_title,
        get_current_programme_from_session=get_current_programme_from_session,
        get_programmes=get_active_programmes,  # ← Fonction pour éviter les conflits
        get_company_logo_url=get_company_logo_url,
        get_company_logo_path=get_company_logo_path,
        get_company_file_url=get_company_file_url,
        get_company_file_path=get_company_file_path,
        company_file_exists=company_file_exists,
        list_company_files=list_company_files,

        
        # === INFORMATIONS TECHNIQUES ===
        environment=settings.ENVIRONMENT,
        max_file_size_mb=settings.MAX_UPLOAD_SIZE_MB,
    )
