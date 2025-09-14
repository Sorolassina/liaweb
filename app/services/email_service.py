# app/services/email_service.py
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from app_lia_web.core.config import settings
from app_lia_web.core.utils import EmailUtils
from jinja2 import Environment, FileSystemLoader
import os

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.MAIL_FROM
        
        # Configuration Jinja2 pour les templates d'email
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates', 'emails')
        if os.path.exists(template_dir):
            self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        else:
            self.jinja_env = None
        
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
            if self.jinja_env:
                template_obj = self.jinja_env.get_template(f"{template}.html")
                html_content = template_obj.render(**data)
            else:
                # Fallback si pas de template
                html_content = f"""
                <html>
                <body>
                    <h2>{subject}</h2>
                    <p>Bonjour {data.get('nom', '')},</p>
                    <p>Vous êtes invité au séminaire : {data.get('seminaire_titre', '')}</p>
                    <p>Description : {data.get('seminaire_description', '')}</p>
                    <p>Dates : du {data.get('date_debut', '')} au {data.get('date_fin', '')}</p>
                    <p>Lieu : {data.get('lieu', '')}</p>
                    <p>Token d'invitation : {data.get('token', '')}</p>
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
            
            # Envoyer l'email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_username and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
                logger.info(f"Email envoyé avec succès à {to_email}")
                return True
                
        except Exception as e:
            logger.error(f"Erreur envoi email à {to_email}: {e}")
            return False