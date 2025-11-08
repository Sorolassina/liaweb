"""
Service de calcul des statistiques
"""
from sqlmodel import Session, select
import logging
from ..models.base import Programme
from ..models.preinscription import Preinscription
from ..models.inscription import Inscription
from ..models.jury import Jury
from ..models.enums import StatutDossier
from ..schemas import StatistiquesResponse
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere

logger = logging.getLogger(__name__)


class StatistiquesService:
    """Service de calcul des statistiques"""
    
    @staticmethod
    def get_dashboard_stats(session: Session) -> StatistiquesResponse:
        """Récupère les statistiques du tableau de bord - Version sécurisée"""
        candidats_preinscrits = 0
        if table_exists_anywhere("preinscription", session):
            candidats_preinscrits = safe_count_query(session, Preinscription)
        
        candidats_inscrits = 0
        if table_exists_anywhere("inscription", session):
            candidats_inscrits = safe_count_query(session, Inscription)
        
        programmes_actifs = 0
        if table_exists_anywhere("programme", session):
            programmes_actifs = safe_count_query(session, Programme, actif=True)
        
        # Jurys planifiés - Version sécurisée
        jurys_planifies = 0
        if table_exists_anywhere("jury", session):
            try:
                jurys_planifies = session.exec(select(Jury).where(Jury.statut == "planifie")).count()
            except Exception as e:
                logging.warning(f"Erreur lors du comptage des jurys planifiés: {e}")
                jurys_planifies = 0
        
        # Décisions en attente - Version sécurisée
        decisions_en_attente = 0
        if table_exists_anywhere("inscription", session):
            try:
                decisions_en_attente = session.exec(select(Inscription).where(Inscription.statut == StatutDossier.EN_EXAMEN)).count()
            except Exception as e:
                logging.warning(f"Erreur lors du comptage des décisions en attente: {e}")
                decisions_en_attente = 0
        
        return StatistiquesResponse(
            candidats_preinscrits=candidats_preinscrits,
            candidats_inscrits=candidats_inscrits,
            programmes_actifs=programmes_actifs,
            jurys_planifies=jurys_planifies,
            decisions_en_attente=decisions_en_attente
        )
