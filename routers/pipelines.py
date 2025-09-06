"""
Router pour la gestion des pipelines de formation
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from ..core.database import get_session
from ..core.security import get_current_user, require_permission
from ..models.base import User, EtapePipeline, AvancementEtape, Programme, Inscription
from ..models.enums import UserRole, StatutDossier
from ..schemas import EtapePipelineCreate, EtapePipelineUpdate, AvancementEtapeCreate
from ..services import PipelineService

router = APIRouter()


@router.get("/pipelines/{programme_id}/etapes", response_model=List[dict])
async def get_pipeline_etapes(
    programme_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les étapes du pipeline d'un programme"""
    etapes = PipelineService.get_pipeline_etapes(session, programme_id)
    return etapes


@router.post("/pipelines/{programme_id}/etapes")
async def create_pipeline_etape(
    programme_id: int,
    etape: EtapePipelineCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crée une nouvelle étape dans le pipeline d'un programme"""
    require_permission(current_user, [UserRole.DIRECTEUR_TECHNIQUE.value, UserRole.RESPONSABLE_PROGRAMME.value])
    
    nouvelle_etape = PipelineService.create_pipeline_etape(session, programme_id, etape)
    return {"message": "Étape créée avec succès", "etape": nouvelle_etape}


@router.put("/pipelines/etapes/{etape_id}")
async def update_pipeline_etape(
    etape_id: int,
    etape_update: EtapePipelineUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour une étape du pipeline"""
    require_permission(current_user, [UserRole.DIRECTEUR_TECHNIQUE.value, UserRole.RESPONSABLE_PROGRAMME.value])
    
    etape = PipelineService.update_pipeline_etape(session, etape_id, etape_update)
    return {"message": "Étape mise à jour avec succès", "etape": etape}


@router.delete("/pipelines/etapes/{etape_id}")
async def delete_pipeline_etape(
    etape_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprime une étape du pipeline"""
    require_permission(current_user, [UserRole.DIRECTEUR_TECHNIQUE.value])
    
    PipelineService.delete_pipeline_etape(session, etape_id)
    return {"message": "Étape supprimée avec succès"}


@router.post("/pipelines/etapes/{etape_id}/toggle")
async def toggle_pipeline_etape(
    etape_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Active/désactive une étape du pipeline"""
    require_permission(current_user, [UserRole.DIRECTEUR_TECHNIQUE.value, UserRole.RESPONSABLE_PROGRAMME.value])
    
    etape = PipelineService.toggle_pipeline_etape(session, etape_id)
    return {"message": f"Étape {'activée' if etape.active else 'désactivée'} avec succès", "etape": etape}


@router.get("/inscriptions/{inscription_id}/avancement")
async def get_inscription_avancement(
    inscription_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère l'avancement d'un candidat dans le pipeline"""
    avancement = PipelineService.get_inscription_avancement(session, inscription_id)
    return avancement


@router.post("/inscriptions/{inscription_id}/avancement")
async def update_inscription_avancement(
    inscription_id: int,
    avancement: AvancementEtapeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour l'avancement d'un candidat dans le pipeline"""
    require_permission(current_user, [UserRole.CONSEILLER.value, UserRole.RESPONSABLE_PROGRAMME.value])
    
    nouvel_avancement = PipelineService.update_inscription_avancement(session, inscription_id, avancement)
    return {"message": "Avancement mis à jour avec succès", "avancement": nouvel_avancement}


@router.get("/pipelines/{programme_id}/statistiques")
async def get_pipeline_statistiques(
    programme_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les statistiques du pipeline d'un programme"""
    stats = PipelineService.get_pipeline_statistiques(session, programme_id)
    return stats


@router.get("/pipelines/etapes/{etape_id}/candidats")
async def get_candidats_par_etape(
    etape_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les candidats à une étape spécifique du pipeline"""
    candidats = PipelineService.get_candidats_par_etape(session, etape_id, skip, limit)
    return candidats


@router.post("/pipelines/{programme_id}/reinitialiser")
async def reinitialiser_pipeline(
    programme_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Réinitialise le pipeline d'un programme (supprime tous les avancements)"""
    require_permission(current_user, [UserRole.DIRECTEUR_TECHNIQUE.value])
    
    PipelineService.reinitialiser_pipeline(session, programme_id)
    return {"message": "Pipeline réinitialisé avec succès"}


@router.get("/pipelines/etapes/{etape_id}/details")
async def get_etape_details(
    etape_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les détails d'une étape du pipeline"""
    etape = session.get(EtapePipeline, etape_id)
    if not etape:
        raise HTTPException(status_code=404, detail="Étape non trouvée")
    
    # Compter les candidats à cette étape
    candidats_count = session.exec(
        select(AvancementEtape)
        .where(AvancementEtape.etape_id == etape_id)
    ).count()
    
    return {
        "etape": etape,
        "candidats_count": candidats_count
    }


@router.post("/pipelines/etapes/{etape_id}/reordonner")
async def reordonner_etapes(
    etape_id: int,
    nouvelle_position: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Réordonne les étapes du pipeline"""
    require_permission(current_user, [UserRole.DIRECTEUR_TECHNIQUE.value, UserRole.RESPONSABLE_PROGRAMME.value])
    
    PipelineService.reordonner_etapes(session, etape_id, nouvelle_position)
    return {"message": "Ordre des étapes mis à jour avec succès"}
