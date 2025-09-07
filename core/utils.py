"""
Module utilitaire pour les traitements communs
"""
import os
import json
import logging
import shutil
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import requests
from fastapi import UploadFile
from ..core.config import settings

logger = logging.getLogger(__name__)


class FileUtils:
    """Utilitaires pour la gestion des fichiers"""
    
    @staticmethod
    def ensure_upload_dir() -> str:
        """Crée le répertoire d'upload s'il n'existe pas"""
        from .config import Settings
        settings = Settings()
        upload_path = settings.BASE_DIR / settings.UPLOAD_DIR
        upload_path.mkdir(parents=True, exist_ok=True)
        return str(upload_path)
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Extrait l'extension d'un fichier"""
        return os.path.splitext(filename)[1].lower()
    
    @staticmethod
    def is_allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
        """Vérifie si le fichier a une extension autorisée"""
        return FileUtils.get_file_extension(filename) in allowed_extensions
    
    @staticmethod
    def save_upload_file(file: UploadFile, destination_dir: str, filename: str) -> str:
        """Sauvegarde un fichier uploadé et retourne le chemin complet"""
        from .config import Settings
        settings = Settings()
        
        # Créer le chemin de destination
        dest_path = settings.BASE_DIR / destination_dir
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Chemin complet du fichier
        file_path = dest_path / filename
        
        # Sauvegarder le fichier
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        return str(file_path)
    
    @staticmethod
    def validate_file_upload(file: UploadFile, allowed_mime_types: List[str], max_size_mb: int) -> None:
        """Valide un fichier uploadé"""
        from fastapi import HTTPException
        
        # Vérifier le type MIME
        if file.content_type not in allowed_mime_types:
            raise HTTPException(
                status_code=400,
                detail=f"Type de fichier non autorisé. Types autorisés: {', '.join(allowed_mime_types)}"
            )
        
        # Vérifier la taille
        if file.size > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Fichier trop volumineux. Taille maximum: {max_size_mb}MB"
            )

    @staticmethod
    def get_file_size_mb(file_path: str) -> float:
        """Retourne la taille d'un fichier en MB"""
        return os.path.getsize(file_path) / (1024 * 1024)


class QPVUtils:
    """Utilitaires pour la vérification QPV"""
    
    @staticmethod
    def check_qpv_status(address: str) -> Dict[str, Any]:
        """
        Vérifie si une adresse est en QPV
        TODO: Implémenter l'appel à l'API QPV
        """
        # Simulation pour le moment
        return {
            "is_qpv": False,
            "confidence": 0.8,
            "source": "simulation"
        }


class PappersUtils:
    """Utilitaires pour l'API Pappers"""
    
    @staticmethod
    def get_company_info(siret: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une entreprise via l'API Pappers"""
        if not settings.PAPPERS_API_KEY:
            logger.warning("Clé API Pappers non configurée")
            return None
            
        try:
            headers = {
                "Authorization": f"Bearer {settings.PAPPERS_API_KEY}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"https://api.pappers.fr/v2/entreprise/{siret}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Erreur API Pappers: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de l'appel API Pappers: {e}")
            return None


class EligibilityUtils:
    """Utilitaires pour le calcul d'éligibilité"""
    
    @staticmethod
    def calculate_ca_score(chiffre_affaires: float, seuil_min: float, seuil_max: float) -> Dict[str, Any]:
        """Calcule le score basé sur le chiffre d'affaires"""
        if chiffre_affaires < seuil_min:
            return {
                "score": 0,
                "status": "insuffisant",
                "message": f"CA inférieur au seuil minimum ({seuil_min}€)"
            }
        elif chiffre_affaires > seuil_max:
            return {
                "score": 100,
                "status": "excellent",
                "message": f"CA supérieur au seuil maximum ({seuil_max}€)"
            }
        else:
            # Score proportionnel entre min et max
            score = ((chiffre_affaires - seuil_min) / (seuil_max - seuil_min)) * 100
            return {
                "score": round(score, 2),
                "status": "correct",
                "message": f"CA dans la fourchette cible ({seuil_min}€ - {seuil_max}€)"
            }
    
    @staticmethod
    def calculate_anciennete_score(date_creation: date, seuil_min_annees: int) -> Dict[str, Any]:
        """Calcule le score basé sur l'ancienneté de l'entreprise"""
        if not date_creation:
            return {
                "score": 0,
                "status": "inconnu",
                "message": "Date de création non renseignée"
            }
        
        aujourd_hui = date.today()
        anciennete_annees = (aujourd_hui - date_creation).days / 365.25
        
        if anciennete_annees >= seuil_min_annees:
            return {
                "score": 100,
                "status": "suffisant",
                "message": f"Ancienneté suffisante ({anciennete_annees:.1f} ans)"
            }
        else:
            return {
                "score": 0,
                "status": "insuffisant",
                "message": f"Ancienneté insuffisante ({anciennete_annees:.1f} ans < {seuil_min_annees} ans)"
            }


class EmailUtils:
    """Utilitaires pour l'envoi d'emails"""
    
    @staticmethod
    def send_welcome_email(email: str, nom: str, programme: str) -> bool:
        """Envoie un email de bienvenue"""
        # TODO: Implémenter l'envoi d'email
        logger.info(f"Email de bienvenue envoyé à {email} pour le programme {programme}")
        return True
    
    @staticmethod
    def send_inscription_confirmation(email: str, nom: str, programme: str, conseiller: str) -> bool:
        """Envoie un email de confirmation d'inscription"""
        # TODO: Implémenter l'envoi d'email
        logger.info(f"Email de confirmation d'inscription envoyé à {email}")
        return True


class JsonUtils:
    """Utilitaires pour la gestion JSON"""
    
    @staticmethod
    def safe_json_loads(data: str) -> Optional[Dict[str, Any]]:
        """Charge un JSON de manière sécurisée"""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    
    @staticmethod
    def safe_json_dumps(data: Any) -> str:
        """Sérialise en JSON de manière sécurisée"""
        try:
            return json.dumps(data, default=str)
        except (TypeError, ValueError):
            return "{}"


class ValidationUtils:
    """Utilitaires pour la validation"""
    
    @staticmethod
    def validate_siret(siret: str) -> bool:
        """Valide un numéro SIRET"""
        if not siret or len(siret) != 14:
            return False
        return siret.isdigit()
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Valide un email"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Valide un numéro de téléphone français"""
        import re
        # Supprime les espaces et caractères spéciaux
        clean_phone = re.sub(r'[\s\-\(\)\.]', '', phone)
        # Vérifie si c'est un numéro français valide
        return bool(re.match(r'^(?:(?:\+|00)33|0)\s*[1-9](?:[\s\-]*\d{2}){4}$', phone))
