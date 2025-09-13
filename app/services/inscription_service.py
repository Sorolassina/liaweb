"""
Service de gestion des inscriptions
"""
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime,timezone
import logging
from app_lia_web.app.models.base import Inscription
from app_lia_web.app.models.enums import StatutDossier
from app_lia_web.app.schemas import InscriptionCreate

logger = logging.getLogger(__name__)


class InscriptionService:
    """Service de gestion des inscriptions"""
    
    @staticmethod
    def create_inscription(session: Session, inscription_data: InscriptionCreate) -> Inscription:
        """Crée une nouvelle inscription"""
        inscription = Inscription(**inscription_data.dict())
        session.add(inscription)
        session.commit()
        session.refresh(inscription)
        return inscription
    
    @staticmethod
    def get_inscriptions_by_programme(session: Session, programme_id: int) -> List[Inscription]:
        """Récupère les inscriptions d'un programme"""
        return session.exec(
            select(Inscription)
            .where(Inscription.programme_id == programme_id)
            .order_by(Inscription.cree_le.desc())
        ).all()
    
    @staticmethod
    def update_inscription_status(session: Session, inscription_id: int, statut: StatutDossier) -> Optional[Inscription]:
        """Met à jour le statut d'une inscription"""
        inscription = session.get(Inscription, inscription_id)
        if not inscription:
            return None
        
        inscription.statut = statut
        inscription.date_decision = datetime.now(timezone.utc)
        
        session.add(inscription)
        session.commit()
        session.refresh(inscription)
        
        return inscription
