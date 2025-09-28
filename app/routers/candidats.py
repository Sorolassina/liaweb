"""
Router pour la gestion des candidats
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form
from sqlmodel import Session, select
from typing import List, Optional
import logging

from app_lia_web.core.database import get_session
from app_lia_web.core.middleware import get_shared_session
from app_lia_web.core.security import get_current_user
from app_lia_web.core.program_schema_integration import safe_count_query, table_exists_anywhere
from app_lia_web.app.models.base import User, Candidat, Entreprise
from app_lia_web.app.models.preinscription import Preinscription
from app_lia_web.app.models.enums import UserRole, StatutDossier
from app_lia_web.app.schemas import (
    CandidatCreate, CandidatUpdate, CandidatResponse,
    EntrepriseCreate, EntrepriseUpdate, EntrepriseResponse,
    CandidatFiltres, PaginationParams, PaginatedResponse
)
from app_lia_web.app.services import CandidatService, EntrepriseService

router = APIRouter()

@router.post("/candidats", response_model=CandidatResponse, name="create_candidat")
async def create_candidat(
    candidat_data: CandidatCreate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Crée un nouveau candidat"""
    # Vérifier si l'email existe déjà
    existing_candidat = CandidatService.get_candidat_by_email(session, candidat_data.email)
    if existing_candidat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un candidat avec cet email existe déjà"
        )
    
    candidat = CandidatService.create_candidat(session, candidat_data)
    return CandidatResponse.from_orm(candidat)


@router.get("/candidats", response_model=PaginatedResponse, name="get_candidats")
async def get_candidats(
    programme_id: Optional[int] = Query(None, description="Filtrer par programme"),
    statut: Optional[StatutDossier] = Query(None, description="Filtrer par statut"),
    handicap: Optional[bool] = Query(None, description="Filtrer par handicap"),
    territoire: Optional[str] = Query(None, description="Filtrer par territoire"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    taille: int = Query(10, ge=1, le=100, description="Taille de page"),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des candidats avec filtres et pagination"""
    filtres = CandidatFiltres(
        programme_id=programme_id,
        statut=statut,
        handicap=handicap,
        territoire=territoire
    )
    pagination = PaginationParams(page=page, taille=taille)
    
    result = CandidatService.get_candidats_with_filters(session, filtres, pagination)
    
    return PaginatedResponse(
        items=[CandidatResponse.from_orm(candidat).dict() for candidat in result["items"]],
        total=result["total"],
        page=result["page"],
        taille=result["taille"],
        pages=result["pages"]
    )


@router.get("/candidats/{candidat_id}", response_model=CandidatResponse, name="get_candidat")
async def get_candidat(
    candidat_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère un candidat par ID"""
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidat non trouvé"
        )
    
    return CandidatResponse.from_orm(candidat)


@router.put("/candidats/{candidat_id}", response_model=CandidatResponse, name="update_candidat")
async def update_candidat(
    candidat_id: int,
    candidat_data: CandidatUpdate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour un candidat"""
    # Vérifier les permissions (conseiller ou candidat lui-même)
    if current_user.role not in [UserRole.CONSEILLER.value, UserRole.RESPONSABLE_PROGRAMME.value, UserRole.ADMINISTRATEUR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    candidat = CandidatService.update_candidat(session, candidat_id, candidat_data)
    if not candidat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidat non trouvé"
        )
    
    return CandidatResponse.from_orm(candidat)


@router.post("/candidats/{candidat_id}/entreprise", response_model=EntrepriseResponse, name="create_entreprise")
async def create_entreprise(
    candidat_id: int,
    entreprise_data: EntrepriseCreate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Crée une entreprise pour un candidat"""
    # Vérifier que le candidat existe
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidat non trouvé"
        )
    
    # Vérifier qu'il n'y a pas déjà une entreprise
    existing_entreprise = EntrepriseService.get_entreprise_by_candidat(session, candidat_id)
    if existing_entreprise:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce candidat a déjà une entreprise"
        )
    
    entreprise_data.candidat_id = candidat_id
    entreprise = EntrepriseService.create_entreprise(session, entreprise_data)
    return EntrepriseResponse.from_orm(entreprise)


@router.get("/candidats/{candidat_id}/entreprise", response_model=EntrepriseResponse, name="get_entreprise")
async def get_entreprise(
    candidat_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère l'entreprise d'un candidat"""
    entreprise = EntrepriseService.get_entreprise_by_candidat(session, candidat_id)
    if not entreprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune entreprise trouvée pour ce candidat"
        )
    
    return EntrepriseResponse.from_orm(entreprise)


@router.put("/candidats/{candidat_id}/entreprise", response_model=EntrepriseResponse, name="update_entreprise")
async def update_entreprise(
    candidat_id: int,
    entreprise_data: EntrepriseUpdate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour l'entreprise d'un candidat"""
    entreprise = EntrepriseService.get_entreprise_by_candidat(session, candidat_id)
    if not entreprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune entreprise trouvée pour ce candidat"
        )
    
    # Mettre à jour les champs
    update_data = entreprise_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entreprise, field, value)
    
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    
    return EntrepriseResponse.from_orm(entreprise)


@router.post("/candidats/{candidat_id}/entreprise/pappers", name="update_entreprise_from_pappers")
async def update_entreprise_from_pappers(
    candidat_id: int,
    siret: str,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour les informations d'entreprise depuis l'API Pappers"""
    entreprise = EntrepriseService.get_entreprise_by_candidat(session, candidat_id)
    if not entreprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune entreprise trouvée pour ce candidat"
        )
    
    updated_entreprise = EntrepriseService.update_entreprise_from_pappers(session, entreprise.id, siret)
    if not updated_entreprise:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de récupérer les données depuis Pappers"
        )
    
    return {"message": "Entreprise mise à jour depuis Pappers", "entreprise": EntrepriseResponse.from_orm(updated_entreprise)}


@router.post("/candidats/{candidat_id}/entreprise/qpv", name="check_qpv_status")
async def check_qpv_status(
    candidat_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Vérifie le statut QPV de l'entreprise d'un candidat"""
    entreprise = EntrepriseService.get_entreprise_by_candidat(session, candidat_id)
    if not entreprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune entreprise trouvée pour ce candidat"
        )
    
    is_qpv = EntrepriseService.check_qpv_status(session, entreprise.id)
    
    return {
        "candidat_id": candidat_id,
        "is_qpv": is_qpv,
        "adresse": entreprise.adresse
    }


@router.get("/candidats/{candidat_id}/preinscriptions", name="get_candidat_preinscriptions")
async def get_candidat_preinscriptions(
    candidat_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les préinscriptions d'un candidat"""
    if not table_exists_anywhere("preinscription", session):
        return []
    
    try:
        preinscriptions = session.exec(
            select(Preinscription)
            .where(Preinscription.candidat_id == candidat_id)
            .order_by(Preinscription.cree_le.desc())
        ).all()
        
        return [{"id": p.id, "programme_id": p.programme_id, "statut": p.statut, "cree_le": p.cree_le} for p in preinscriptions]
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des préinscriptions: {e}")
        return []


# ============================================================================
# ROUTES EMAIL CANDIDAT (fusionnées depuis candidat_email_update.py)
# ============================================================================

logger = logging.getLogger(__name__)

@router.post("/candidats/{candidat_id}/changer-email", name="changer_email_candidat")
def changer_email_candidat(
    candidat_id: int,
    nouvel_email: str = Form(...),
    confirmation_email: str = Form(...),
    raison: str = Form(...),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """
    Change l'email d'un candidat de manière sécurisée
    Nécessite des permissions administrateur et confirmation
    """
    try:
        from app_lia_web.app.services import CandidatEmailService
        
        # Utiliser le service pour changer l'email
        result = CandidatEmailService.change_email_secure(
            session=session,
            candidat_id=candidat_id,
            nouvel_email=nouvel_email,
            confirmation_email=confirmation_email,
            raison=raison,
            current_user=current_user
        )
        
        return result
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur lors du changement d'email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du changement d'email: {str(e)}")


@router.get("/candidats/{candidat_id}/email-history", name="get_email_history")
def get_email_history(
    candidat_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère l'historique des changements d'email pour un candidat
    """
    try:
        from app_lia_web.app.services import CandidatEmailService
        
        # Utiliser le service pour récupérer l'historique
        result = CandidatEmailService.get_email_history(
            session=session,
            candidat_id=candidat_id,
            current_user=current_user
        )
        
        return result
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération de l'historique: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération de l'historique: {str(e)}")
