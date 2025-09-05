"""
Router pour la gestion des programmes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from ..core.database import get_session
from ..core.security import get_current_user
from ..models.base import User, Programme
from ..models.enums import UserRole
from ..schemas import ProgrammeCreate, ProgrammeUpdate, ProgrammeResponse
from ..services import ProgrammeService
from ..models.base import Preinscription, Inscription, Jury

router = APIRouter()


@router.post("/programmes", response_model=ProgrammeResponse)
async def create_programme(
    programme_data: ProgrammeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crée un nouveau programme (directeur technique seulement)"""
    if current_user.role != UserRole.DIRECTEUR_TECHNIQUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le directeur technique peut créer des programmes"
        )
    
    # Vérifier si le code existe déjà
    existing_programme = ProgrammeService.get_programme_by_code(session, programme_data.code)
    if existing_programme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un programme avec ce code existe déjà"
        )
    
    programme = ProgrammeService.create_programme(session, programme_data)
    return ProgrammeResponse.from_orm(programme)


@router.get("/programmes", response_model=List[ProgrammeResponse])
async def get_programmes(
    actif: bool = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des programmes"""
    if actif is not None:
        programmes = session.exec(select(Programme).where(Programme.actif == actif)).all()
    else:
        programmes = session.exec(select(Programme)).all()
    
    return [ProgrammeResponse.from_orm(programme) for programme in programmes]


@router.get("/programmes/{programme_id}", response_model=ProgrammeResponse)
async def get_programme(
    programme_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère un programme par ID"""
    programme = session.get(Programme, programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    return ProgrammeResponse.from_orm(programme)


@router.put("/programmes/{programme_id}", response_model=ProgrammeResponse)
async def update_programme(
    programme_id: int,
    programme_data: ProgrammeUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour un programme (directeur technique seulement)"""
    if current_user.role != UserRole.DIRECTEUR_TECHNIQUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le directeur technique peut modifier les programmes"
        )
    
    programme = ProgrammeService.update_programme(session, programme_id, programme_data)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    return ProgrammeResponse.from_orm(programme)


@router.get("/programmes/{programme_id}/statistiques")
async def get_programme_stats(
    programme_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les statistiques d'un programme"""
    programme = session.get(Programme, programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    # Compter les préinscriptions
    preinscriptions_count = session.exec(
        select(Preinscription).where(Preinscription.programme_id == programme_id)
    ).count()
    
    # Compter les inscriptions
    inscriptions_count = session.exec(
        select(Inscription).where(Inscription.programme_id == programme_id)
    ).count()
    
    # Compter les jurys
    jurys_count = session.exec(
        select(Jury).where(Jury.programme_id == programme_id)
    ).count()
    
    return {
        "programme": programme.nom,
        "preinscriptions": preinscriptions_count,
        "inscriptions": inscriptions_count,
        "jurys": jurys_count
    }
