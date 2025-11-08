"""
Service de gestion des emails candidats
"""
from typing import Dict, Any, List
from sqlmodel import Session, select
import logging

from ..models.base import Candidat, User
from ..models.activity import ActivityLog
from .audit import log_activity
from ..core.program_schema_integration import table_exists_anywhere

logger = logging.getLogger(__name__)


class CandidatEmailService:
    """Service de gestion des emails candidats"""
    
    @staticmethod
    def change_email_secure(
        session: Session,
        candidat_id: int,
        nouvel_email: str,
        confirmation_email: str,
        raison: str,
        current_user: User
    ) -> Dict[str, Any]:
        """
        Change l'email d'un candidat de manière sécurisée
        Nécessite des permissions administrateur et confirmation
        """
        logger.info(f"📧 Changement email candidat {candidat_id} - User: {current_user.email}")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"]:
            raise PermissionError("Seuls les administrateurs peuvent changer l'email d'un candidat")
        
        # Vérifier la confirmation
        if nouvel_email != confirmation_email:
            raise ValueError("Les emails ne correspondent pas")
        
        # Récupérer le candidat
        candidat = session.get(Candidat, candidat_id)
        if not candidat:
            raise ValueError("Candidat non trouvé")
        
        ancien_email = candidat.email
        
        # Vérifier que le nouvel email n'existe pas déjà - Version sécurisée
        existing_candidat = None
        if table_exists_anywhere("candidat", session):
            try:
                existing_candidat = session.exec(select(Candidat).where(Candidat.email == nouvel_email)).first()
            except Exception as e:
                logging.warning(f"Erreur lors de la vérification de l'email existant: {e}")
        
        if existing_candidat:
            raise ValueError("Un candidat avec cet email existe déjà")
        
        try:
            # Mettre à jour l'email du candidat
            candidat.email = nouvel_email
            session.add(candidat)
            
            # Note: Les préinscriptions stockent les données dans donnees_brutes_json
            # et sont liées au candidat via candidat_id, donc pas besoin de les mettre à jour
            
            # Log de l'activité pour audit
            log_activity(
                session=session,
                user=current_user,
                action="Changement email candidat",
                entity="Candidat",
                entity_id=candidat_id,
                activity_data={
                    "ancien_email": ancien_email,
                    "nouvel_email": nouvel_email,
                    "raison": raison
                }
            )
            
            # Valider la transaction
            session.commit()
            
            logger.info(f"✅ Email changé avec succès: {ancien_email} → {nouvel_email}")
            
            return {
                "status": "success",
                "message": f"Email changé avec succès de {ancien_email} vers {nouvel_email}",
                "ancien_email": ancien_email,
                "nouvel_email": nouvel_email
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du changement d'email: {str(e)}")
            session.rollback()
            raise
    
    @staticmethod
    def get_email_history(
        session: Session,
        candidat_id: int,
        current_user: User
    ) -> Dict[str, Any]:
        """
        Récupère l'historique des changements d'email pour un candidat
        """
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"]:
            raise PermissionError("Accès non autorisé")
        
        # Récupérer le candidat
        candidat = session.get(Candidat, candidat_id)
        if not candidat:
            raise ValueError("Candidat non trouvé")
        
        # Récupérer l'historique depuis les logs d'audit
        logs = session.exec(
            select(ActivityLog)
            .where(ActivityLog.entity == "Candidat")
            .where(ActivityLog.entity_id == candidat_id)
            .where(ActivityLog.action.like("%email%"))
            .order_by(ActivityLog.timestamp.desc())
        ).all()
        
        return {
            "candidat_id": candidat_id,
            "email_actuel": candidat.email,
            "historique": [
                {
                    "timestamp": log.timestamp,
                    "action": log.action,
                    "user": log.user_email,
                    "details": log.activity_data
                }
                for log in logs
            ]
        }
    
    @staticmethod
    def validate_email_change(
        session: Session,
        candidat_id: int,
        nouvel_email: str,
        current_user: User
    ) -> Dict[str, Any]:
        """
        Valide un changement d'email sans l'exécuter
        Retourne les erreurs potentielles
        """
        errors = []
        warnings = []
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"]:
            errors.append("Permissions insuffisantes")
        
        # Vérifier que le candidat existe
        candidat = session.get(Candidat, candidat_id)
        if not candidat:
            errors.append("Candidat non trouvé")
        else:
            # Vérifier si l'email change vraiment
            if candidat.email == nouvel_email:
                warnings.append("L'email est identique à l'actuel")
            
            # Vérifier que le nouvel email n'existe pas déjà - Version sécurisée
            existing_candidat = None
            if table_exists_anywhere("candidat", session):
                try:
                    existing_candidat = session.exec(select(Candidat).where(Candidat.email == nouvel_email)).first()
                except Exception as e:
                    logging.warning(f"Erreur lors de la vérification de l'email existant: {e}")
            
            if existing_candidat:
                errors.append("Un candidat avec cet email existe déjà")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
