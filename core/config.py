"""
Configuration de l'application LIA Coaching (compatible Pydantic v2)
"""
from typing import List, Optional, ClassVar
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import Field
import os
from fastapi import Request

# Constante globale (pas dans la classe)
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Paramètres centralisés (chargés via .env si présent)."""

    # --- Pydantic v2 config ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # ignore les clés inconnues
    )

    # === Base de données ===
    PGUSER: Optional[str] = "liauser"
    PGPASSWORD: Optional[str] = "liapass123"
    PGHOST: Optional[str] = "localhost"
    PGPORT: Optional[int] = 5432
    PGDATABASE: Optional[str] = "lia_coaching"

    PGSUPERUSER : Optional[str] = "soro"
    PGSUPERPASS : Optional[str] = "Ayoub112326"

    @property
    def DATABASE_URL(self) -> str:
        """URL de connexion à la base de données PostgreSQL."""
        from urllib.parse import quote_plus
        password = quote_plus(self.PGPASSWORD) if self.PGPASSWORD else ""
        return f"postgresql://{self.PGUSER}:{password}@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"

    # === Sécurité / JWT ===
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 heures au lieu de 30 minutes

    # === Services externes ===
    PAPPERS_API_KEY: Optional[str] = None
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    
    # === Services QPV et SIRET ===
    QPV_API_TIMEOUT: int = 30  # Timeout pour l'API géolocalisation
    SIRET_API_TIMEOUT: int = 30  # Timeout pour l'API Pappers
    MAP_ZOOM_LEVEL: int = 14  # Niveau de zoom par défaut
    MAP_WIDTH: int = 800  # Largeur des cartes générées
    MAP_HEIGHT: int = 600  # Hauteur des cartes générées
    DISTANCE_QPV_LIMITE: float = 500.0  # Distance en mètres pour considérer une adresse comme "QPV limite"

   # Clés API (optionnelles)
    PAPPERS_API_KEY: Optional[str] = "3721812f3ce2b994725e057e906fe35a96ec4ee4209da3f2"
    DIGIFORMA_API_KEY: Optional[str] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MzU0OSwidHlwZSI6InVzZXIiLCJtb2RlIjoiYXBpIiwiZXhwIjoyMDU2Mzc5MTYzLCJpc3MiOiJEaWdpZm9ybWEifQ.gmu5m45X2a54BUXiZJA8Vhh6x36kqKtcLp-2hGomfxo"
    DIGIFORMAT_PASSWORD:Optional[str]="2311SLSs@1990"

    # === Email ===
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = "sorolassina58@gmail.com"
    SMTP_PASSWORD: Optional[str] = "sbam wlve xhyr zxza"
    SMTP_TLS: bool = True   # STARTTLS
    SMTP_SSL: bool = False  # SMTPS port 465

    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: str = "noreply@lia-coaching.com"
    MAIL_FROM_NAME: str = "LIA Coaching"

    MAIL_SERVER: Optional[str] = "smtp.gmail.com"
    MAIL_PORT: Optional[int] = 587
    MAIL_USE_TLS: Optional[bool] = True
    MAIL_ADMIN: Optional[str] = "sorolassina58@gmail.com"
    PASSWORD_ADMIN: Optional[str] = "ChangeMoi#2025"

    # === Upload et fichiers ===
    MAX_UPLOAD_SIZE_MB: int = 10  # Taille maximale des fichiers uploadés
    ALLOWED_IMAGE_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    ALLOWED_DOC_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/jpeg", "image/png", "image/gif",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    ALLOWED_DOC_EXTENSIONS: List[str] = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx']
    
    # === Chemins des fichiers ===
    UPLOAD_DIR: str = "uploads"
    STATIC_DOCS_DIR: str = "static/documents"
    
    # === Propriétés calculées (s'exécutent seulement quand appelées) ===
    @property
    def STATIC_DIR(self) -> Path:
        return BASE_DIR / "static"
    
    @property
    def TEMPLATE_DIR(self) -> Path:
        return BASE_DIR / "templates"
    
    @property
    def FICHIERS_DIR(self) -> Path:
        return BASE_DIR / "fichiers"
    
    @property
    def STATIC_IMAGES_DIR(self) -> Path:
        return self.STATIC_DIR / "images"
    
    @property
    def STATIC_MAPS_DIR(self) -> Path:
        return self.STATIC_DIR / "maps"
    
    @property
    def MEDIA_ROOT(self) -> Path:
        return BASE_DIR / "media"

    # === App ===
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # Flags middlewares (DEV = valeurs ci-dessous)
    ENABLE_HTTPS_REDIRECT: bool = True
    TRUSTED_HOST_STRICT: bool = False
    RATE_LIMITING_ENABLED: bool = False
    IP_FILTER_ENABLED: bool = False
    UA_FILTER_ENABLED: bool = False
    CSP_ENABLED: bool = False
    REQUEST_SIZE_LIMIT_ENABLED: bool = False
    GZIP_ENABLED: bool = False
    CACHE_ENABLED: bool = False
    SECURITY_HEADERS_ENABLED: bool = False
    CORS_ALLOW_ALL: bool = False

    # === Divers ===
    ADMIN_EMAIL: str = "sorolassina58@gmail.com"
    MAX_FILE_SIZE: int = 10_485_760  # 10MB

    # === Couleurs du thème ===
    THEME_PRIMARY: str = "rgb(255, 211, 0)"  # Jaune
    THEME_SECONDARY: str = "#000000"  # Noir
    THEME_WHITE: str = "#FFFFFF"  # Blanc

    # Constante non issue de l'env (pas un champ)
    VERSION: ClassVar[str] = "1.0.0"
    APP_NAME: ClassVar[str] = "LIA Coaching"
    AUTHOR: ClassVar[str] = "Soro Wangboho Lassina"

    # Autoriser "ALLOWED_HOSTS=localhost,127.0.0.1" dans .env
    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def _split_hosts(cls, v):
        if isinstance(v, str):
            return [h.strip() for h in v.split(",") if h.strip()]
        return v

    @staticmethod
    def get_pdf_path(filename: str) -> str:
        """Retourne le chemin absolu d'un fichier PDF dans le dossier fichiers/"""
        return os.path.join(FICHIERS_DIR, filename)

    @staticmethod
    def get_media_url(path: str) -> str:
        """Génère une URL pour les ressources médias selon l'environnement"""
        # Détecter l'environnement
        environnement = os.environ.get('ENVIRONNEMENT', 'development').lower()
        
        if environnement == 'production':
            base_url = "https://mca-services.onrender.com"
        else:
            base_url = "http://localhost:8000"
        
        return f"{base_url}/media/{path.lstrip('/')}"

    @staticmethod
    def get_base_url_for_email() -> str:
        """Génère l'URL de base pour les emails selon l'environnement"""
        environnement = os.environ.get('ENVIRONNEMENT', 'development').lower()
        
        if environnement == 'production':
            return "https://mca-services.onrender.com"
        else:
            return "http://localhost:8000"

    @staticmethod
    def get_static_url(path: str) -> str:
        """Génère une URL pour les ressources statiques selon l'environnement"""
        # Détecter l'environnement
        environnement = os.environ.get('ENVIRONNEMENT', 'development').lower()
        
        if environnement == 'production':
            # Production : utiliser l'URL HTTPS de Render
            base_url = "https://mca-services.onrender.com"
        else:
            # Développement local : utiliser l'URL locale
            base_url = "http://localhost:8000"
        
        return f"{base_url}/static/{path.lstrip('/')}"

    @staticmethod
    def get_base_url(request: Request) -> str:
        """Détecte dynamiquement l'URL de l'API"""
        base_url = str(request.base_url).rstrip("/")
        return base_url

    def ensure_directories(self):
        """Crée les dossiers s'ils n'existent pas - À APPELER MANUELLEMENT"""
        directories = [
            BASE_DIR / self.UPLOAD_DIR,
            self.STATIC_IMAGES_DIR, 
            BASE_DIR / self.STATIC_DOCS_DIR,
            self.STATIC_DIR, 
            self.FICHIERS_DIR, 
            self.STATIC_MAPS_DIR, 
            self.MEDIA_ROOT
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Créer aussi les sous-dossiers statiques nécessaires
        (self.STATIC_DIR / "css").mkdir(exist_ok=True)
        (self.STATIC_DIR / "js").mkdir(exist_ok=True)
        (self.STATIC_DIR / "images").mkdir(exist_ok=True)
        (self.STATIC_DIR / "maps").mkdir(exist_ok=True)

settings = Settings()

