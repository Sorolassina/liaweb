"""
Service de gestion des préinscriptions
"""
from typing import List
from sqlmodel import Session, select
from datetime import datetime,timezone
import logging
from ..models.base import Preinscription, Programme, Candidat, Entreprise, Eligibilite
from ..schemas import PreinscriptionCreate
from ..core.utils import EligibilityUtils

logger = logging.getLogger(__name__)


class PreinscriptionService:
    """Service de gestion des préinscriptions"""
    
    @staticmethod
    def create_preinscription(session: Session, preinscription_data: PreinscriptionCreate) -> Preinscription:
        """Crée une nouvelle préinscription"""
        preinscription = Preinscription(**preinscription_data.dict())
        session.add(preinscription)
        session.commit()
        session.refresh(preinscription)
        return preinscription
    
    @staticmethod
    def get_preinscriptions_by_programme(session: Session, programme_id: int) -> List[Preinscription]:
        """Récupère les préinscriptions d'un programme"""
        return session.exec(
            select(Preinscription)
            .where(Preinscription.programme_id == programme_id)
            .order_by(Preinscription.cree_le.desc())
        ).all()
    
    @staticmethod
    def calculate_eligibilite(session: Session, preinscription_id: int) -> Eligibilite:
        """Calcule l'éligibilité d'une préinscription"""
        preinscription = session.get(Preinscription, preinscription_id)
        if not preinscription:
            raise ValueError("Préinscription non trouvée")
        
        programme = session.get(Programme, preinscription.programme_id)
        candidat = session.get(Candidat, preinscription.candidat_id)
        entreprise = session.get(Entreprise, candidat.id) if candidat else None
        
        # Calculer les scores
        ca_score = None
        ca_seuil_ok = None
        if entreprise and entreprise.chiffre_affaires and programme.ca_seuil_min and programme.ca_seuil_max:
            ca_result = EligibilityUtils.calculate_ca_score(
                entreprise.chiffre_affaires,
                programme.ca_seuil_min,
                programme.ca_seuil_max
            )
            ca_score = ca_result["score"]
            ca_seuil_ok = ca_result["status"] != "insuffisant"
        
        anciennete_score = None
        anciennete_ok = None
        anciennete_annees = None
        if entreprise and entreprise.date_creation and programme.anciennete_min_annees:
            anciennete_result = EligibilityUtils.calculate_anciennete_score(
                entreprise.date_creation,
                programme.anciennete_min_annees
            )
            anciennete_score = anciennete_result["score"]
            anciennete_ok = anciennete_result["status"] == "suffisant"
            anciennete_annees = anciennete_result.get("anciennete_annees")
        
        # Vérifier QPV
        qpv_ok = entreprise.qpv if entreprise else None
        
        # Déterminer le verdict global
        verdict = "ok"
        if ca_seuil_ok is False or anciennete_ok is False:
            verdict = "ko"
        elif ca_seuil_ok is None or anciennete_ok is None:
            verdict = "attention"
        
        # Créer ou mettre à jour l'éligibilité
        eligibilite = session.exec(
            select(Eligibilite).where(Eligibilite.preinscription_id == preinscription_id)
        ).first()
        
        if not eligibilite:
            eligibilite = Eligibilite(preinscription_id=preinscription_id)
        
        eligibilite.ca_seuil_ok = ca_seuil_ok
        eligibilite.ca_score = ca_score
        eligibilite.qpv_ok = qpv_ok
        eligibilite.anciennete_ok = anciennete_ok
        eligibilite.anciennete_annees = anciennete_annees
        eligibilite.verdict = verdict
        eligibilite.calcule_le = datetime.now(timezone.utc)
        
        session.add(eligibilite)
        session.commit()
        session.refresh(eligibilite)
        
        return eligibilite
