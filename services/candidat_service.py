"""
Service de gestion des candidats
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
import logging
from ..models.base import Candidat, Preinscription, Entreprise
from ..schemas import CandidatCreate, CandidatUpdate, CandidatFiltres, PaginationParams

logger = logging.getLogger(__name__)


class CandidatService:
    """Service de gestion des candidats"""
    
    @staticmethod
    def create_candidat(session: Session, candidat_data: CandidatCreate) -> Candidat:
        """Crée un nouveau candidat"""
        candidat = Candidat(**candidat_data.dict())
        session.add(candidat)
        session.commit()
        session.refresh(candidat)
        return candidat
    
    @staticmethod
    def get_candidat_by_email(session: Session, email: str) -> Optional[Candidat]:
        """Récupère un candidat par email"""
        return session.exec(select(Candidat).where(Candidat.email == email)).first()
    
    @staticmethod
    def get_candidats_with_filters(session: Session, filtres: CandidatFiltres, pagination: PaginationParams) -> Dict[str, Any]:
        """Récupère les candidats avec filtres et pagination"""
        query = select(Candidat)
        
        # Appliquer les filtres
        if filtres.programme_id:
            query = query.join(Preinscription).where(Preinscription.programme_id == filtres.programme_id)
        
        if filtres.handicap is not None:
            query = query.where(Candidat.handicap == filtres.handicap)
        
        if filtres.territoire:
            query = query.join(Entreprise).where(Entreprise.territoire == filtres.territoire)
        
        # Pagination
        offset = (pagination.page - 1) * pagination.taille
        total = session.exec(select(Candidat)).count()
        
        candidats = session.exec(query.offset(offset).limit(pagination.taille)).all()
        
        return {
            "items": candidats,
            "total": total,
            "page": pagination.page,
            "taille": pagination.taille,
            "pages": (total + pagination.taille - 1) // pagination.taille
        }
    
    @staticmethod
    def update_candidat(session: Session, candidat_id: int, candidat_data: CandidatUpdate) -> Optional[Candidat]:
        """Met à jour un candidat"""
        candidat = session.get(Candidat, candidat_id)
        if not candidat:
            return None
        
        update_data = candidat_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(candidat, field, value)
        
        session.add(candidat)
        session.commit()
        session.refresh(candidat)
        return candidat
