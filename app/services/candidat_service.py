"""
Service de gestion des candidats
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
import logging
from app_lia_web.app.models.base import Candidat, Entreprise
from app_lia_web.app.models.preinscription import Preinscription
from app_lia_web.app.schemas import CandidatCreate, CandidatUpdate, CandidatFiltres, PaginationParams
from app_lia_web.core.program_schema_integration import safe_count_query, table_exists_anywhere

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
        """Récupère un candidat par email - Version sécurisée"""
        if not table_exists_anywhere("candidat", session):
            return None
        try:
            return session.exec(select(Candidat).where(Candidat.email == email)).first()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du candidat par email: {e}")
            return None
    
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
        
        # Pagination - Version sécurisée
        offset = (pagination.page - 1) * pagination.taille
        total = 0
        if table_exists_anywhere("candidat", session):
            total = safe_count_query(session, Candidat)
        
        candidats = []
        if table_exists_anywhere("candidat", session):
            try:
                candidats = session.exec(query.offset(offset).limit(pagination.taille)).all()
            except Exception as e:
                logging.warning(f"Erreur lors de la récupération des candidats avec filtres: {e}")
                candidats = []
        
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
