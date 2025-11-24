"""
Service de gestion des décisions de jury
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from datetime import datetime, timezone
import logging

from ..models.base import Candidat, Partenaire, ReorientationCandidat, User
from ..models.jury import Jury, DecisionJuryCandidat
from ..models.enums import DecisionJury, UserRole
from .audit import log_activity

logger = logging.getLogger(__name__)


class JuryDecisionService:
    """Service de gestion des décisions de jury"""
    
    @staticmethod
    def create_decision(
        session: Session,
        candidat_id: int,
        jury_id: int,
        decision: str,
        commentaires: Optional[str] = None,
        conseiller_id: Optional[int] = None,
        groupe_codev: Optional[str] = None,
        promotion_id: Optional[int] = None,
        partenaire_id: Optional[int] = None,
        envoyer_mail_candidat: bool = False,
        envoyer_mail_conseiller: bool = False,
        envoyer_mail_partenaire: bool = False,
        current_user: User = None
    ) -> DecisionJuryCandidat:
        """Crée une décision du jury avec toute la logique métier"""
        
        # Validation des entités
        candidat = session.get(Candidat, candidat_id)
        if not candidat:
            raise ValueError("Candidat introuvable")
        
        jury = session.get(Jury, jury_id)
        if not jury:
            raise ValueError("Jury introuvable")
        
        # Vérifier s'il existe déjà une décision pour ce candidat et ce jury
        existing = session.exec(
            select(DecisionJuryCandidat).where(
                (DecisionJuryCandidat.candidat_id == candidat_id) &
                (DecisionJuryCandidat.jury_id == jury_id)
            )
        ).first()
        
        if existing:
            logger.info(f"Une décision existe déjà pour ce candidat et ce jury (ID: {existing.id}), suppression de l'ancienne décision")
            # Supprimer les réorientations associées à l'ancienne décision
            reorientations = session.exec(
                select(ReorientationCandidat).where(
                    ReorientationCandidat.decision_jury_id == existing.id
                )
            ).all()
            for reo in reorientations:
                logger.info(f"Suppression de la réorientation ID: {reo.id}")
                session.delete(reo)
            # Supprimer l'ancienne décision
            session.delete(existing)
            logger.info("Ancienne décision supprimée, création de la nouvelle")
        
        # Créer la décision
        decision_obj = DecisionJuryCandidat(
            candidat_id=candidat_id,
            jury_id=jury_id,
            decision=DecisionJury(decision),
            commentaires=commentaires,
            conseiller_id=conseiller_id if decision == DecisionJury.VALIDE.value else None,
            groupe_codev=groupe_codev if decision == DecisionJury.VALIDE.value else None,
            promotion_id=promotion_id if decision == DecisionJury.VALIDE.value else None,
            partenaire_id=partenaire_id if decision == DecisionJury.REORIENTE.value else None,
            envoyer_mail_candidat=envoyer_mail_candidat,
            envoyer_mail_conseiller=envoyer_mail_conseiller,
            envoyer_mail_partenaire=envoyer_mail_partenaire,
        )
        
        session.add(decision_obj)
        session.flush()
        
        # Mettre à jour le statut du candidat
        candidat.statut = DecisionJury(decision)
        # S'assurer que le candidat est dans la session pour que les modifications soient trackées
        session.add(candidat)
        
        # Gérer la réorientation si nécessaire
        if decision == DecisionJury.REORIENTE.value and partenaire_id:
            JuryDecisionService._handle_reorientation(
                session, decision_obj.id, candidat_id, partenaire_id, envoyer_mail_partenaire
            )
        
        session.commit()
        
        # Log d'audit
        if current_user:
            log_activity(
                session=session,
                user=current_user,
                action="Décision jury créée",
                entity="DecisionJuryCandidat",
                entity_id=decision_obj.id,
                activity_data={
                    "candidat_id": candidat_id,
                    "jury_id": jury_id,
                    "decision": decision,
                    "emails_envoyes": {
                        "candidat": envoyer_mail_candidat,
                        "conseiller": envoyer_mail_conseiller,
                        "partenaire": envoyer_mail_partenaire,
                    }
                }
            )
        
        return decision_obj
    
    @staticmethod
    def update_decision(
        session: Session,
        decision_id: int,
        decision: str,
        commentaires: Optional[str] = None,
        conseiller_id: Optional[int] = None,
        groupe_codev: Optional[str] = None,
        promotion_id: Optional[int] = None,
        partenaire_id: Optional[int] = None,
        envoyer_mail_candidat: bool = False,
        envoyer_mail_conseiller: bool = False,
        envoyer_mail_partenaire: bool = False,
        current_user: User = None
    ) -> DecisionJuryCandidat:
        """Met à jour une décision du jury"""
        
        decision_obj = session.get(DecisionJuryCandidat, decision_id)
        if not decision_obj:
            raise ValueError("Décision introuvable")
        
        # Mettre à jour les champs
        decision_obj.decision = DecisionJury(decision)
        decision_obj.commentaires = commentaires
        decision_obj.conseiller_id = conseiller_id if decision == DecisionJury.VALIDE.value else None
        decision_obj.groupe_codev = groupe_codev if decision == DecisionJury.VALIDE.value else None
        decision_obj.promotion_id = promotion_id if decision == DecisionJury.VALIDE.value else None
        decision_obj.partenaire_id = partenaire_id if decision == DecisionJury.REORIENTE.value else None
        decision_obj.envoyer_mail_candidat = envoyer_mail_candidat
        decision_obj.envoyer_mail_conseiller = envoyer_mail_conseiller
        decision_obj.envoyer_mail_partenaire = envoyer_mail_partenaire
        decision_obj.date_decision = datetime.now(timezone.utc)
        
        # Mettre à jour le statut du candidat
        candidat = session.get(Candidat, decision_obj.candidat_id)
        if candidat:
            candidat.statut = DecisionJury(decision)
            # S'assurer que le candidat est dans la session pour que les modifications soient trackées
            session.add(candidat)
        
        session.commit()
        
        # Log d'audit
        if current_user:
            log_activity(
                session=session,
                user=current_user,
                action="Décision jury mise à jour",
                entity="DecisionJuryCandidat",
                entity_id=decision_id,
                activity_data={
                    "nouvelle_decision": decision,
                    "emails_envoyes": {
                        "candidat": envoyer_mail_candidat,
                        "conseiller": envoyer_mail_conseiller,
                        "partenaire": envoyer_mail_partenaire,
                    }
                }
            )
        
        return decision_obj
    
    @staticmethod
    def delete_decision(
        session: Session,
        decision_id: int,
        current_user: User = None
    ) -> int:
        """Supprime une décision du jury"""
        
        decision_obj = session.get(DecisionJuryCandidat, decision_id)
        if not decision_obj:
            raise ValueError("Décision introuvable")
        
        jury_id = decision_obj.jury_id
        
        # Remettre le candidat en attente
        candidat = session.get(Candidat, decision_obj.candidat_id)
        if candidat:
            candidat.statut = DecisionJury.EN_ATTENTE
            # S'assurer que le candidat est dans la session pour que les modifications soient trackées
            session.add(candidat)
        
        # Supprimer les réorientations associées
        session.exec(
            select(ReorientationCandidat).where(
                ReorientationCandidat.decision_jury_id == decision_id
            )
        )
        
        session.delete(decision_obj)
        session.commit()
        
        # Log d'audit
        if current_user:
            log_activity(
                session=session,
                user=current_user,
                action="Décision jury supprimée",
                entity="DecisionJuryCandidat",
                entity_id=decision_id,
                activity_data={
                    "candidat_id": decision_obj.candidat_id,
                    "jury_id": jury_id,
                }
            )
        
        return jury_id
    
    @staticmethod
    def get_decisions_list(
        session: Session,
        jury_id: Optional[int] = None,
        decision: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[tuple]:
        """Récupère la liste des décisions avec filtres"""
        
        # Construire la requête
        stmt = (
            select(DecisionJuryCandidat, Candidat, Jury, User, Partenaire)
            .join(Candidat, Candidat.id == DecisionJuryCandidat.candidat_id)
            .join(Jury, Jury.id == DecisionJuryCandidat.jury_id)
            .outerjoin(User, User.id == DecisionJuryCandidat.conseiller_id)
            .outerjoin(Partenaire, Partenaire.id == DecisionJuryCandidat.partenaire_id)
        )
        
        # Appliquer les filtres
        if jury_id:
            stmt = stmt.where(DecisionJuryCandidat.jury_id == jury_id)
        if decision:
            stmt = stmt.where(DecisionJuryCandidat.decision == decision)
        if search_query:
            like = f"%{search_query}%"
            stmt = stmt.where(
                (Candidat.nom.ilike(like)) |
                (Candidat.prenom.ilike(like)) |
                (Candidat.email.ilike(like))
            )
        
        return session.exec(stmt.order_by(DecisionJuryCandidat.date_decision.desc())).all()
    
    @staticmethod
    def get_decision_context_data(session: Session) -> Dict[str, Any]:
        """Récupère les données de contexte pour les décisions (jurys, partenaires, etc.)"""
        
        return {
            "jurys": session.exec(select(Jury).where(Jury.actif == True)).all(),
            "partenaires": session.exec(select(Partenaire).where(Partenaire.actif == True)).all(),
            "conseillers": session.exec(select(User).where(User.role == UserRole.CONSEILLER.value)).all(),
        }
    
    @staticmethod
    def _handle_reorientation(
        session: Session,
        decision_jury_id: int,
        candidat_id: int,
        partenaire_id: int,
        mail_envoye: bool
    ) -> None:
        """Gère la création d'une réorientation"""
        
        reorientation = ReorientationCandidat(
            candidat_id=candidat_id,
            partenaire_id=partenaire_id,
            decision_jury_id=decision_jury_id,
            mail_envoye=mail_envoye,
        )
        session.add(reorientation)
