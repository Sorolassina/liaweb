"""
Service de gestion des inscriptions
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from datetime import datetime, timezone
import logging

from app_lia_web.app.models.inscription import Inscription
from app_lia_web.app.models.preinscription import Preinscription
from app_lia_web.app.models.base import Programme, EtapePipeline, AvancementEtape
from app_lia_web.app.models.enums import StatutDossier, StatutEtape
from app_lia_web.app.schemas import InscriptionCreate
from app_lia_web.core.program_schema_integration import table_exists_anywhere

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
        """Récupère les inscriptions d'un programme - Version sécurisée"""
        if not table_exists_anywhere("inscription", session):
            return []
        try:
            return session.exec(
                select(Inscription)
                .where(Inscription.programme_id == programme_id)
                .order_by(Inscription.cree_le.desc())
            ).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des inscriptions: {e}")
            return []
    
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
    
    @staticmethod
    def create_from_preinscription(session: Session, pre_id: int) -> Inscription:
        """
        Crée une inscription depuis une préinscription avec initialisation du pipeline
        """
        # Récupérer la préinscription
        pre = session.get(Preinscription, pre_id)
        if not pre:
            raise ValueError("Préinscription introuvable")
        
        # Récupérer le programme
        prog = session.get(Programme, pre.programme_id)
        if not prog:
            raise ValueError("Programme introuvable")
        
        # Vérifier qu'il n'y a pas déjà une inscription
        existing = session.exec(
            select(Inscription).where(
                (Inscription.programme_id == pre.programme_id) & 
                (Inscription.candidat_id == pre.candidat_id)
            )
        ).first()
        
        if existing:
            raise ValueError("Une inscription existe déjà pour ce candidat et ce programme")
        
        # Créer l'inscription
        inscription = Inscription(
            programme_id=pre.programme_id,
            candidat_id=pre.candidat_id,
            statut=pre.statut
        )
        session.add(inscription)
        session.flush()
        
        # Initialiser le pipeline d'étapes
        InscriptionService._initialize_pipeline(session, inscription.id, prog.id)
        
        session.commit()
        session.refresh(inscription)
        
        logger.info(f"✅ Inscription créée depuis préinscription {pre_id} -> {inscription.id}")
        
        return inscription
    
    @staticmethod
    def update_candidate_info(
        session: Session,
        inscription_id: int,
        candidate_data: Dict[str, Any],
        enterprise_data: Optional[Dict[str, Any]] = None
    ) -> Inscription:
        """
        Met à jour les informations candidat/entreprise d'une inscription
        """
        inscription = session.get(Inscription, inscription_id)
        if not inscription:
            raise ValueError("Inscription introuvable")
        
        # Récupérer le candidat
        from app_lia_web.app.models.base import Candidat
        candidat = session.get(Candidat, inscription.candidat_id)
        if not candidat:
            raise ValueError("Candidat introuvable")
        
        # Mettre à jour les données candidat
        for field, value in candidate_data.items():
            if hasattr(candidat, field) and value is not None:
                setattr(candidat, field, value)
        
        session.add(candidat)
        
        # Mettre à jour les données entreprise si fournies
        if enterprise_data:
            from app_lia_web.app.models.base import Entreprise
            entreprise = session.get(Entreprise, candidat.entreprise_id) if candidat.entreprise_id else None
            
            if entreprise:
                for field, value in enterprise_data.items():
                    if hasattr(entreprise, field) and value is not None:
                        setattr(entreprise, field, value)
                session.add(entreprise)
        
        session.commit()
        session.refresh(inscription)
        
        logger.info(f"✅ Informations candidat/entreprise mises à jour pour inscription {inscription_id}")
        
        return inscription
    
    @staticmethod
    def get_inscription_context_data(session: Session, programme_code: str) -> Dict[str, Any]:
        """
        Récupère les données de contexte pour les inscriptions
        """
        from app_lia_web.app.models.base import User, Promotion, Partenaire, Groupe
        from app_lia_web.app.models.enums import UserRole
        
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
    
    @staticmethod
    def _initialize_pipeline(session: Session, inscription_id: int, programme_id: int) -> None:
        """
        Initialise le pipeline d'étapes pour une inscription
        """
        # Récupérer les étapes actives du programme - Version sécurisée
        steps = []
        if table_exists_anywhere("etape_pipeline", session):
            try:
                steps = session.exec(
                    select(EtapePipeline).where(
                        (EtapePipeline.programme_id == programme_id) & 
                        (EtapePipeline.active.is_(True))
                    ).order_by(EtapePipeline.ordre)
                ).all()
            except Exception as e:
                logging.warning(f"Erreur lors de la récupération des étapes du pipeline: {e}")
                steps = []
        
        # Créer les avancements d'étapes
        for step in steps:
            avancement = AvancementEtape(
                inscription_id=inscription_id,
                etape_id=step.id,
                statut=StatutEtape.A_FAIRE
            )
            session.add(avancement)
        
        logger.info(f"✅ Pipeline initialisé pour inscription {inscription_id} avec {len(steps)} étapes")
