"""
Service de gestion des jurys
"""
from typing import List
from sqlmodel import Session, select
import logging
from ..models.base import Jury, MembreJury
from ..schemas import JuryCreate

logger = logging.getLogger(__name__)


class JuryService:
    """Service de gestion des jurys"""
    
    @staticmethod
    def create_jury(session: Session, jury_data: JuryCreate) -> Jury:
        """Crée une nouvelle session de jury"""
        jury = Jury(**jury_data.dict())
        session.add(jury)
        session.commit()
        session.refresh(jury)
        return jury
    
    @staticmethod
    def get_jurys_by_programme(session: Session, programme_id: int) -> List[Jury]:
        """Récupère les jurys d'un programme"""
        return session.exec(
            select(Jury)
            .where(Jury.programme_id == programme_id)
            .order_by(Jury.session_le.desc())
        ).all()
    
    @staticmethod
    def add_jury_member(session: Session, jury_id: int, utilisateur_id: int, role: str = "membre") -> MembreJury:
        """Ajoute un membre au jury"""
        membre = MembreJury(
            jury_id=jury_id,
            utilisateur_id=utilisateur_id,
            role=role
        )
        session.add(membre)
        session.commit()
        session.refresh(membre)
        return membre
