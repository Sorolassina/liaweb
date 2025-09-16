"""
Service de gestion du Codéveloppement
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, func, and_, or_
from datetime import datetime, timezone, date, timedelta
import logging

from app_lia_web.app.models.codev import (
    SeanceCodev, PresentationCodev, ContributionCodev, ParticipationSeance,
    CycleCodev, GroupeCodev, MembreGroupeCodev
)
from app_lia_web.app.models.base import Inscription, User, Programme, Promotion, Groupe
from app_lia_web.app.models.enums import (
    StatutSeanceCodev, StatutPresentation, TypeContribution,
    StatutCycleCodev, StatutGroupeCodev, StatutMembreGroupe, StatutPresence
)
from app_lia_web.app.schemas import (
    CycleCodevCreate, CycleCodevUpdate,
    GroupeCodevCreate, SeanceCodevCreate, 
    PresentationCodevCreate, ContributionCodevCreate,
    MembreGroupeCodevCreate
)

logger = logging.getLogger(__name__)

class CodevService:
    """Service de gestion du codéveloppement"""
    
    @staticmethod
    def create_cycle_codev(
        session: Session, 
        nom: str,
        programme_id: int,
        promotion_id: Optional[int] = None,
        date_debut: date = None,
        date_fin: date = None,
        nombre_seances: int = 6,
        animateur_principal_id: Optional[int] = None
    ) -> CycleCodev:
        """Crée un nouveau cycle de codéveloppement"""
        
        if not date_debut:
            date_debut = date.today()
        if not date_fin:
            date_fin = date_debut + timedelta(weeks=nombre_seances * 2)  # 1 séance toutes les 2 semaines
        
        cycle = CycleCodev(
            nom=nom,
            programme_id=programme_id,
            promotion_id=promotion_id,
            date_debut=date_debut,
            date_fin=date_fin,
            nombre_seances_prevues=nombre_seances,
            animateur_principal_id=animateur_principal_id,
            statut=StatutCycleCodev.PLANIFIE.value
        )
        
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        
        logger.info(f"Cycle de codéveloppement créé: {cycle.nom} (ID: {cycle.id})")
        return cycle
    
    @staticmethod
    def create_groupe_codev(
        session: Session,
        cycle_id: int,
        groupe_id: int,
        nom_groupe: str,
        animateur_id: Optional[int] = None,
        capacite_max: int = 12
    ) -> GroupeCodev:
        """Crée un groupe de codéveloppement dans un cycle"""
        
        groupe_codev = GroupeCodev(
            cycle_id=cycle_id,
            groupe_id=groupe_id,
            nom_groupe=nom_groupe,
            animateur_id=animateur_id,
            capacite_max=capacite_max,
            statut=StatutGroupeCodev.EN_CONSTITUTION.value
        )
        
        session.add(groupe_codev)
        session.commit()
        session.refresh(groupe_codev)
        
        logger.info(f"Groupe de codéveloppement créé: {nom_groupe} (ID: {groupe_codev.id})")
        return groupe_codev
    
    @staticmethod
    def add_membre_groupe(
        session: Session,
        groupe_codev_id: int,
        candidat_id: int,
        role_special: Optional[str] = None
    ) -> MembreGroupeCodev:
        """Ajoute un candidat à un groupe de codéveloppement"""
        
        # Vérifier que le groupe n'est pas complet
        groupe_codev = session.get(GroupeCodev, groupe_codev_id)
        if not groupe_codev:
            raise ValueError("Groupe de codéveloppement introuvable")
        
        membres_actifs = session.exec(
            select(func.count()).select_from(MembreGroupeCodev)
            .where(and_(
                MembreGroupeCodev.groupe_codev_id == groupe_codev_id,
                MembreGroupeCodev.statut == StatutMembreGroupe.ACTIF.value
            ))
        ).one()
        
        if membres_actifs >= groupe_codev.capacite_max:
            raise ValueError("Le groupe est complet")
        
        # Vérifier que le candidat n'est pas déjà dans le groupe
        existing = session.exec(
            select(MembreGroupeCodev).where(and_(
                MembreGroupeCodev.groupe_codev_id == groupe_codev_id,
                MembreGroupeCodev.candidat_id == candidat_id
            ))
        ).first()
        
        if existing:
            raise ValueError("Le candidat est déjà dans ce groupe")
        
        membre = MembreGroupeCodev(
            groupe_codev_id=groupe_codev_id,
            candidat_id=candidat_id,
            role_special=role_special,
            statut=StatutMembreGroupe.ACTIF.value
        )
        
        session.add(membre)
        session.commit()
        session.refresh(membre)
        
        logger.info(f"Candidat {candidat_id} ajouté au groupe {groupe_codev_id}")
        return membre
    
    @staticmethod
    def create_seance_codev(
        session: Session,
        groupe_id: int,
        numero_seance: int,
        date_seance: datetime,
        lieu: Optional[str] = None,
        animateur_id: Optional[int] = None,
        duree_minutes: int = 180
    ) -> SeanceCodev:
        """Crée une séance de codéveloppement"""
        
        seance = SeanceCodev(
            groupe_id=groupe_id,
            numero_seance=numero_seance,
            date_seance=date_seance,
            lieu=lieu,
            animateur_id=animateur_id,
            duree_minutes=duree_minutes,
            statut=StatutSeanceCodev.PLANIFIEE.value
        )
        
        session.add(seance)
        session.commit()
        session.refresh(seance)
        
        logger.info(f"Séance {numero_seance} créée pour le groupe {groupe_id}")
        return seance
    
    @staticmethod
    def planifier_presentations_seance(
        session: Session,
        seance_id: int,
        candidats_ids: List[int],
        ordre_presentations: Optional[List[int]] = None
    ) -> List[PresentationCodev]:
        """Planifie les présentations pour une séance"""
        
        seance = session.get(SeanceCodev, seance_id)
        if not seance:
            raise ValueError("Séance introuvable")
        
        presentations = []
        
        # Si pas d'ordre spécifié, utiliser l'ordre de la liste
        if not ordre_presentations:
            ordre_presentations = list(range(1, len(candidats_ids) + 1))
        
        for i, candidat_id in enumerate(candidats_ids):
            presentation = PresentationCodev(
                seance_id=seance_id,
                candidat_id=candidat_id,
                ordre_presentation=ordre_presentations[i],
                probleme_expose="",  # À remplir par le candidat
                statut=StatutPresentation.EN_ATTENTE.value
            )
            session.add(presentation)
            presentations.append(presentation)
        
        session.commit()
        
        for presentation in presentations:
            session.refresh(presentation)
        
        logger.info(f"{len(presentations)} présentations planifiées pour la séance {seance_id}")
        return presentations
    
    @staticmethod
    def add_contribution(
        session: Session,
        presentation_id: int,
        contributeur_id: int,
        type_contribution: TypeContribution,
        contenu: str,
        ordre_contribution: Optional[int] = None
    ) -> ContributionCodev:
        """Ajoute une contribution à une présentation"""
        
        # Déterminer l'ordre automatiquement si non spécifié
        if not ordre_contribution:
            max_ordre = session.exec(
                select(func.max(ContributionCodev.ordre_contribution))
                .where(ContributionCodev.presentation_id == presentation_id)
            ).one() or 0
            ordre_contribution = max_ordre + 1
        
        contribution = ContributionCodev(
            presentation_id=presentation_id,
            contributeur_id=contributeur_id,
            type_contribution=type_contribution,
            contenu=contenu,
            ordre_contribution=ordre_contribution
        )
        
        session.add(contribution)
        session.commit()
        session.refresh(contribution)
        
        logger.info(f"Contribution ajoutée à la présentation {presentation_id}")
        return contribution
    
    @staticmethod
    def get_statistiques_cycle(session: Session, cycle_id: int) -> Dict[str, Any]:
        """Récupère les statistiques d'un cycle de codéveloppement"""
        
        cycle = session.get(CycleCodev, cycle_id)
        if not cycle:
            return {}
        
        # Nombre de groupes
        nb_groupes = session.exec(
            select(func.count()).select_from(GroupeCodev)
            .where(GroupeCodev.cycle_id == cycle_id)
        ).one()
        
        # Nombre total de membres
        nb_membres = session.exec(
            select(func.count()).select_from(MembreGroupeCodev)
            .join(GroupeCodev, MembreGroupeCodev.groupe_codev_id == GroupeCodev.id)
            .where(GroupeCodev.cycle_id == cycle_id)
        ).one()
        
        # Nombre de séances réalisées
        nb_seances = session.exec(
            select(func.count()).select_from(SeanceCodev)
            .join(Groupe, SeanceCodev.groupe_id == Groupe.id)
            .join(GroupeCodev, Groupe.id == GroupeCodev.groupe_id)
            .where(GroupeCodev.cycle_id == cycle_id)
            .where(SeanceCodev.statut == StatutSeanceCodev.TERMINEE.value)
        ).one()
        
        # Nombre de présentations terminées
        nb_presentations = session.exec(
            select(func.count()).select_from(PresentationCodev)
            .join(SeanceCodev, PresentationCodev.seance_id == SeanceCodev.id)
            .join(Groupe, SeanceCodev.groupe_id == Groupe.id)
            .join(GroupeCodev, Groupe.id == GroupeCodev.groupe_id)
            .where(GroupeCodev.cycle_id == cycle_id)
            .where(PresentationCodev.statut == StatutPresentation.RETOUR_FAIT.value)
        ).one()
        
        return {
            "cycle": cycle,
            "nb_groupes": nb_groupes,
            "nb_membres": nb_membres,
            "nb_seances": nb_seances,
            "nb_presentations": nb_presentations,
            "taux_realisation": (nb_seances / cycle.nombre_seances_prevues * 100) if cycle.nombre_seances_prevues > 0 else 0
        }
    
    @staticmethod
    def get_prochaines_seances(session: Session, limit: int = 10) -> List[SeanceCodev]:
        """Récupère les prochaines séances de codéveloppement"""
        
        maintenant = datetime.now(timezone.utc)
        
        seances = session.exec(
            select(SeanceCodev)
            .where(and_(
                SeanceCodev.date_seance >= maintenant,
                SeanceCodev.statut == StatutSeanceCodev.PLANIFIEE.value
            ))
            .order_by(SeanceCodev.date_seance)
            .limit(limit)
        ).all()
        
        return seances
    
    @staticmethod
    def get_engagements_en_cours(session: Session) -> List[PresentationCodev]:
        """Récupère les engagements en cours de test"""
        
        maintenant = datetime.now(timezone.utc)
        
        presentations = session.exec(
            select(PresentationCodev)
            .where(and_(
                PresentationCodev.statut == StatutPresentation.TEST_EN_COURS.value,
                PresentationCodev.delai_engagement >= maintenant.date()
            ))
            .order_by(PresentationCodev.delai_engagement)
        ).all()
        
        return presentations
    
    @staticmethod
    def marquer_engagement_pris(
        session: Session,
        presentation_id: int,
        engagement: str,
        delai_engagement: date
    ) -> PresentationCodev:
        """Marque qu'un engagement a été pris par le candidat"""
        
        presentation = session.get(PresentationCodev, presentation_id)
        if not presentation:
            raise ValueError("Présentation introuvable")
        
        presentation.engagement_candidat = engagement
        presentation.delai_engagement = delai_engagement
        presentation.statut = StatutPresentation.ENGAGEMENT_PRIS.value
        
        session.commit()
        session.refresh(presentation)
        
        logger.info(f"Engagement pris pour la présentation {presentation_id}")
        return presentation
    
    @staticmethod
    def marquer_test_en_cours(session: Session, presentation_id: int) -> PresentationCodev:
        """Marque qu'un test est en cours"""
        
        presentation = session.get(PresentationCodev, presentation_id)
        if not presentation:
            raise ValueError("Présentation introuvable")
        
        presentation.statut = StatutPresentation.TEST_EN_COURS.value
        
        session.commit()
        session.refresh(presentation)
        
        logger.info(f"Test marqué en cours pour la présentation {presentation_id}")
        return presentation
    
    @staticmethod
    def ajouter_retour_experience(
        session: Session,
        presentation_id: int,
        notes_candidat: str
    ) -> PresentationCodev:
        """Ajoute le retour d'expérience du candidat"""
        
        presentation = session.get(PresentationCodev, presentation_id)
        if not presentation:
            raise ValueError("Présentation introuvable")
        
        presentation.notes_candidat = notes_candidat
        presentation.statut = StatutPresentation.RETOUR_FAIT.value
        
        session.commit()
        session.refresh(presentation)
        
        logger.info(f"Retour d'expérience ajouté pour la présentation {presentation_id}")
        return presentation
