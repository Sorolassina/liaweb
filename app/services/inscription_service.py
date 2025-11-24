"""
Service de gestion des inscriptions
NOTE: Ce service est obsolète car le modèle Inscription a été supprimé.
Les fonctionnalités d'inscription sont maintenant gérées directement via Candidat.
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from datetime import datetime, timezone
import logging

from ..models.preinscription import Preinscription
from ..models.base import Programme, EtapePipeline, AvancementEtape
from ..models.enums import StatutDossier, StatutEtape
from ..core.program_schema_integration import table_exists_anywhere

logger = logging.getLogger(__name__)


class InscriptionService:
    """Service de gestion des inscriptions - OBSOLÈTE"""
    
    @staticmethod
    def create_from_preinscription(session: Session, pre_id: int):
        """
        Crée une inscription depuis une préinscription avec initialisation du pipeline
        NOTE: Cette méthode est obsolète. Le modèle Inscription n'existe plus.
        """
        # Récupérer la préinscription
        pre = session.get(Preinscription, pre_id)
        if not pre:
            raise ValueError("Préinscription introuvable")
        
        # Récupérer le programme
        prog = session.get(Programme, pre.programme_id)
        if not prog:
            raise ValueError("Programme introuvable")
        
        # NOTE: Le modèle Inscription a été supprimé.
        # Les candidats validés sont maintenant identifiés par leur statut dans la table Candidat.
        logger.warning(f"⚠️ InscriptionService.create_from_preinscription appelé mais le modèle Inscription n'existe plus")
        raise NotImplementedError("Le modèle Inscription a été supprimé. Utilisez directement le modèle Candidat avec statut VALIDE.")
    
    @staticmethod
    def get_inscription_context_data(session: Session, programme_code: str) -> Dict[str, Any]:
        """
        Récupère les données de contexte pour les inscriptions
        """
        from ..models.base import User, Promotion, Partenaire, Groupe
        from ..models.enums import UserRole
        
        # Récupérer le programme
        programme = session.exec(select(Programme).where(Programme.code == programme_code)).first()
        if not programme:
            raise ValueError("Programme introuvable")
        
        # Version sécurisée des requêtes de contexte
        conseillers = []
        promotions = []
        partenaires = []
        groupes = []
        
        try:
            conseillers = session.exec(select(User).where(User.role == UserRole.CONSEILLER.value)).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des conseillers: {e}")
        
        try:
            promotions = session.exec(select(Promotion)).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des promotions: {e}")
        
        try:
            partenaires = session.exec(select(Partenaire).where(Partenaire.actif == True)).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des partenaires: {e}")
        
        try:
            groupes = session.exec(select(Groupe).where(Groupe.actif == True).order_by(Groupe.nom)).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des groupes: {e}")
        
        return {
            "programme": programme,
            "conseillers": conseillers,
            "promotions": promotions,
            "partenaires": partenaires,
            "groupes": groupes,
        }
