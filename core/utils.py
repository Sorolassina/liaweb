"""
Module utilitaire pour les traitements communs
"""
import os
import json
import logging
import shutil
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from pathlib import Path
import requests
from fastapi import UploadFile
from app_lia_web.core.config import settings

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


class MediaUtils:
    """Utilitaires pour la gestion des médias (images, vidéos, etc.)"""
    
    @staticmethod
    def encode_image_base64(image_path: str) -> str:
        """Encode une image en base64 pour l'email ou l'affichage web"""
        try:
            image_file_path = Path(image_path)
            if image_file_path.exists():
                # Vérifier la taille du fichier
                file_size = image_file_path.stat().st_size
                logger.info(f"🔍 Taille du fichier: {file_size} bytes ({file_size/1024:.1f} KB)")
                
                with open(image_file_path, "rb") as image_file:
                    image_data = image_file.read()
                    encoded_string = base64.b64encode(image_data).decode('utf-8')
                    
                    # Détecter le type MIME basé sur l'extension
                    extension = image_file_path.suffix.lower()
                    mime_type = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif',
                        '.webp': 'image/webp',
                        '.svg': 'image/svg+xml',
                        '.bmp': 'image/bmp',
                        '.tiff': 'image/tiff'
                    }.get(extension, 'image/png')
                    
                    result = f"data:{mime_type};base64,{encoded_string}"
                    logger.info(f"🔍 Base64 final: {len(result)} caractères")
                    return result
            else:
                logger.warning(f"Image non trouvée à {image_path}")
                return ""
        except Exception as e:
            logger.error(f"Erreur lors de l'encodage de l'image {image_path}: {e}")
            return ""
    
    @staticmethod
    def encode_logo_base64() -> str:
        """Encode le logo de l'entreprise en base64 pour l'email (redimensionné)"""
        logo_path = Path(__file__).parent.parent / "static" / "images" / "logo.png"
        logger.info(f"🔍 Chemin du logo: {logo_path}")
        logger.info(f"🔍 Logo existe: {logo_path.exists()}")
        
        # Redimensionner le logo pour l'email (max 200px de largeur)
        try:
            from PIL import Image
            import io
            
            with Image.open(logo_path) as img:
                # Calculer les nouvelles dimensions (max 100px de largeur pour email)
                max_width = 100
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"🔍 Logo redimensionné: {img.width}x{img.height}")
                
                # Convertir en PNG optimisé pour l'email
                buffer = io.BytesIO()
                img.save(buffer, format='PNG', optimize=True)
                image_data = buffer.getvalue()
                
                # Encoder en base64
                encoded_string = base64.b64encode(image_data).decode('utf-8')
                result = f"data:image/png;base64,{encoded_string}"
                
                logger.info(f"🔍 Base64 final (redimensionné): {len(result)} caractères")
                return result
                
        except ImportError:
            logger.warning("PIL/Pillow non installé - utilisation du logo original")
            return MediaUtils.encode_image_base64(str(logo_path))
        except Exception as e:
            logger.error(f"Erreur lors du redimensionnement du logo: {e}")
            return MediaUtils.encode_image_base64(str(logo_path))
    
    @staticmethod
    def get_image_dimensions(image_path: str) -> tuple[int, int]:
        """Retourne les dimensions d'une image (largeur, hauteur)"""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return img.size
        except ImportError:
            logger.warning("PIL/Pillow non installé - impossible de récupérer les dimensions")
            return (0, 0)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des dimensions de {image_path}: {e}")
            return (0, 0)
    
    @staticmethod
    def resize_image_base64(image_base64: str, max_width: int = 800, max_height: int = 600) -> str:
        """Redimensionne une image encodée en base64"""
        try:
            from PIL import Image
            import io
            
            # Décoder le base64
            header, data = image_base64.split(',', 1)
            image_data = base64.b64decode(data)
            
            # Ouvrir l'image
            with Image.open(io.BytesIO(image_data)) as img:
                # Calculer les nouvelles dimensions
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Réencoder en base64
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                resized_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                return f"data:image/png;base64,{resized_data}"
        except ImportError:
            logger.warning("PIL/Pillow non installé - retour de l'image originale")
            return image_base64
        except Exception as e:
            logger.error(f"Erreur lors du redimensionnement de l'image: {e}")
            return image_base64


class EmailUtils:
    """Utilitaires pour l'envoi d'emails"""
    
    @staticmethod
    def envoyer_mail(to_email: str, objet: str, corps_html: str, corps_texte: str = None) -> bool:
        """Méthode générique pour envoyer un email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = objet
            msg['From'] = settings.MAIL_FROM
            msg['To'] = to_email
            
            # Ajouter la partie texte si fournie
            if corps_texte:
                part1 = MIMEText(corps_texte, 'plain', 'utf-8')
                msg.attach(part1)
            
            # Ajouter la partie HTML
            part2 = MIMEText(corps_html, 'html', 'utf-8')
            msg.attach(part2)
            
            # Debug du contenu HTML
            logger.info(f"🔍 HTML contient 'data:image': {'data:image' in corps_html}")
            logger.info(f"🔍 HTML contient 'base64': {'base64' in corps_html}")
            
            # Envoyer l'email
            if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
                logger.warning("Configuration SMTP manquante - simulation d'envoi d'email")
                logger.info(f"📧 EMAIL SIMULÉ - {objet} pour {to_email}")
                logger.info(f"🔍 Extrait HTML (premiers 200 chars): {corps_html[:200]}")
                return True
            
            # Connexion SMTP
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"✅ Email envoyé à {to_email}: {objet}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi de l'email: {e}")
            return False
    
    @staticmethod
    def send_rdv_invitation(to_email: str, 
                           candidat_nom: str, 
                           candidat_prenom: str,
                           rdv_id: int,
                           rdv_date: str,
                           rdv_type: str,
                           programme_nom: str,
                           conseiller_nom: str = "Conseiller non assigné") -> bool:
        """Envoie un email d'invitation pour un rendez-vous vidéo"""
        
        # Générer le lien d'invitation
        base_url_clean = settings.get_base_url_for_email()
        invitation_link = f"{base_url_clean}/video-rdv/{rdv_id}/invitation/candidat"
        
        # Encoder le logo en base64 pour l'email
        logo_base64 = MediaUtils.encode_logo_base64()
        
        # Fabriquer l'objet
        objet = f"Invitation à votre rendez-vous vidéo - {programme_nom}"
        
        # Fabriquer le corps HTML
        corps_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Invitation à votre rendez-vous vidéo</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: {settings.THEME_SECONDARY};
                    line-height: 1.6;
                    color: {settings.THEME_WHITE};
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: {settings.THEME_PRIMARY};
                    color: {settings.THEME_SECONDARY};
                    padding: 20px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header img {{
                    height: 60px;
                    margin-bottom: 10px;
                }}
                .content {{
                    background-color: {settings.THEME_WHITE};
                    color: #333;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .info-box {{
                    background-color: #f8f9fa;
                    border-left: 4px solid {settings.THEME_PRIMARY};
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .btn {{
                    display: inline-block;
                    background-color: {settings.THEME_PRIMARY};
                    color: {settings.THEME_SECONDARY};
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .btn:hover {{
                    background-color: {settings.THEME_SECONDARY};
                    color: {settings.THEME_PRIMARY};
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #666;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <img src="https://cdn.jaimelesstartups.fr/wp-content/uploads/2022/12/logo-my-creo-academy-1500x928.png" alt="LIA Coaching">
                <h2>Invitation Rendez-vous Vidéo</h2>
            </div>
            
            <div class="content">
                <p>Bonjour <strong>{candidat_prenom} {candidat_nom}</strong>,</p>
                
                <p>Vous êtes invité(e) à participer à votre rendez-vous vidéo de coaching via <strong>Visioconférence</strong>.</p>
                
                <div class="info-box">
                    <h3>📋 Détails du rendez-vous</h3>
                    <p><strong>Programme :</strong> {programme_nom}</p>
                    <p><strong>Type :</strong> {rdv_type}</p>
                    <p><strong>Date :</strong> {rdv_date}</p>
                    <p><strong>Conseiller :</strong> {conseiller_nom}</p>
                </div>
                
                <p>Pour rejoindre votre rendez-vous vidéo, cliquez simplement sur le bouton ci-dessous :</p>
                
                <div style="text-align: center;">
                    <a href="{invitation_link}" class="btn">🎬 Rejoindre LIA Coaching</a>
                </div>
                
                <div class="info-box">
                    <h3>💡 Instructions</h3>
                    <ul>
                        <li>Cliquez sur le bouton "Rejoindre LIA Coaching" ci-dessus</li>
                        <li>Autorisez l'accès à votre caméra et microphone</li>
                        <li>Vous pouvez utiliser LIA Coaching depuis votre navigateur</li>
                        <li>Assurez-vous d'avoir une connexion internet stable</li>
                        <li>Testez votre équipement avant le rendez-vous</li>
                    </ul>
                </div>
                
                <p><strong>Lien direct :</strong> <a href="{invitation_link}">{invitation_link}</a></p>
            </div>
            
            <div class="footer">
                <p>Cet email a été envoyé automatiquement par le système LIA Coaching.</p>
                <p>Si vous avez des questions, n'hésitez pas à contacter votre conseiller.</p>
            </div>
        </body>
        </html>
        """
        
        # Fabriquer le corps texte
        corps_texte = f"""
        Bonjour {candidat_prenom} {candidat_nom},
        
        Vous êtes invité(e) à participer à votre rendez-vous vidéo de coaching.
        
        Détails du rendez-vous :
        - Programme : {programme_nom}
        - Type : {rdv_type}
        - Date : {rdv_date}
        - Conseiller : {conseiller_nom}
        
        Pour rejoindre votre rendez-vous vidéo, cliquez sur ce lien :
        {invitation_link}
        
        Instructions :
        - Cliquez sur le lien ci-dessus pour rejoindre la visioconférence
        - Assurez-vous que votre micro et votre caméra fonctionnent
        - Rejoignez quelques minutes avant l'heure prévue
        - En cas de problème technique, contactez votre conseiller
        
        Cet email a été envoyé automatiquement par le système LIA Coaching.
        Si vous avez des questions, n'hésitez pas à contacter votre conseiller.
        """
        
        # Appeler la méthode générique
        return EmailUtils.envoyer_mail(to_email, objet, corps_html, corps_texte)
    
    @staticmethod
    def send_welcome_email(email: str, nom: str, programme: str) -> bool:
        """Envoie un email de bienvenue"""
        objet = f"Bienvenue dans le programme {programme}"
        
        corps_html = f"""
        <html>
        <body>
            <h1>Bienvenue {nom} !</h1>
            <p>Vous êtes maintenant inscrit au programme {programme}.</p>
        </body>
        </html>
        """
        
        corps_texte = f"Bienvenue {nom} ! Vous êtes maintenant inscrit au programme {programme}."
        
        return EmailUtils.envoyer_mail(email, objet, corps_html, corps_texte)
    
    @staticmethod
    def send_inscription_confirmation(email: str, nom: str, programme: str, conseiller: str) -> bool:
        """Envoie un email de confirmation d'inscription"""
        objet = f"Confirmation d'inscription - {programme}"
        
        corps_html = f"""
        <html>
        <body>
            <h1>Confirmation d'inscription</h1>
            <p>Bonjour {nom},</p>
            <p>Votre inscription au programme {programme} a été confirmée.</p>
            <p>Votre conseiller : {conseiller}</p>
        </body>
        </html>
        """
        
        corps_texte = f"Bonjour {nom}, votre inscription au programme {programme} a été confirmée. Votre conseiller : {conseiller}"
        
        return EmailUtils.envoyer_mail(email, objet, corps_html, corps_texte)
    
    @staticmethod
    def send_emargement_invitation(
        to_email: str,
        candidat_nom: str,
        candidat_prenom: str,
        rdv_id: int,
        rdv_date: str,
        rdv_type: str,
        lien_emargement: str
    ) -> bool:
        """Envoie un email d'invitation pour l'émargement d'un RDV"""
        logger.info(f"📧 Envoi invitation émargement - RDV {rdv_id} à {to_email}")
        
        try:
            from .config import settings
            
            # Construire l'URL complète
            base_url = settings.get_base_url_for_email()
            lien_complet = f"{base_url}{lien_emargement}"
            
            objet = f"✍️ Émargement requis - Rendez-vous du {rdv_date}"
            
            corps_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Émargement Rendez-vous</title>
            </head>
            <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    
                    <!-- En-tête -->
                    <div style="background: linear-gradient(135deg, {settings.THEME_PRIMARY} 0%, {settings.THEME_SECONDARY} 100%); color: {settings.THEME_WHITE}; padding: 30px; text-align: center;">
                        <img src="{settings.get_static_url('images/logo.png')}" alt="LIA Coaching" style="height: 60px; margin-bottom: 15px;">
                        <h1 style="margin: 0; font-size: 24px; font-weight: 600;">✍️ Émargement Requis</h1>
                        <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">Signature électronique pour votre rendez-vous</p>
                    </div>
                    
                    <!-- Contenu principal -->
                    <div style="padding: 40px 30px; color: #333333;">
                        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                            Bonjour <strong>{candidat_prenom} {candidat_nom}</strong>,
                        </p>
                        
                        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                            Votre rendez-vous de coaching approche et nous avons besoin de votre <strong>signature électronique</strong> 
                            pour confirmer votre présence.
                        </p>
                        
                        <!-- Informations du RDV -->
                        <div style="background-color: #e9ecef; border-left: 4px solid {settings.THEME_PRIMARY}; padding: 20px; margin: 25px 0; border-radius: 5px;">
                            <h3 style="margin: 0 0 15px 0; color: {settings.THEME_PRIMARY}; font-size: 18px;">📋 Détails du rendez-vous</h3>
                            <p style="margin: 8px 0; font-size: 15px;"><strong>Type :</strong> {rdv_type}</p>
                            <p style="margin: 8px 0; font-size: 15px;"><strong>Date :</strong> {rdv_date}</p>
                            <p style="margin: 8px 0; font-size: 15px;"><strong>ID RDV :</strong> #{rdv_id}</p>
                        </div>
                        
                        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                            <strong>Important :</strong> Votre signature est <strong>obligatoire</strong> pour pouvoir participer au rendez-vous. 
                            Sans cette signature, le rendez-vous ne pourra pas commencer.
                        </p>
                        
                        <!-- Bouton d'action -->
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{lien_complet}" style="display: inline-block; background: linear-gradient(135deg, {settings.THEME_PRIMARY} 0%, {settings.THEME_SECONDARY} 100%); color: {settings.THEME_WHITE}; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                                ✍️ Signer l'émargement
                            </a>
                        </div>
                        
                        <p style="font-size: 14px; color: #6c757d; margin-top: 25px; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                            <strong>🔒 Sécurité :</strong> Ce lien est personnel et sécurisé. Ne le partagez pas avec d'autres personnes.
                        </p>
                        
                        <p style="font-size: 14px; color: #6c757d; margin-top: 20px;">
                            <strong>Lien direct :</strong> <a href="{lien_complet}" style="color: {settings.THEME_PRIMARY}; text-decoration: none;">{lien_complet}</a>
                        </p>
                    </div>
                    
                    <!-- Pied de page -->
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #dee2e6;">
                        <p style="margin: 0; font-size: 12px; color: #6c757d;">
                            Cet email a été envoyé automatiquement par le système LIA Coaching.<br>
                            Si vous avez des questions, contactez votre conseiller.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            corps_texte = f"""
            ÉMARGEMENT REQUIS - RENDEZ-VOUS DU {rdv_date}
            
            Bonjour {candidat_prenom} {candidat_nom},
            
            Votre rendez-vous de coaching approche et nous avons besoin de votre signature électronique pour confirmer votre présence.
            
            DÉTAILS DU RENDEZ-VOUS :
            - Type : {rdv_type}
            - Date : {rdv_date}
            - ID RDV : #{rdv_id}
            
            IMPORTANT : Votre signature est OBLIGATOIRE pour pouvoir participer au rendez-vous. Sans cette signature, le rendez-vous ne pourra pas commencer.
            
            Pour signer votre émargement, cliquez sur le lien suivant :
            {lien_complet}
            
            Ce lien est personnel et sécurisé. Ne le partagez pas avec d'autres personnes.
            
            Cordialement,
            L'équipe LIA Coaching
            """
            
            return EmailUtils.envoyer_mail(
                to_email=to_email,
                objet=objet,
                corps_html=corps_html,
                corps_texte=corps_texte
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi de l'invitation d'émargement: {e}")
            return False


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
