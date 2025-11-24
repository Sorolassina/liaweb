"""
Router pour la gestion des jurys
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timezone

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.program_schema_integration import table_exists_anywhere
import logging
from ..models.base import User, Programme, Candidat, Partenaire, ReorientationCandidat
from ..models.jury import DecisionJuryCandidat
from ..models.jury import Jury, MembreJury, DecisionJuryTable
from ..templates import templates
from ..core.config import settings
from ..models.enums import UserRole, DecisionJury
from ..schemas import (
    JuryCreate, JuryUpdate, JuryResponse,
    DecisionJuryCreate, DecisionJuryResponse
)
from ..services import JuryService

router = APIRouter()


@router.post("/jurys", response_model=JuryResponse, name="create_jury")
async def create_jury(
    jury_data: JuryCreate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Crée une nouvelle session de jury (responsable programme seulement)"""
    # Vérifier les permissions
    if current_user.role != UserRole.RESPONSABLE_PROGRAMME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le responsable de programme peut créer des jurys"
        )
    
    # Vérifier que le programme existe
    programme = session.get(Programme, jury_data.programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Programme non trouvé"
        )
    
    jury = JuryService.create_jury(session, jury_data)
    return JuryResponse.from_orm(jury)


@router.get("/jurys", response_model=List[JuryResponse], name="get_jurys")
async def get_jurys(
    programme_id: Optional[int] = Query(None, description="Filtrer par programme"),
    statut: Optional[str] = Query(None, description="Filtrer par statut"),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des jurys"""
    query = select(Jury)
    
    # Appliquer les filtres
    if programme_id:
        query = query.where(Jury.programme_id == programme_id)
    
    if statut:
        query = query.where(Jury.statut == statut)
    
    if not table_exists_anywhere("jury", session):
        return []
    
    try:
        jurys = session.exec(query.order_by(Jury.session_le.desc())).all()
        return [JuryResponse.from_orm(jury) for jury in jurys]
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des jurys: {e}")
        return []


# ============================================================================
# ROUTES DÉCISIONS JURY (fusionnées depuis jury_decisions.py)
# ============================================================================

@router.get("/jury-decisions", name="jury_decisions_list", response_class=HTMLResponse)
def jury_decisions_list(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    jury_id: Optional[int] = Query(None),
    decision: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """Liste des décisions du jury"""
    try:
        from ..services import JuryDecisionService
        
        # Utiliser le service pour récupérer les décisions
        decisions = JuryDecisionService.get_decisions_list(
            session=session,
            jury_id=jury_id,
            decision=decision,
            search_query=q
        )
        
        # Récupérer les données de contexte
        context_data = JuryDecisionService.get_decision_context_data(session)
        
        return templates.TemplateResponse(
            "admin/jury_decisions.html",
            {
                "request": request,
                "settings": settings,
                "utilisateur": current_user,
                "decisions": decisions,
                "jurys": context_data["jurys"],
                "partenaires": context_data["partenaires"],
                "conseillers": context_data["conseillers"],
                "current_jury_id": jury_id,
                "current_decision": decision,
                "q": q or "",
                "decision_enum": DecisionJury,
            },
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des décisions: {str(e)}")


@router.post("/jury-decisions/create", name="create_jury_decision_web")
def create_jury_decision_web(
    request: Request,
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
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
):
    """Créer une décision du jury"""
    try:
        from ..services import JuryDecisionService
        
        # Utiliser le service pour créer la décision
        decision_obj = JuryDecisionService.create_decision(
            session=session,
            candidat_id=candidat_id,
            jury_id=jury_id,
            decision=decision,
            commentaires=commentaires,
            conseiller_id=conseiller_id,
            groupe_codev=groupe_codev,
            promotion_id=promotion_id,
            partenaire_id=partenaire_id,
            envoyer_mail_candidat=envoyer_mail_candidat,
            envoyer_mail_conseiller=envoyer_mail_conseiller,
            envoyer_mail_partenaire=envoyer_mail_partenaire,
            current_user=current_user
        )
        
        return RedirectResponse(
            url=f"{request.url_for('jury_decisions_list')}?jury_id={jury_id}&success=decision_created", 
            status_code=303
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la décision: {str(e)}")


@router.post("/jury-decisions/{decision_id}/update", name="update_jury_decision_web")
def update_jury_decision_web(
    request: Request,
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
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
):
    """Mettre à jour une décision du jury"""
    try:
        from ..services import JuryDecisionService
        
        # Utiliser le service pour mettre à jour la décision
        decision_obj = JuryDecisionService.update_decision(
            session=session,
            decision_id=decision_id,
            decision=decision,
            commentaires=commentaires,
            conseiller_id=conseiller_id,
            groupe_codev=groupe_codev,
            promotion_id=promotion_id,
            partenaire_id=partenaire_id,
            envoyer_mail_candidat=envoyer_mail_candidat,
            envoyer_mail_conseiller=envoyer_mail_conseiller,
            envoyer_mail_partenaire=envoyer_mail_partenaire,
            current_user=current_user
        )
        
        return RedirectResponse(
            url=f"{request.url_for('jury_decisions_list')}?jury_id={decision_obj.jury_id}&success=decision_updated", 
            status_code=303
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour de la décision: {str(e)}")


@router.post("/jury-decisions/{decision_id}/delete", name="delete_jury_decision_web")
def delete_jury_decision_web(
    request: Request,
    decision_id: int,
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
):
    """Supprimer une décision du jury"""
    try:
        from ..services import JuryDecisionService
        
        # Utiliser le service pour supprimer la décision
        jury_id = JuryDecisionService.delete_decision(
            session=session,
            decision_id=decision_id,
            current_user=current_user
        )
        
        return RedirectResponse(
            url=f"{request.url_for('jury_decisions_list')}?jury_id={jury_id}&success=decision_deleted", 
            status_code=303
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression de la décision: {str(e)}")


@router.get("/jurys/{jury_id}", response_model=JuryResponse, name="get_jury")
async def get_jury(
    jury_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère un jury par ID"""
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jury non trouvé"
        )
    
    return JuryResponse.from_orm(jury)


@router.put("/jurys/{jury_id}", response_model=JuryResponse, name="update_jury")
async def update_jury(
    jury_id: int,
    jury_data: JuryUpdate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour un jury"""
    # Vérifier les permissions
    if current_user.role != UserRole.RESPONSABLE_PROGRAMME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le responsable de programme peut modifier les jurys"
        )
    
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jury non trouvé"
        )
    
    # Mettre à jour les champs
    update_data = jury_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(jury, field, value)
    
    session.add(jury)
    session.commit()
    session.refresh(jury)
    
    return JuryResponse.from_orm(jury)


@router.post("/jurys/{jury_id}/membres", name="add_jury_member")
async def add_jury_member(
    jury_id: int,
    utilisateur_id: int,
    role: str = "membre",
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Ajoute un membre au jury"""
    # Vérifier les permissions
    if current_user.role != UserRole.RESPONSABLE_PROGRAMME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le responsable de programme peut ajouter des membres"
        )
    
    # Vérifier que le jury existe
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jury non trouvé"
        )
    
    # Vérifier que l'utilisateur existe
    user = session.get(User, utilisateur_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur non trouvé"
        )
    
    # Vérifier qu'il n'est pas déjà membre
    existing_member = session.exec(
        select(MembreJury).where(
            MembreJury.jury_id == jury_id,
            MembreJury.utilisateur_id == utilisateur_id
        )
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet utilisateur est déjà membre du jury"
        )
    
    membre = JuryService.add_jury_member(session, jury_id, utilisateur_id, role)
    
    return {
        "message": "Membre ajouté au jury",
        "membre": {
            "id": membre.id,
            "jury_id": membre.jury_id,
            "utilisateur_id": membre.utilisateur_id,
            "role": membre.role
        }
    }


@router.get("/jurys/{jury_id}/membres", name="get_jury_members")
async def get_jury_members(
    jury_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les membres d'un jury"""
    # Vérifier que le jury existe
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jury non trouvé"
        )
    
    membres = session.exec(
        select(MembreJury).where(MembreJury.jury_id == jury_id)
    ).all()
    
    return [{"id": m.id, "utilisateur_id": m.utilisateur_id, "role": m.role} for m in membres]


@router.post("/jurys/{jury_id}/decisions", name="create_jury_decision")
async def create_jury_decision(
    jury_id: int,
    decision_data: DecisionJuryCreate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Crée une décision de jury"""
    # Vérifier que le jury existe
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jury non trouvé"
        )
    
    # Vérifier que l'inscription existe
    inscription = session.get(Inscription, decision_data.inscription_id)
    if not inscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inscription non trouvée"
        )
    
    # Vérifier qu'il n'y a pas déjà une décision pour cette inscription
    existing_decision = session.exec(
        select(DecisionJuryTable).where(
            DecisionJuryTable.inscription_id == decision_data.inscription_id,
            DecisionJuryTable.jury_id == jury_id
        )
    ).first()
    
    if existing_decision:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Une décision existe déjà pour cette inscription dans ce jury"
        )
    
    # Créer la décision
    decision = DecisionJuryTable(
        inscription_id=decision_data.inscription_id,
        jury_id=jury_id,
        decision=decision_data.decision,
        commentaires=decision_data.commentaires,
        prises_en_charge_json=decision_data.prises_en_charge_json,
                    decide_le=datetime.now(timezone.utc)
    )
    
    session.add(decision)
    session.commit()
    session.refresh(decision)
    
    # Mettre à jour le statut de l'inscription selon la décision
    if decision_data.decision == DecisionJury.VALIDE:
        inscription.statut = StatutDossier.VALIDE
    elif decision_data.decision == DecisionJury.REJETE:
        inscription.statut = StatutDossier.REJETE
    elif decision_data.decision == DecisionJury.EN_ATTENTE:
        inscription.statut = StatutDossier.EN_EXAMEN
    elif decision_data.decision == DecisionJury.REORIENTE:
        inscription.statut = StatutDossier.REORIENTE
    
    inscription.date_decision = datetime.now(timezone.utc)
    session.add(inscription)
    session.commit()
    
    return {
        "message": "Décision de jury enregistrée",
        "decision": DecisionJuryResponse.from_orm(decision)
    }


@router.get("/jurys/{jury_id}/decisions", name="get_jury_decisions")
async def get_jury_decisions(
    jury_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les décisions d'un jury"""
    # Vérifier que le jury existe
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jury non trouvé"
        )
    
    decisions = session.exec(
        select(DecisionJuryTable).where(DecisionJuryTable.jury_id == jury_id)
    ).all()
    
    return [DecisionJuryResponse.from_orm(d).dict() for d in decisions]


@router.get("/programmes/{programme_id}/jurys", name="get_programme_jurys")
async def get_programme_jurys(
    programme_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les jurys d'un programme"""
    # Vérifier que le programme existe
    programme = session.get(Programme, programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    jurys = session.exec(
        select(Jury)
        .where(Jury.programme_id == programme_id)
        .order_by(Jury.session_le.desc())
    ).all()
    
    return [JuryResponse.from_orm(jury).dict() for jury in jurys]
