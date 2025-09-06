"""
Router pour la gestion des jurys
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timezone

from ..core.database import get_session
from ..core.security import get_current_user
from ..models.base import User, Jury, MembreJury, DecisionJuryTable, Programme, Inscription
from ..models.enums import UserRole, DecisionJury
from ..schemas import (
    JuryCreate, JuryUpdate, JuryResponse,
    DecisionJuryCreate, DecisionJuryResponse
)
from ..services import JuryService

router = APIRouter()


@router.post("/jurys", response_model=JuryResponse)
async def create_jury(
    jury_data: JuryCreate,
    session: Session = Depends(get_session),
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


@router.get("/jurys", response_model=List[JuryResponse])
async def get_jurys(
    programme_id: Optional[int] = Query(None, description="Filtrer par programme"),
    statut: Optional[str] = Query(None, description="Filtrer par statut"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des jurys"""
    query = select(Jury)
    
    # Appliquer les filtres
    if programme_id:
        query = query.where(Jury.programme_id == programme_id)
    
    if statut:
        query = query.where(Jury.statut == statut)
    
    jurys = session.exec(query.order_by(Jury.session_le.desc())).all()
    return [JuryResponse.from_orm(jury) for jury in jurys]


@router.get("/jurys/{jury_id}", response_model=JuryResponse)
async def get_jury(
    jury_id: int,
    session: Session = Depends(get_session),
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


@router.put("/jurys/{jury_id}", response_model=JuryResponse)
async def update_jury(
    jury_id: int,
    jury_data: JuryUpdate,
    session: Session = Depends(get_session),
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


@router.post("/jurys/{jury_id}/membres")
async def add_jury_member(
    jury_id: int,
    utilisateur_id: int,
    role: str = "membre",
    session: Session = Depends(get_session),
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


@router.get("/jurys/{jury_id}/membres")
async def get_jury_members(
    jury_id: int,
    session: Session = Depends(get_session),
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


@router.post("/jurys/{jury_id}/decisions")
async def create_jury_decision(
    jury_id: int,
    decision_data: DecisionJuryCreate,
    session: Session = Depends(get_session),
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


@router.get("/jurys/{jury_id}/decisions")
async def get_jury_decisions(
    jury_id: int,
    session: Session = Depends(get_session),
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


@router.get("/programmes/{programme_id}/jurys")
async def get_programme_jurys(
    programme_id: int,
    session: Session = Depends(get_session),
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
