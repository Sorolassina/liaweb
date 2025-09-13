"""
Service de gestion des entreprises
"""
from typing import Optional
from sqlmodel import Session, select
import logging
from app_lia_web.app.models.base import Entreprise
from app_lia_web.app.schemas import EntrepriseCreate
from app_lia_web.core.utils import PappersUtils, QPVUtils

logger = logging.getLogger(__name__)


class EntrepriseService:
    """Service de gestion des entreprises"""
    
    @staticmethod
    def create_entreprise(session: Session, entreprise_data: EntrepriseCreate) -> Entreprise:
        """Crée une nouvelle entreprise"""
        entreprise = Entreprise(**entreprise_data.dict())
        session.add(entreprise)
        session.commit()
        session.refresh(entreprise)
        return entreprise
    
    @staticmethod
    def get_entreprise_by_candidat(session: Session, candidat_id: int) -> Optional[Entreprise]:
        """Récupère l'entreprise d'un candidat"""
        return session.exec(select(Entreprise).where(Entreprise.candidat_id == candidat_id)).first()
    
    @staticmethod
    def update_entreprise_from_pappers(session: Session, entreprise_id: int, siret: str) -> Optional[Entreprise]:
        """Met à jour les informations d'entreprise depuis l'API Pappers"""
        entreprise = session.get(Entreprise, entreprise_id)
        if not entreprise:
            return None
        
        # Récupérer les données depuis Pappers
        pappers_data = PappersUtils.get_company_info(siret)
        if pappers_data:
            # Mettre à jour les champs avec les données Pappers
            entreprise.siren = pappers_data.get("siren")
            entreprise.raison_sociale = pappers_data.get("denomination")
            entreprise.code_naf = pappers_data.get("code_naf")
            entreprise.date_creation = pappers_data.get("date_creation")
            entreprise.adresse = pappers_data.get("adresse")
            
            session.add(entreprise)
            session.commit()
            session.refresh(entreprise)
        
        return entreprise
    
    @staticmethod
    def check_qpv_status(session: Session, entreprise_id: int) -> bool:
        """Vérifie le statut QPV d'une entreprise"""
        entreprise = session.get(Entreprise, entreprise_id)
        if not entreprise or not entreprise.adresse:
            return False
        
        qpv_result = QPVUtils.check_qpv_status(entreprise.adresse)
        entreprise.qpv = qpv_result.get("is_qpv", False)
        
        session.add(entreprise)
        session.commit()
        
        return entreprise.qpv
