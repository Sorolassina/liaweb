# app/routers/ACD/jury_decisions.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app_lia_web.core.database import get_session
from app_lia_web.core.config import settings
from app_lia_web.core.security import get_current_user
from app_lia_web.app.templates import templates

from app_lia_web.app.models.base import (
    Candidat, Jury, DecisionJuryCandidat, Partenaire, User, Promotion,
    ReorientationCandidat
)
from app_lia_web.app.models.enums import DecisionJury, UserRole

router = APIRouter()


# --------- GESTION DES DÉCISIONS DU JURY ---------
@router.get("/jury-decisions", name="jury_decisions_list", response_class=HTMLResponse)
def jury_decisions_list(
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
    jury_id: Optional[int] = Query(None),
    decision: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """Liste des décisions du jury"""
    
    # Récupérer les jurys actifs
    jurys = session.exec(select(Jury).where(Jury.actif == True)).all()
    
    # Construire la requête
    stmt = (
        select(DecisionJuryCandidat, Candidat, Jury, User, Promotion, Partenaire)
        .join(Candidat, Candidat.id == DecisionJuryCandidat.candidat_id)
        .join(Jury, Jury.id == DecisionJuryCandidat.jury_id)
        .outerjoin(User, User.id == DecisionJuryCandidat.conseiller_id)
        .outerjoin(Promotion, Promotion.id == DecisionJuryCandidat.promotion_id)
        .outerjoin(Partenaire, Partenaire.id == DecisionJuryCandidat.partenaire_id)
    )
    
    # Filtres
    if jury_id:
        stmt = stmt.where(DecisionJuryCandidat.jury_id == jury_id)
    if decision:
        stmt = stmt.where(DecisionJuryCandidat.decision == decision)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Candidat.nom.ilike(like)) |
            (Candidat.prenom.ilike(like)) |
            (Candidat.email.ilike(like))
        )
    
    decisions = session.exec(stmt.order_by(DecisionJuryCandidat.date_decision.desc())).all()
    
    # Récupérer les partenaires actifs
    partenaires = session.exec(select(Partenaire).where(Partenaire.actif == True)).all()
    
    # Récupérer les conseillers
    conseillers = session.exec(select(User).where(User.role == UserRole.CONSEILLER.value)).all()
    
    # Récupérer les promotions
    promotions = session.exec(select(Promotion)).all()
    
    return templates.TemplateResponse(
        "ACD/admin/jury_decisions.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "decisions": decisions,
            "jurys": jurys,
            "partenaires": partenaires,
            "conseillers": conseillers,
            "promotions": promotions,
            "current_jury_id": jury_id,
            "current_decision": decision,
            "q": q or "",
            "decision_enum": DecisionJury,
        },
    )


@router.post("/jury-decisions/create")
def create_jury_decision(
    candidat_id: int = Form(...),
    jury_id: int = Form(...),
    decision: str = Form(...),
    commentaires: Optional[str] = Form(None),
    conseiller_id: Optional[int] = Form(None),
    groupe_codev: Optional[str] = Form(None),
    promotion_id: Optional[int] = Form(None),
    partenaire_id: Optional[int] = Form(None),
    envoyer_mail_candidat: bool = Form(False),
    envoyer_mail_conseiller: bool = Form(False),
    envoyer_mail_partenaire: bool = Form(False),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Créer une décision du jury"""
    
    # Vérifier que le candidat existe
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Vérifier que le jury existe
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(status_code=404, detail="Jury introuvable")
    
    # Vérifier qu'il n'y a pas déjà une décision pour ce candidat et ce jury
    existing = session.exec(
        select(DecisionJuryCandidat).where(
            (DecisionJuryCandidat.candidat_id == candidat_id) &
            (DecisionJuryCandidat.jury_id == jury_id)
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Une décision existe déjà pour ce candidat et ce jury")
    
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
    candidat.statut = decision
    
    # Si réorienté, créer l'enregistrement de réorientation
    if decision == DecisionJury.REORIENTE.value and partenaire_id:
        reorientation = ReorientationCandidat(
            candidat_id=candidat_id,
            partenaire_id=partenaire_id,
            decision_jury_id=decision_obj.id,
            mail_envoye=envoyer_mail_partenaire,
        )
        session.add(reorientation)
    
    session.commit()
    
    # TODO: Envoyer les emails selon les cases cochées
    if envoyer_mail_candidat or envoyer_mail_conseiller or envoyer_mail_partenaire:
        # Logique d'envoi d'emails à implémenter
        pass
    
    # Log de l'activité
    from app_lia_web.app.services.ACD.audit import log_activity
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
    
    return RedirectResponse(url=request.url_for("jury_decisions_list", jury_id=jury_id, success="decision_created"), status_code=303)


@router.post("/jury-decisions/{decision_id}/update")
def update_jury_decision(
    decision_id: int,
    decision: str = Form(...),
    commentaires: Optional[str] = Form(None),
    conseiller_id: Optional[int] = Form(None),
    groupe_codev: Optional[str] = Form(None),
    promotion_id: Optional[int] = Form(None),
    partenaire_id: Optional[int] = Form(None),
    envoyer_mail_candidat: bool = Form(False),
    envoyer_mail_conseiller: bool = Form(False),
    envoyer_mail_partenaire: bool = Form(False),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Mettre à jour une décision du jury"""
    
    decision_obj = session.get(DecisionJuryCandidat, decision_id)
    if not decision_obj:
        raise HTTPException(status_code=404, detail="Décision introuvable")
    
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
        candidat.statut = decision
    
    session.commit()
    
    # Log de l'activité
    from app_lia_web.app.services.ACD.audit import log_activity
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
    
    return RedirectResponse(url=request.url_for("jury_decisions_list", jury_id=decision_obj.jury_id, success="decision_updated"), status_code=303)


@router.post("/jury-decisions/{decision_id}/delete")
def delete_jury_decision(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Supprimer une décision du jury"""
    
    decision_obj = session.get(DecisionJuryCandidat, decision_id)
    if not decision_obj:
        raise HTTPException(status_code=404, detail="Décision introuvable")
    
    jury_id = decision_obj.jury_id
    
    # Remettre le candidat en attente
    candidat = session.get(Candidat, decision_obj.candidat_id)
    if candidat:
        candidat.statut = DecisionJury.EN_ATTENTE.value
    
    # Supprimer les réorientations associées
    session.exec(
        select(ReorientationCandidat).where(
            ReorientationCandidat.decision_jury_id == decision_id
        )
    )
    
    session.delete(decision_obj)
    session.commit()
    
    # Log de l'activité
    from app_lia_web.app.services.ACD.audit import log_activity
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
    
    return RedirectResponse(url=request.url_for("jury_decisions_list", jury_id=jury_id, success="decision_deleted"), status_code=303)
