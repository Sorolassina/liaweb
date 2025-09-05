"""
Service de calcul des statistiques
"""
from sqlmodel import Session, select
import logging
from ..models.base import Preinscription, Inscription, Programme, Jury
from ..models.enums import StatutDossier
from ..schemas import StatistiquesResponse

logger = logging.getLogger(__name__)


class StatistiquesService:
    """Service de calcul des statistiques"""
    
    @staticmethod
    def get_dashboard_stats(session: Session) -> StatistiquesResponse:
        """Récupère les statistiques du tableau de bord"""
        candidats_preinscrits = session.exec(select(Preinscription)).count()
        candidats_inscrits = session.exec(select(Inscription)).count()
        programmes_actifs = session.exec(select(Programme).where(Programme.actif == True)).count()
        jurys_planifies = session.exec(select(Jury).where(Jury.statut == "planifie")).count()
        decisions_en_attente = session.exec(select(Inscription).where(Inscription.statut == StatutDossier.EN_EXAMEN)).count()
        
        return StatistiquesResponse(
            candidats_preinscrits=candidats_preinscrits,
            candidats_inscrits=candidats_inscrits,
            programmes_actifs=programmes_actifs,
            jurys_planifies=jurys_planifies,
            decisions_en_attente=decisions_en_attente
        )
