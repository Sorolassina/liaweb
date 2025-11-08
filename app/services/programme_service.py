"""
Service de gestion des programmes
"""
from typing import List, Optional
from sqlmodel import Session, select
import logging
from ..models.base import Programme
from ..schemas import ProgrammeCreate, ProgrammeUpdate

logger = logging.getLogger(__name__)


class ProgrammeService:
    """Service de gestion des programmes"""
    
    @staticmethod
    def create_programme(session: Session, programme_data: ProgrammeCreate) -> Programme:
        """Crée un nouveau programme"""
        programme = Programme(**programme_data.dict())
        session.add(programme)
        session.commit()
        session.refresh(programme)
        return programme
    
    @staticmethod
    def get_programme_by_code(session: Session, code: str) -> Optional[Programme]:
        """Récupère un programme par code"""
        return session.exec(select(Programme).where(Programme.code == code)).first()
    
    @staticmethod
    def get_active_programmes(session: Session) -> List[Programme]:
        """Récupère tous les programmes actifs"""
        return session.exec(select(Programme).where(Programme.actif == True)).all()
    
    @staticmethod
    def update_programme(session: Session, programme_id: int, programme_data: ProgrammeUpdate) -> Optional[Programme]:
        """Met à jour un programme"""
        programme = session.get(Programme, programme_id)
        if not programme:
            return None
        
        update_data = programme_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(programme, field, value)
        
        session.add(programme)
        session.commit()
        session.refresh(programme)
        return programme
