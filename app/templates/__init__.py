"""
Configuration des templates Jinja2
"""
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import os
import time
from datetime import datetime
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from core.config import settings
    from core.path_config import path_config
except ImportError:
    # Fallback si l'import échoue
    settings = None
    path_config = None

# Configuration des templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if settings:
    TEMPLATES_DIR = settings.TEMPLATE_DIR
else:
    # Fallback si settings n'est pas disponible
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

def format_time(value):
    """Formate une heure"""
    if value:
        return value.strftime("%H:%M")
    return "Non renseigné"

def format_date_input(value):
    """Formate une date pour input HTML (YYYY-MM-DD)"""
    if value:
        return value.strftime("%Y-%m-%d")
    return ""

def format_datetime_input(value):
    """Formate une date et heure pour input HTML (YYYY-MM-DDTHH:MM)"""
    if value:
        return value.strftime("%Y-%m-%dT%H:%M")
    return ""

def format_date_short(value):
    """Formate une date courte (DD/MM)"""
    if value:
        return value.strftime("%d/%m")
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
    """Extrait le titre du programme depuis l'URL, les paramètres ou retourne le titre par défaut"""
    if not request:
        return "TIEKA-Gestion coaching"
    
    # PRIORITÉ 1: Depuis request.state (middleware)
    if hasattr(request, 'state') and hasattr(request.state, 'program_schema') and request.state.program_schema:
        return request.state.program_schema.upper()
    
    # PRIORITÉ 2: Depuis les paramètres de requête (ex: ?programme=ACD)
    programme_param = request.query_params.get('programme')
    if programme_param:
        return programme_param.upper()
    else:   
        return "TIEKA-Gestion coaching"


def get_user_type_from_cookie(request):
    """Récupère le type d'utilisateur depuis les cookies (bpi, partenaire, candidat)"""
    if not request:
        return ""
    return request.cookies.get("user_type", "")

def can_see_menu_item(user, menu_name: str) -> bool:
    """
    Détermine si un utilisateur peut voir un élément de menu spécifique
    basé sur sa position et son rôle.
    
    Args:
        user: L'utilisateur connecté (doit avoir position et role)
        menu_name: Le nom du menu ('candidat', 'bpi', 'programmes', 'admin', etc.)
    
    Returns:
        bool: True si l'utilisateur peut voir le menu, False sinon
    """
    if not user:
        return False
    
    position = getattr(user, 'position', 'Candidat').lower()
    role = getattr(user, 'role', '').lower()
    
    # SuperAdmin (administrateur) : accès complet à tous les menus
    if role == 'administrateur':
        return True
    
    # Directeur : droit à tous les menus (mais pas accès complet comme SuperAdmin)
    if role in ['directeur_general', 'directeur_technique']:
        return True
    
    # Filtrage par position
    if position == 'bpi':
        # BPI : accès uniquement à l'espace BPI (pas d'accueil, pas de programmes, pas d'admin)
        return menu_name == 'bpi'
    
    elif position == 'candidat':
        # Candidat : accès uniquement à l'espace Candidat (pas d'accueil, pas de programmes, pas d'admin)
        return menu_name == 'candidat'
    
    elif position == 'partenaire':
        # Partenaire : masquer BPI et Candidat
        if menu_name in ['bpi', 'candidat']:
            return False
        # Les partenaires voient les programmes selon leur rôle
        return menu_name in ['programmes', 'accueil']
    
    # Pour les autres positions ou par défaut, vérifier selon le rôle
    # Conseiller, Coordinateur, Responsable_programme : droit au menu de son programme
    if role in ['conseiller', 'coordinateur', 'responsable_programme']:
        return menu_name in ['programmes', 'accueil']
    
    # Coach : droit au menu rdv de son programme
    if role in ['coach_externe', 'accompagnateur']:
        return menu_name in ['programmes', 'accueil']  # Les RDV sont dans les programmes
    
    # Responsable Communication : droit au menu seminaire, event de tous les programmes
    if role in ['responsable_communication', 'assistant_communication']:
        return menu_name in ['programmes', 'accueil']
    
    # Par défaut, ne rien afficher
    return False

def can_see_programme_menu_item(user, menu_item: str) -> bool:
    """
    Détermine si un utilisateur peut voir un élément de menu spécifique dans un programme
    basé sur son rôle.
    
    Args:
        user: L'utilisateur connecté
        menu_item: L'élément de menu ('dashboard', 'preinscriptions', 'inscriptions', 
                  'rendez-vous', 'seminaires', 'events', 'codev', 'elearning', 'suivi-mensuel')
    
    Returns:
        bool: True si l'utilisateur peut voir l'élément, False sinon
    """
    if not user:
        return False
    
    position = getattr(user, 'position', 'Candidat').lower()
    role = getattr(user, 'role', '').lower()
    
    # SuperAdmin (administrateur) : accès complet à tous les menus de programme
    if role == 'administrateur':
        return True
    
    # Directeur : droit à tous les menus de programme
    if role in ['directeur_general', 'directeur_technique']:
        return True
    
    # Si position est BPI, ne pas voir les menus de programme (uniquement l'espace BPI)
    if position == 'bpi':
        return False
    
    # Si position est Partenaire, voir certains éléments
    if position == 'partenaire':
        return menu_item in ['dashboard', 'rendez-vous', 'seminaires', 'events', 'codev', 'elearning']
    
    # Conseiller, Coordinateur, Responsable_programme : accès à tous les menus de leur programme
    if role in ['conseiller', 'coordinateur', 'responsable_programme']:
        return True
    
    # Coach : accès uniquement aux RDV
    if role in ['coach_externe', 'accompagnateur']:
        return menu_item == 'rendez-vous'
    
    # Responsable Communication : accès aux séminaires et événements de tous les programmes
    if role in ['responsable_communication', 'assistant_communication']:
        return menu_item in ['seminaires', 'events']
    
    return False

def get_current_programme_from_session(request):
    """Récupère le code du programme actuel depuis request.state (middleware)"""
    if not request:
        return "PUBLIC"
    
    try:
        programme = getattr(request.state, 'program_schema', None)
        if programme:
            logger.info(f"Programme récupéré depuis request.state: {programme}")
            return programme.upper()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération depuis request.state: {e}")
    
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
templates.env.filters["format_time"] = format_time
templates.env.filters["format_date_input"] = format_date_input
templates.env.filters["format_datetime_input"] = format_datetime_input
templates.env.filters["format_date_short"] = format_date_short
templates.env.filters["statut_color"] = statut_color
templates.env.filters["action_color"] = action_color
templates.env.filters["format_candidat_name"] = format_candidat_name
templates.env.filters["format_email"] = format_email
templates.env.filters["format_number_french"] = format_number_french

def get_active_programmes():
    """Récupère tous les programmes actifs pour le menu (lazy loading)"""
    try:
        from ..core.database import get_session
        from ..models.base import Programme
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

def get_current_time_formatted(format_str='%Y%m%d%H%M'):
    """Fonction pour obtenir l'heure actuelle formatée dans les templates"""
    return datetime.now().strftime(format_str)

def get_current_year():
    """Fonction pour obtenir l'année actuelle dans les templates"""
    return datetime.now().year

def company_logo(return_type='url'):
    """
    Fonction unique pour gérer le logo de l'entreprise.
    
    Args:
        return_type: Type de retour souhaité
            - 'url': URL du logo avec versionnement (par défaut)
            - 'path': Chemin physique du logo
            - 'exists': Booléen indiquant si le logo existe
            - 'filename': Nom du fichier logo
    
    Returns:
        Selon return_type: URL (str), chemin (Path), booléen, ou nom de fichier (str)
    """
    # Extraire le nom du fichier logo
    logo_filename = "logo.png"
    if settings:
        try:
            logo_path = settings.COMPANY_LOGO_PATH
            logo_filename = logo_path.split('/')[-1]  # "logo.png"
        except Exception:
            pass
    
    # Si on veut juste le nom du fichier
    if return_type == 'filename':
        return logo_filename
    
    # Vérifier si le logo existe dans media/compagnie/
    logo_exists = False
    logo_url = None
    logo_path = None
    
    if path_config and settings:
        try:
            if path_config.company_file_exists(logo_filename, "compagnie"):
                logo_exists = True
                logo_url = path_config.get_company_logo_url(logo_filename)
                logo_path = path_config.get_company_logo_path(logo_filename)
        except Exception:
            pass
    
    # Fallback vers le logo par défaut
    if not logo_exists:
        if path_config:
            try:
                # Utiliser path_config pour obtenir le chemin et l'URL du logo par défaut
                default_logo_path = path_config.get_physical_path("images", "logo.png")
                if default_logo_path.exists():
                    logo_exists = True
                    logo_url = path_config.get_file_url("images", "logo.png")
                    logo_path = default_logo_path
            except Exception:
                pass
        elif settings:
            try:
                default_logo_path = settings.STATIC_DIR / "images" / "logo.png"
                if default_logo_path.exists():
                    logo_exists = True
                    logo_url = settings.COMPANY_LOGO_PATH
                    logo_path = default_logo_path
            except Exception:
                pass
        else:
            # Si pas de path_config ni settings, utiliser le logo par défaut
            logo_url = "/static/images/logo.png"
            logo_exists = True
    
    # Retourner selon le type demandé
    if return_type == 'exists':
        return logo_exists
    elif return_type == 'path':
        return logo_path
    elif return_type == 'url':
        # Ajouter le versionnement automatiquement
        return static_versioning(logo_url) if logo_url else None
    else:
        return logo_url

def get_company_file_url(filename: str, subfolder: str = "compagnie") -> str:
    """Obtenir l'URL d'un fichier de l'entreprise depuis le dossier media/compagnie/"""
    if path_config:
        try:
            return path_config.get_company_file_url(filename, subfolder)
        except Exception:
            pass
    # Fallback : utiliser path_config pour obtenir le chemin de montage "media"
    if path_config:
        try:
            media_path = path_config.get_mount_path("media")
            return f"{media_path}/{subfolder}/{filename}"
        except Exception:
            pass
    return f"/uploads/{subfolder}/{filename}"

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

def get_user_photo_url(utilisateur=None):
    """
    Obtenir l'URL de la photo de profil de l'utilisateur ou l'image par défaut.
    Utilise path_config pour générer les URLs de manière centralisée.
    Vérifie que le fichier existe avant de retourner son URL.
    
    Args:
        utilisateur: Objet utilisateur avec attribut photo_profil (optionnel)
    
    Returns:
        str: URL de la photo de profil ou de l'image par défaut (utilisateur.png)
    """
    # Fonction helper pour obtenir l'image par défaut
    def get_default_photo_url():
        """Retourne l'URL de l'image par défaut (bonhomme de login)"""
        try:
            if path_config:
                # Utiliser path_config pour générer l'URL de l'image par défaut
                # La monture "images" pointe vers /static/images
                default_url = path_config.get_file_url("images", "utilisateur.png")
                # Ajouter le versionnement pour éviter les problèmes de cache
                return static_versioning(default_url)
            else:
                # Fallback si path_config n'est pas disponible : utiliser STATIC_BASE_PATH
                if settings:
                    base_path = settings.STATIC_BASE_PATH
                else:
                    base_path = '/static'
                default_url = f"{base_path}/images/utilisateur.png"
                return static_versioning(default_url)
        except Exception as e:
            # Log l'erreur pour debugging (en mode développement)
            if settings and settings.DEBUG:
                logger.warning(f"Erreur lors de la génération de l'URL de photo par défaut: {e}")
            # Fallback si erreur
            return "/static/images/utilisateur.png"
    
    # Vérifier si l'utilisateur a une photo de profil
    if utilisateur and hasattr(utilisateur, 'photo_profil') and utilisateur.photo_profil:
        photo_path = str(utilisateur.photo_profil).strip()
        
        # Ignorer les chaînes vides après strip
        if not photo_path:
            # Passer à l'image par défaut si photo_path est vide
            return get_default_photo_url()
        
        # Si le chemin commence déjà par /uploads/ ou /media/, vérifier l'existence
        if photo_path.startswith('/uploads/') or photo_path.startswith('/media/'):
            # Extraire le chemin relatif pour vérifier l'existence
            if path_config:
                try:
                    # Extraire le chemin relatif depuis l'URL complète
                    normalized_path = photo_path.lstrip('/uploads/').lstrip('/media/')
                    # Vérifier si le fichier existe physiquement
                    physical_path = path_config.get_physical_path("media", normalized_path)
                    if physical_path.exists():
                        return photo_path
                    else:
                        # Le fichier n'existe pas, utiliser l'image par défaut
                        if settings and settings.DEBUG:
                            logger.debug(f"Photo utilisateur non trouvée: {physical_path}, utilisation de l'image par défaut")
                        return get_default_photo_url()
                except Exception as e:
                    if settings and settings.DEBUG:
                        logger.warning(f"Erreur lors de la vérification de la photo: {e}")
                    # En cas d'erreur, utiliser l'image par défaut
                    return get_default_photo_url()
            else:
                # Si path_config n'est pas disponible, retourner tel quel (pas de vérification)
                return photo_path
        
        # Utiliser path_config pour générer l'URL de la photo uploadée
        if path_config:
            try:
                # Normaliser le chemin (supprimer les slashes en début si présents)
                normalized_path = photo_path.lstrip('/')
                # Vérifier si le fichier existe physiquement
                physical_path = path_config.get_physical_path("media", normalized_path)
                if physical_path.exists():
                    # Le fichier existe, retourner l'URL
                    return path_config.get_file_url("media", normalized_path)
                else:
                    # Le fichier n'existe pas, utiliser l'image par défaut
                    if settings and settings.DEBUG:
                        logger.debug(f"Photo utilisateur non trouvée: {physical_path}, utilisation de l'image par défaut")
                    return get_default_photo_url()
            except Exception as e:
                if settings and settings.DEBUG:
                    logger.warning(f"Erreur lors de la génération de l'URL de photo: {e}")
                # En cas d'erreur, utiliser l'image par défaut
                return get_default_photo_url()
        else:
            # Fallback si path_config n'est pas disponible (pas de vérification d'existence)
            normalized_path = photo_path.lstrip('/')
            return f"/uploads/{normalized_path}"
    
    # Pas de photo de profil : utiliser l'image par défaut
    return get_default_photo_url()

def static_versioning(static_path):
    """
    Ajoute un paramètre de version à une URL de fichier statique pour éviter les problèmes de cache.
    
    Args:
        static_path: Chemin du fichier statique (ex: "/static/images/logo.png")
    
    Returns:
        URL avec paramètre de version (ex: "/static/images/logo.png?v=1.0.0")
    """
    if not static_path:
        return static_path
    
    # Récupérer la version depuis settings si disponible
    version = None
    if settings:
        version = getattr(settings, 'VERSION', None)
    
    # Si pas de version dans settings, utiliser un timestamp
    if not version:
        try:
            # Utiliser un timestamp basé sur la date de modification du fichier si possible
            # Détecter le type de chemin (static, images, media, etc.)
            file_path = None
            static_file = None
            
            if path_config:
                # Essayer de trouver le fichier via path_config
                for mount_name in ["static", "images", "media"]:
                    try:
                        mount_path = path_config.get_mount_path(mount_name)
                        if static_path.startswith(mount_path + '/'):
                            file_path = static_path.replace(mount_path + '/', '')
                            static_file = path_config.get_physical_path(mount_name, file_path)
                            break
                    except Exception:
                        continue
            
            # Fallback : détection manuelle si path_config n'a pas fonctionné
            if not static_file:
                if static_path.startswith('/static/'):
                    file_path = static_path.replace('/static/', '')
                    if settings:
                        static_file = settings.STATIC_DIR / file_path.lstrip('/')
                    else:
                        static_file = BASE_DIR / "app" / "static" / file_path.lstrip('/')
            
            if static_file and static_file.exists():
                mtime = os.path.getmtime(static_file)
                version = str(int(mtime))
        except Exception:
            pass
        
        # Fallback: utiliser un timestamp simple
        if not version:
            version = str(int(time.time()))
    
    # Ajouter le paramètre de version
    separator = '&' if '?' in static_path else '?'
    return f"{static_path}{separator}v={version}"

def static_url(path):
    """
    Génère une URL pour un fichier statique.
    Utilise path_config pour obtenir le chemin de montage "static".
    
    Args:
        path: Chemin relatif du fichier statique (ex: "css/base.css" ou "images/logo.png")
    
    Returns:
        URL complète du fichier statique (ex: "/static/css/base.css")
    """
    # Normaliser le chemin (supprimer les slashes en début si présents)
    normalized_path = path.lstrip('/')
    
    # Utiliser path_config pour obtenir le chemin de montage "static"
    if path_config:
        try:
            static_base_path = path_config.get_mount_path("static")
            return f"{static_base_path}/{normalized_path}"
        except Exception:
            pass
    
    # Fallback : utiliser STATIC_BASE_PATH depuis settings
    if settings:
        static_base_path = settings.STATIC_BASE_PATH
    else:
        static_base_path = '/static'
    
    # Construire l'URL statique
    return f"{static_base_path}/{normalized_path}"

def static_versioned_url(path):
    """
    Génère une URL versionnée pour un fichier statique.
    Alias de static_versioning(static_url(path)).
    
    Args:
        path: Chemin relatif du fichier statique (ex: "css/base.css")
    
    Returns:
        URL versionnée du fichier statique (ex: "/static/css/base.css?v=1.0.0")
    """
    return static_versioning(static_url(path))


# Configuration globale des templates
# Injection des fonctions utilitaires (toujours disponibles)
templates.env.globals.update(
    # === FONCTIONS UTILITAIRES ===
    now=get_current_time,
    now_formatted=get_current_time_formatted,
    current_year=get_current_year,
    datetime=datetime,
    format_candidat_name=format_candidat_name,
    format_email=format_email,
    get_current_programme_title=get_current_programme_title,
    get_current_programme_from_session=get_current_programme_from_session,
    get_user_type_from_cookie=get_user_type_from_cookie,  # Type d'utilisateur (bpi, partenaire, candidat)
    get_programmes=get_active_programmes,  # ← Fonction pour éviter les conflits
    get_user_photo_url=get_user_photo_url,
    static_versioning=static_versioning,  # Fonction de versionnement des fichiers statiques
    static_versioned_url=static_versioned_url,  # Alias avec static_url intégré
    static_url=static_url,  # Fonction pour générer les URLs statiques
    company_logo=company_logo,  # Fonction unique pour gérer le logo de l'entreprise
    # Alias pour compatibilité avec l'ancien code
    get_company_logo_url=lambda: company_logo('url'),
    company_logo_exists=lambda: company_logo('exists'),
    # === FONCTIONS DE VISIBILITÉ DES MENUS ===
    can_see_menu_item=can_see_menu_item,  # Vérifie si un utilisateur peut voir un menu principal
    can_see_programme_menu_item=can_see_programme_menu_item,  # Vérifie si un utilisateur peut voir un menu de programme
   
)

# Créer un contexte personnalisé qui injecte url_for basé sur request
# Cela sera fait via un contexte de processus de rendu personnalisé

# Configuration spécifique si settings est disponible
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
        company_email=settings.ADMIN_EMAIL,
        # Variables globales pour les templates (version et root_path)
        version=settings.VERSION,  # Version de l'application
        root_path="",  # Chemin racine (vide par défaut, peut être surchargé par les routes)
        
        # === THÈME ET DESIGN ===
        is_debug=settings.DEBUG,
        theme_primary=settings.THEME_PRIMARY,
        theme_secondary=settings.THEME_SECONDARY,
        theme_white=settings.THEME_WHITE,
        
        # === FONCTIONS ENTREPRISE ===
        get_company_file_url=get_company_file_url,
        get_company_file_path=get_company_file_path,
        company_file_exists=company_file_exists,
        list_company_files=list_company_files,
        
        # === INFORMATIONS TECHNIQUES ===
        environment=settings.ENVIRONMENT,
        max_file_size_mb=settings.MAX_UPLOAD_SIZE_MB,
    )
