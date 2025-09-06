"""
Router pour la gestion des inscriptions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional

from ..core.database import get_session
from ..core.security import get_current_user
from ..models.base import User, Inscription, Candidat, Programme, Preinscription
from ..models.enums import UserRole, StatutDossier
from ..schemas import (
    InscriptionCreate, InscriptionUpdate, InscriptionResponse,
    PaginationParams, PaginatedResponse
)
from ..services import InscriptionService

router = APIRouter()


@router.post("/inscriptions", response_model=InscriptionResponse)
async def create_inscription(
    inscription_data: InscriptionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crée une nouvelle inscription (responsable programme seulement)"""
    # Vérifier les permissions
    if current_user.role != UserRole.RESPONSABLE_PROGRAMME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le responsable de programme peut créer des inscriptions"
        )
    
    # Vérifier que le programme existe et est actif
    programme = session.get(Programme, inscription_data.programme_id)
    if not programme or not programme.actif:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Programme non trouvé ou inactif"
        )
    
    # Vérifier que le candidat existe
    candidat = session.get(Candidat, inscription_data.candidat_id)
    if not candidat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidat non trouvé"
        )
    
    # Vérifier qu'il n'y a pas déjà une inscription pour ce candidat/programme
    existing_inscription = session.exec(
        select(Inscription).where(
            Inscription.programme_id == inscription_data.programme_id,
            Inscription.candidat_id == inscription_data.candidat_id
        )
    ).first()
    
    if existing_inscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Une inscription existe déjà pour ce candidat dans ce programme"
        )
    
    inscription = InscriptionService.create_inscription(session, inscription_data)
    return InscriptionResponse.from_orm(inscription)


@router.get("/inscriptions", response_model=PaginatedResponse)
async def get_inscriptions(
    programme_id: Optional[int] = Query(None, description="Filtrer par programme"),
    statut: Optional[StatutDossier] = Query(None, description="Filtrer par statut"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    taille: int = Query(10, ge=1, le=100, description="Taille de page"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des inscriptions avec filtres et pagination"""
    query = select(Inscription)
    
    # Appliquer les filtres
    if programme_id:
        query = query.where(Inscription.programme_id == programme_id)
    
    if statut:
        query = query.where(Inscription.statut == statut)
    
    # Pagination
    offset = (page - 1) * taille
    total = session.exec(select(Inscription)).count()
    
    inscriptions = session.exec(query.offset(offset).limit(taille)).all()
    
    return PaginatedResponse(
        items=[InscriptionResponse.from_orm(i).dict() for i in inscriptions],
        total=total,
        page=page,
        taille=taille,
        pages=(total + taille - 1) // taille
    )


@router.get("/inscriptions/{inscription_id}", response_model=InscriptionResponse)
async def get_inscription(
    inscription_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère une inscription par ID"""
    inscription = session.get(Inscription, inscription_id)
    if not inscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscription non trouvée"
        )
    
    return InscriptionResponse.from_orm(inscription)


@router.put("/inscriptions/{inscription_id}", response_model=InscriptionResponse)
async def update_inscription(
    inscription_id: int,
    inscription_data: InscriptionUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour une inscription"""
    # Vérifier les permissions
    if current_user.role not in [UserRole.RESPONSABLE_PROGRAMME.value, UserRole.CONSEILLER.value, UserRole.ADMINISTRATEUR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    inscription = InscriptionService.update_inscription_status(session, inscription_id, inscription_data.statut)
    if not inscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscription non trouvée"
        )
    
    # Mettre à jour les autres champs si fournis
    update_data = inscription_data.dict(exclude_unset=True, exclude={'statut'})
    for field, value in update_data.items():
        setattr(inscription, field, value)
    
    session.add(inscription)
    session.commit()
    session.refresh(inscription)
    
    return InscriptionResponse.from_orm(inscription)


@router.post("/inscriptions/{inscription_id}/status")
async def update_inscription_status(
    inscription_id: int,
    statut: StatutDossier,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour le statut d'une inscription"""
    # Vérifier les permissions
    if current_user.role not in [UserRole.RESPONSABLE_PROGRAMME.value, UserRole.ADMINISTRATEUR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    inscription = InscriptionService.update_inscription_status(session, inscription_id, statut)
    if not inscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscription non trouvée"
        )
    
    return {
        "message": f"Statut de l'inscription mis à jour vers {statut}",
        "inscription": InscriptionResponse.from_orm(inscription)
    }


@router.get("/programmes/{programme_id}/inscriptions")
async def get_programme_inscriptions(
    programme_id: int,
    statut: Optional[StatutDossier] = Query(None, description="Filtrer par statut"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les inscriptions d'un programme"""
    # Vérifier que le programme existe
    programme = session.get(Programme, programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    query = select(Inscription).where(Inscription.programme_id == programme_id)
    
    if statut:
        query = query.where(Inscription.statut == statut)
    
    inscriptions = session.exec(query.order_by(Inscription.cree_le.desc())).all()
    
    return [InscriptionResponse.from_orm(i).dict() for i in inscriptions]


@router.post("/preinscriptions/{preinscription_id}/valider")
async def valider_preinscription(
    preinscription_id: int,
    conseiller_id: Optional[int] = None,
    referent_id: Optional[int] = None,
    promotion_id: Optional[int] = None,
    groupe_id: Optional[int] = None,
    envoyer_email: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Valide une préinscription en créant une inscription"""
    # Vérifier les permissions
    if current_user.role != UserRole.RESPONSABLE_PROGRAMME.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le responsable de programme peut valider les préinscriptions"
        )
    
    # Récupérer la préinscription
    preinscription = session.get(Preinscription, preinscription_id)
    if not preinscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préinscription non trouvée"
        )
    
    if preinscription.statut != StatutDossier.VALIDE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La préinscription doit être validée avant de créer une inscription"
        )
    
    # Créer l'inscription
    inscription_data = InscriptionCreate(
        programme_id=preinscription.programme_id,
        candidat_id=preinscription.candidat_id,
        conseiller_id=conseiller_id,
        referent_id=referent_id,
        promotion_id=promotion_id,
        groupe_id=groupe_id
    )
    
    inscription = InscriptionService.create_inscription(session, inscription_data)
    
    # Mettre à jour le statut de la préinscription
    preinscription.statut = StatutDossier.INSCRIT
    session.add(preinscription)
    session.commit()
    
    # Envoyer l'email de confirmation si demandé
    if envoyer_email:
        # TODO: Implémenter l'envoi d'email
        pass
    
    return {
        "message": "Préinscription validée et inscription créée",
        "inscription": InscriptionResponse.from_orm(inscription)
    }
