# app/services/email_service.py
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from ..core.config import settings
from ..core.utils import EmailUtils

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.MAIL_FROM
        
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