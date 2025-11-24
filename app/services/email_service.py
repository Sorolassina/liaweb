# app/services/email_service.py
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from ..core.config import settings
from ..core.utils import EmailUtils
from ..models.admin import AppSetting
from jinja2 import Environment, FileSystemLoader
import os

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialise le service email avec les paramètres SMTP.
        Les paramètres sont récupérés depuis la base de données (AppSetting) avec fallback sur settings.
        """
        # Récupérer les paramètres depuis la base de données si une session est fournie
        if db_session:
            self.smtp_server = self._get_setting(db_session, "SMTP_HOST", settings.SMTP_HOST)
            self.smtp_port = self._get_setting_int(db_session, "SMTP_PORT", settings.SMTP_PORT)
            self.smtp_username = self._get_setting(db_session, "SMTP_USER", settings.SMTP_USER)
            self.smtp_password = self._get_setting(db_session, "SMTP_PASSWORD", settings.SMTP_PASSWORD)
            self.from_email = self._get_setting(db_session, "MAIL_FROM", settings.MAIL_FROM)
        else:
            # Fallback sur les paramètres de configuration si pas de session
            self.smtp_server = settings.SMTP_HOST
            self.smtp_port = settings.SMTP_PORT
            self.smtp_username = settings.SMTP_USER
            self.smtp_password = settings.SMTP_PASSWORD
            self.from_email = settings.MAIL_FROM
        
        # Configuration Jinja2 pour les templates d'email
        # Chercher dans plusieurs emplacements possibles
        template_dirs = [
            os.path.join(os.path.dirname(__file__), '..', 'templates', 'emails'),
            os.path.join(os.path.dirname(__file__), '..', 'templates', 'pages', 'emails'),
        ]
        self.jinja_env = None
        for template_dir in template_dirs:
            if os.path.exists(template_dir):
                self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
                logger.info(f"📧 Templates d'email trouvés dans: {template_dir}")
                break
        
        if not self.jinja_env:
            logger.warning("⚠️ Aucun répertoire de templates d'email trouvé")
    
    def _get_setting(self, session: Session, key: str, default: str = "") -> str:
        """Récupérer un paramètre depuis AppSetting avec fallback"""
        try:
            setting = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
            return setting.value if setting and setting.value else default
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la récupération du paramètre {key}: {e}")
            return default
    
    def _get_setting_int(self, session: Session, key: str, default: int = 587) -> int:
        """Récupérer un paramètre entier depuis AppSetting avec fallback"""
        try:
            setting = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
            if setting and setting.value:
                return int(setting.value)
            return default
        except (ValueError, Exception) as e:
            logger.warning(f"⚠️ Erreur lors de la récupération du paramètre {key}: {e}")
            return default
    
    def update_smtp_settings(self, db_session: Session):
        """Mettre à jour les paramètres SMTP depuis la base de données"""
        self.smtp_server = self._get_setting(db_session, "SMTP_HOST", settings.SMTP_HOST)
        self.smtp_port = self._get_setting_int(db_session, "SMTP_PORT", settings.SMTP_PORT)
        self.smtp_username = self._get_setting(db_session, "SMTP_USER", settings.SMTP_USER)
        self.smtp_password = self._get_setting(db_session, "SMTP_PASSWORD", settings.SMTP_PASSWORD)
        self.from_email = self._get_setting(db_session, "MAIL_FROM", settings.MAIL_FROM)
        
    def send_rdv_invitation(self, 
                           to_email: str, 
                           candidat_nom: str, 
                           candidat_prenom: str,
                           rdv_id: int,
                           rdv_date: str,
                           rdv_type: str,
                           programme_nom: str,
                           conseiller_nom: str = "Conseiller non assigné") -> bool:
        """Envoie un email d'invitation pour un rendez-vous vidéo"""
        return EmailUtils.send_rdv_invitation(
            to_email=to_email,
            candidat_nom=candidat_nom,
            candidat_prenom=candidat_prenom,
            rdv_id=rdv_id,
            rdv_date=rdv_date,
            rdv_type=rdv_type,
            programme_nom=programme_nom,
            conseiller_nom=conseiller_nom
        )
    
    def send_template_email(self, to_email: str, subject: str, template: str, data: Dict[str, Any]) -> bool:
        """Envoie un email en utilisant un template HTML"""
        try:
            # Générer le contenu HTML à partir du template
            html_content = None
            if self.jinja_env:
                try:
                    template_obj = self.jinja_env.get_template(f"{template}.html")
                    html_content = template_obj.render(**data)
                    logger.info(f"✅ Template {template}.html chargé avec succès")
                except Exception as template_error:
                    logger.warning(f"⚠️ Erreur lors du chargement du template {template}.html: {template_error}")
                    logger.info("📧 Utilisation du template de fallback")
                    html_content = None
            
            # Fallback si pas de template ou erreur de chargement
            if not html_content:
                html_content = f"""
                <html>
                <body>
                    <h2>{subject}</h2>
                    <p>Bonjour {data.get('nom', '')},</p>
                    <p>Vous êtes invité au séminaire : {data.get('seminaire_titre', '')}</p>
                    <p>Description : {data.get('seminaire_description', '')}</p>
                    <p>Dates : du {data.get('date_debut', '')} au {data.get('date_fin', '')}</p>
                    <p>Lieu : {data.get('lieu', '')}</p>
                    <p>Pour accepter l'invitation, cliquez sur ce lien : <a href="{data.get('accept_url', '')}">Accepter</a></p>
                    <p>Pour refuser l'invitation, cliquez sur ce lien : <a href="{data.get('reject_url', '')}">Refuser</a></p>
                </body>
                </html>
                """
            
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Ajouter le contenu HTML
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Vérifier la configuration SMTP
            if not self.smtp_server or not self.smtp_port:
                logger.warning(f"⚠️ Configuration SMTP manquante - simulation d'envoi d'email à {to_email}")
                logger.info(f"📧 EMAIL SIMULÉ - {subject} pour {to_email}")
                logger.info(f"🔍 Contenu HTML (premiers 300 chars): {html_content[:300]}")
                return True  # Retourner True pour permettre le développement sans SMTP
            
            # Envoyer l'email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_username and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
                logger.info(f"✅ Email envoyé avec succès à {to_email}: {subject}")
                return True
                
        except smtplib.SMTPException as e:
            logger.error(f"❌ Erreur SMTP lors de l'envoi de l'email à {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi de l'email à {to_email}: {e}", exc_info=True)
            return False