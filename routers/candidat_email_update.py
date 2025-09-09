# app/routers/candidat_email_update.py
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlmodel import Session, select
from typing import Optional
import logging

from ..core.database import get_session
from ..core.security import get_current_user
from ..models.base import User, Candidat, Preinscription, Inscription, Document, Entreprise
from ..models.enums import UserRole

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/candidats/{candidat_id}/changer-email")
def changer_email_candidat(
    candidat_id: int,
    nouvel_email: str = Form(...),
    confirmation_email: str = Form(...),
    raison: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Change l'email d'un candidat de manière sécurisée
    Nécessite des permissions administrateur et confirmation
    """
    logger.info(f"📧 Changement email candidat {candidat_id} - User: {current_user.email}")
    
    # Vérifier les permissions
    if current_user.role not in ["administrateur", "coordinateur"]:
        raise HTTPException(status_code=403, detail="Seuls les administrateurs peuvent changer l'email d'un candidat")
    
    # Vérifier la confirmation
    if nouvel_email != confirmation_email:
        raise HTTPException(status_code=400, detail="Les emails ne correspondent pas")
    
    # Récupérer le candidat
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")
    
    ancien_email = candidat.email
    
    # Vérifier que le nouvel email n'existe pas déjà
    existing_candidat = session.exec(select(Candidat).where(Candidat.email == nouvel_email)).first()
    if existing_candidat:
        raise HTTPException(status_code=400, detail="Un candidat avec cet email existe déjà")
    
    try:
        # 1. Mettre à jour l'email du candidat
        candidat.email = nouvel_email
        session.add(candidat)
        
        # 2. Note: Les préinscriptions stockent les données dans donnees_brutes_json
        # et sont liées au candidat via candidat_id, donc pas besoin de les mettre à jour
        
        # 3. Log de l'activité pour audit
        from ..services.ACD.audit import log_activity
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
        raise HTTPException(status_code=500, detail=f"Erreur lors du changement d'email: {str(e)}")

@router.get("/candidats/{candidat_id}/email-history")
def get_email_history(
    candidat_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère l'historique des changements d'email pour un candidat
    """
    # Vérifier les permissions
    if current_user.role not in ["administrateur", "coordinateur"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Récupérer le candidat
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")
    
    # Récupérer l'historique depuis les logs d'audit
    from ..models.base import ActivityLog
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
