"""
Configuration centralisée des chemins montés dans l'application
Ce module permet d'accéder aux chemins montés depuis n'importe où dans l'application
"""
from pathlib import Path
from typing import Dict, Any
from app_lia_web.core.config import settings, BASE_DIR

class PathConfig:
    """Configuration centralisée des chemins de l'application"""
    
    def __init__(self):
        # === CHEMINS DE BASE ===
        self.BASE_DIR = BASE_DIR  # Utiliser la constante globale
        self.STATIC_DIR = settings.STATIC_DIR
        self.TEMPLATES_DIR = settings.TEMPLATE_DIR
        self.MEDIA_ROOT = settings.MEDIA_ROOT
        self.FICHIERS_DIR = settings.FICHIERS_DIR
        self.UPLOAD_DIR = settings.UPLOAD_DIR  # Chemin complet vers uploads
        
        # === CHEMINS SPÉCIFIQUES ===
        self.STATIC_MAPS_DIR = self.STATIC_DIR / "maps"
        self.STATIC_IMAGES_DIR = self.STATIC_DIR / "images"
        self.STATIC_CSS_DIR = self.STATIC_DIR / "css"
        self.STATIC_JS_DIR = self.STATIC_DIR / "js"
        
        # === CONFIGURATION DES MONTURES ===
        self.MOUNT_CONFIGS = {
            "static": {
                "path": "/static",
                "directory": str(self.STATIC_DIR),
                "name": "static"
            },
            "maps": {
                "path": "/maps",
                "directory": str(self.STATIC_MAPS_DIR),
                "name": "static_maps"
            },
            "images": {
                "path": "/static/images",
                "directory": str(self.STATIC_IMAGES_DIR),
                "name": "static_images"
            },
            "files": {
                "path": "/files",
                "directory": str(self.FICHIERS_DIR),
                "name": "static_files"
            },
            "media": {
                "path": "/media",
                "directory": str(self.MEDIA_ROOT),
                "name": "media"
            }
        }
    
    def get_mount_path(self, mount_name: str) -> str:
        """Obtenir le chemin de montage pour un nom donné"""
        if mount_name not in self.MOUNT_CONFIGS:
            raise ValueError(f"Monture '{mount_name}' non trouvée. Montures disponibles: {list(self.MOUNT_CONFIGS.keys())}")
        return self.MOUNT_CONFIGS[mount_name]["path"]
    
    def get_mount_directory(self, mount_name: str) -> str:
        """Obtenir le répertoire physique pour un nom de monture donné"""
        if mount_name not in self.MOUNT_CONFIGS:
            raise ValueError(f"Monture '{mount_name}' non trouvée. Montures disponibles: {list(self.MOUNT_CONFIGS.keys())}")
        return self.MOUNT_CONFIGS[mount_name]["directory"]
    
    def get_mount_name(self, mount_name: str) -> str:
        """Obtenir le nom FastAPI pour un nom de monture donné"""
        if mount_name not in self.MOUNT_CONFIGS:
            raise ValueError(f"Monture '{mount_name}' non trouvée. Montures disponibles: {list(self.MOUNT_CONFIGS.keys())}")
        return self.MOUNT_CONFIGS[mount_name]["name"]
    
    def get_file_url(self, mount_name: str, file_path: str, subfolder: str = None) -> str:
        """Générer l'URL complète d'un fichier avec sous-dossier optionnel"""
        mount_path = self.get_mount_path(mount_name)
        # Nettoyer le chemin du fichier
        clean_path = file_path.lstrip('/')
        
        # Ajouter le sous-dossier si fourni
        if subfolder:
            clean_path = f"{subfolder}/{clean_path}"
        
        return f"{mount_path}/{clean_path}"
    
    def get_physical_path(self, mount_name: str, file_path: str, subfolder: str = None) -> Path:
        """Obtenir le chemin physique complet d'un fichier avec sous-dossier optionnel"""
        mount_directory = self.get_mount_directory(mount_name)
        # Nettoyer le chemin du fichier
        clean_path = file_path.lstrip('/')
        
        # Ajouter le sous-dossier si fourni
        if subfolder:
            clean_path = f"{subfolder}/{clean_path}"
        
        return Path(mount_directory) / clean_path
    
    def ensure_directory_exists(self, mount_name: str) -> Path:
        """S'assurer que le répertoire de monture existe"""
        directory = Path(self.get_mount_directory(mount_name))
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    
    def ensure_subdirectory_exists(self, mount_name: str, subfolder: str) -> Path:
        """S'assurer qu'un sous-répertoire existe dans une monture"""
        mount_dir = self.ensure_directory_exists(mount_name)
        subdir = mount_dir / subfolder
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir
    
    
    # === MÉTHODES SPÉCIALISÉES POUR L'ENTREPRISE ===
    
    def get_company_logo_url(self, logo_filename: str = "logo.png") -> str:
        """Obtenir l'URL du logo de l'entreprise depuis media/compagnie/"""
        return self.get_file_url("media", logo_filename, "compagnie")
    
    def get_company_logo_path(self, logo_filename: str = "logo.png") -> Path:
        """Obtenir le chemin physique du logo de l'entreprise"""
        return self.get_physical_path("media", logo_filename, "compagnie")
    
    def get_company_file_url(self, filename: str, subfolder: str = "compagnie") -> str:
        """Obtenir l'URL d'un fichier de l'entreprise"""
        return self.get_file_url("media", filename, subfolder)
    
    def get_company_file_path(self, filename: str, subfolder: str = "compagnie") -> Path:
        """Obtenir le chemin physique d'un fichier de l'entreprise"""
        return self.get_physical_path("media", filename, subfolder)
    
    def ensure_company_directory_exists(self, subfolder: str = "compagnie") -> Path:
        """S'assurer que le dossier compagnie existe"""
        return self.ensure_subdirectory_exists("media", subfolder)
    
    def company_file_exists(self, filename: str, subfolder: str = "compagnie") -> bool:
        """Vérifier si un fichier de l'entreprise existe"""
        try:
            file_path = self.get_company_file_path(filename, subfolder)
            return file_path.exists()
        except:
            return False

# Instance globale pour faciliter l'import
path_config = PathConfig()
