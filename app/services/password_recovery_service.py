"""
Service de récupération de mot de passe
"""
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Session, select, and_

from app_lia_web.app.models.password_recovery import PasswordRecoveryCode
from app_lia_web.app.models.base import User
from app_lia_web.core.security import get_password_hash
from app_lia_web.core.config import settings
from app_lia_web.app.services.ACD.mailer import SmtpMailer, EmailMessage, EmailContent

logger = logging.getLogger(__name__)


class PasswordRecoveryService:
    """Service de gestion de la récupération de mot de passe"""
    
    def __init__(self):
        self.mailer = SmtpMailer()
    
    def request_password_recovery(self, session: Session, email: str, ip_address: Optional[str] = None) -> bool:
        """
        Demande une récupération de mot de passe
        Retourne True si l'email existe et le code a été envoyé
        """
        # Vérifier que l'utilisateur existe
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            logger.warning(f"Tentative de récupération pour un email inexistant: {email}")
            return False
        
        # Invalider les codes précédents pour cet email
        self._invalidate_existing_codes(session, email)
        
        # Créer un nouveau code
        recovery_code = PasswordRecoveryCode.create_recovery_code(email, ip_address)
        session.add(recovery_code)
        session.commit()
        session.refresh(recovery_code)
        
        # Envoyer l'email
        success = self._send_recovery_email(email, user.nom_complet, recovery_code.code)
        
        if success:
            logger.info(f"Code de récupération envoyé à {email}")
        else:
            logger.error(f"Échec envoi code de récupération à {email}")
            # Supprimer le code si l'email n'a pas pu être envoyé
            session.delete(recovery_code)
            session.commit()
        
        return success
    
    def verify_recovery_code(self, session: Session, email: str, code: str) -> bool:
        """
        Vérifie un code de récupération
        Retourne True si le code est valide
        """
        recovery_code = session.exec(
            select(PasswordRecoveryCode).where(
                and_(
                    PasswordRecoveryCode.email == email,
                    PasswordRecoveryCode.code == code,
                    PasswordRecoveryCode.used == False
                )
            )
        ).first()
        
        if not recovery_code:
            logger.warning(f"Code de récupération invalide pour {email}: {code}")
            return False
        
        if not recovery_code.is_valid():
            logger.warning(f"Code de récupération expiré pour {email}")
            return False
        
        return True
    
    def reset_password(self, session: Session, email: str, code: str, new_password: str) -> bool:
        """
        Réinitialise le mot de passe avec un code valide
        Retourne True si la réinitialisation a réussi
        """
        # Vérifier le code
        recovery_code = session.exec(
            select(PasswordRecoveryCode).where(
                and_(
                    PasswordRecoveryCode.email == email,
                    PasswordRecoveryCode.code == code,
                    PasswordRecoveryCode.used == False
                )
            )
        ).first()
        
        if not recovery_code or not recovery_code.is_valid():
            logger.warning(f"Tentative de réinitialisation avec un code invalide pour {email}")
            return False
        
        # Récupérer l'utilisateur
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            logger.error(f"Utilisateur introuvable pour la réinitialisation: {email}")
            return False
        
        # Mettre à jour le mot de passe
        user.mot_de_passe_hash = get_password_hash(new_password)
        session.add(user)
        
        # Marquer le code comme utilisé
        recovery_code.mark_as_used()
        session.add(recovery_code)
        
        session.commit()
        
        logger.info(f"Mot de passe réinitialisé avec succès pour {email}")
        return True
    
    def _invalidate_existing_codes(self, session: Session, email: str):
        """Invalide tous les codes existants pour un email"""
        existing_codes = session.exec(
            select(PasswordRecoveryCode).where(
                and_(
                    PasswordRecoveryCode.email == email,
                    PasswordRecoveryCode.used == False
                )
            )
        ).all()
        
        for code in existing_codes:
            code.used = True
            code.used_at = datetime.now(timezone.utc)
            session.add(code)
        
        session.commit()
    
    def _send_recovery_email(self, email: str, nom_complet: str, code: str) -> bool:
        """Envoie l'email avec le code de récupération"""
        try:
            subject = f"Récupération de mot de passe - {settings.APP_NAME}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Récupération de mot de passe</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f8f9fa;
                    }}
                    .container {{
                        background: white;
                        padding: 30px;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo {{
                        color: {settings.THEME_PRIMARY};
                        font-size: 24px;
                        font-weight: bold;
                        margin-bottom: 10px;
                    }}
                    .code-container {{
                        background: {settings.THEME_PRIMARY};
                        color: {settings.THEME_SECONDARY};
                        padding: 20px;
                        border-radius: 8px;
                        text-align: center;
                        margin: 20px 0;
                    }}
                    .code {{
                        font-size: 32px;
                        font-weight: bold;
                        letter-spacing: 5px;
                        margin: 10px 0;
                    }}
                    .warning {{
                        background: #fff3cd;
                        border: 1px solid #ffeaa7;
                        color: #856404;
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .footer {{
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid #eee;
                        font-size: 12px;
                        color: #666;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">{settings.APP_NAME}</div>
                        <h1>Récupération de mot de passe</h1>
                    </div>
                    
                    <p>Bonjour <strong>{nom_complet}</strong>,</p>
                    
                    <p>Vous avez demandé une récupération de mot de passe pour votre compte <strong>{settings.APP_NAME}</strong>.</p>
                    
                    <div class="code-container">
                        <p>Votre code de récupération est :</p>
                        <div class="code">{code}</div>
                        <p><small>Ce code est valide pendant 15 minutes</small></p>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ Important :</strong>
                        <ul>
                            <li>Ce code est valide pendant <strong>15 minutes</strong> uniquement</li>
                            <li>Ne partagez jamais ce code avec personne</li>
                            <li>Si vous n'avez pas demandé cette récupération, ignorez cet email</li>
                        </ul>
                    </div>
                    
                    <p>Pour réinitialiser votre mot de passe :</p>
                    <ol>
                        <li>Retournez sur la page de récupération</li>
                        <li>Saisissez votre email et ce code</li>
                        <li>Choisissez votre nouveau mot de passe</li>
                    </ol>
                    
                    <div class="footer">
                        <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
                        <p>{settings.APP_NAME} - {settings.AUTHOR}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Récupération de mot de passe - {settings.APP_NAME}
            
            Bonjour {nom_complet},
            
            Vous avez demandé une récupération de mot de passe pour votre compte {settings.APP_NAME}.
            
            Votre code de récupération est : {code}
            
            Ce code est valide pendant 15 minutes uniquement.
            
            Pour réinitialiser votre mot de passe :
            1. Retournez sur la page de récupération
            2. Saisissez votre email et ce code
            3. Choisissez votre nouveau mot de passe
            
            ⚠️ Important :
            - Ne partagez jamais ce code avec personne
            - Si vous n'avez pas demandé cette récupération, ignorez cet email
            
            Cet email a été envoyé automatiquement, merci de ne pas y répondre.
            
            {settings.APP_NAME} - {settings.AUTHOR}
            """
            
            message = EmailMessage(
                to=[email],
                subject=subject,
                html=html_content,
                text=text_content
            )
            
            self.mailer.send(message)
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email de récupération: {e}")
            return False
    
    def cleanup_expired_codes(self, session: Session) -> int:
        """
        Nettoie les codes expirés
        Retourne le nombre de codes supprimés
        """
        expired_codes = session.exec(
            select(PasswordRecoveryCode).where(
                PasswordRecoveryCode.expires_at < datetime.now(timezone.utc)
            )
        ).all()
        
        count = len(expired_codes)
        for code in expired_codes:
            session.delete(code)
        
        session.commit()
        
        if count > 0:
            logger.info(f"Nettoyage de {count} codes de récupération expirés")
        
        return count
