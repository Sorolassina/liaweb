"""
Router pour la gestion du Codéveloppement
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, and_, or_, func
from datetime import datetime, timezone, date, timedelta

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user
from app_lia_web.app.models.base import User, Programme, Promotion, Groupe
from app_lia_web.app.models.codev import (
    CycleCodev, GroupeCodev, SeanceCodev, PresentationCodev, 
    ContributionCodev, MembreGroupeCodev, ParticipationSeance
)
from app_lia_web.app.models.enums import UserRole, StatutCycleCodev, StatutGroupeCodev
from app_lia_web.app.services.codev_service import CodevService
from app_lia_web.app.schemas.codev import (
    CycleCodevCreate, CycleCodevUpdate, GroupeCodevCreate, SeanceCodevCreate,
    PresentationCodevCreate, ContributionCodevCreate, MembreGroupeCodevCreate,
    CycleCodevResponse, GroupeCodevResponse, SeanceCodevResponse,
    StatistiquesCycleCodev, PlanificationSeance, EngagementCandidat, RetourExperience
)
from app_lia_web.app.templates import templates
from app_lia_web.core.config import settings

router = APIRouter()

def codev_access_required(current_user: User):
    """Vérifie que l'utilisateur a accès au module Codev"""
    allowed_roles = [
        UserRole.ADMINISTRATEUR.value,
        UserRole.DIRECTEUR_TECHNIQUE.value,
        UserRole.RESPONSABLE_PROGRAMME.value,
        UserRole.COORDINATEUR.value,
        UserRole.CONSEILLER.value,
        UserRole.FORMATEUR.value
    ]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé au module Codéveloppement"
        )

# ===== ROUTES WEB =====

@router.get("/", name="codev_dashboard", response_class=HTMLResponse)
async def codev_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Tableau de bord du codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer les cycles actifs
    cycles_actifs = session.exec(
        select(CycleCodev)
        .where(CycleCodev.statut.in_([StatutCycleCodev.PLANIFIE.value, StatutCycleCodev.EN_COURS.value]))
        .order_by(CycleCodev.date_debut.desc())
    ).all()
    
    # Récupérer les prochaines séances
    prochaines_seances = CodevService.get_prochaines_seances(session, limit=5)
    
    # Récupérer les engagements en cours
    engagements_en_cours = CodevService.get_engagements_en_cours(session)
    
    return templates.TemplateResponse(
        "codev/dashboard.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycles_actifs": cycles_actifs,
            "prochaines_seances": prochaines_seances,
            "engagements_en_cours": engagements_en_cours,
            "settings": settings
        }
    )

@router.get("/cycles", response_class=HTMLResponse)
async def codev_cycles(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(None)
):
    """Liste des cycles de codéveloppement"""
    codev_access_required(current_user)
    
    stmt = select(CycleCodev)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CycleCodev.nom.ilike(like),
                CycleCodev.description.ilike(like)
            )
        )
    
    cycles = session.exec(stmt.order_by(CycleCodev.date_debut.desc())).all()
    
    return templates.TemplateResponse(
        "codev/cycles.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycles": cycles,
            "q": q or "",
            "settings": settings
        }
    )

@router.get("/cycles/creer", response_class=HTMLResponse)
async def codev_cycles_creer(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire de création d'un cycle"""
    codev_access_required(current_user)
    
    # Récupérer les programmes et promotions
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    promotions = session.exec(select(Promotion).where(Promotion.actif == True)).all()
    
    # Récupérer les animateurs potentiels
    animateurs = session.exec(
        select(User).where(
            User.role.in_([
                UserRole.CONSEILLER.value,
                UserRole.FORMATEUR.value,
                UserRole.COORDINATEUR.value,
                UserRole.RESPONSABLE_PROGRAMME.value
            ])
        )
    ).all()
    
    return templates.TemplateResponse(
        "codev/cycle_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programmes": programmes,
            "promotions": promotions,
            "animateurs": animateurs,
            "settings": settings
        }
    )

@router.post("/cycles/creer")
async def codev_cycles_creer_post(
    request: Request,
    nom: str = Form(...),
    description: Optional[str] = Form(None),
    programme_id: int = Form(...),
    promotion_id: Optional[int] = Form(None),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    nombre_seances: int = Form(6),
    duree_seance: int = Form(180),
    animateur_principal_id: Optional[int] = Form(None),
    objectifs_cycle: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Création d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    try:
        cycle = CodevService.create_cycle_codev(
            session=session,
            nom=nom,
            programme_id=programme_id,
            promotion_id=promotion_id,
            date_debut=date_debut,
            date_fin=date_fin,
            nombre_seances=nombre_seances,
            animateur_principal_id=animateur_principal_id
        )
        
        if objectifs_cycle:
            cycle.objectifs_cycle = objectifs_cycle
            session.commit()
        
        return RedirectResponse(
            url=f"/codev/cycles/{cycle.id}?success=1&action=create",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur création cycle: {e}")
        return RedirectResponse(
            url=f"/codev/cycles/creer?error=1&message={str(e)}",
            status_code=303
        )

@router.get("/cycles/{cycle_id}", response_class=HTMLResponse)
async def codev_cycle_detail(
    cycle_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Détail d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    cycle = session.get(CycleCodev, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle introuvable")
    
    # Récupérer les groupes du cycle
    groupes = session.exec(
        select(GroupeCodev).where(GroupeCodev.cycle_id == cycle_id)
    ).all()
    
    # Récupérer les statistiques
    stats = CodevService.get_statistiques_cycle(session, cycle_id)
    
    return templates.TemplateResponse(
        "codev/cycle_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycle": cycle,
            "groupes": groupes,
            "stats": stats,
            "settings": settings
        }
    )

@router.get("/groupes", response_class=HTMLResponse)
async def codev_groupes(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    cycle_id: Optional[int] = Query(None)
):
    """Liste des groupes de codéveloppement"""
    codev_access_required(current_user)
    
    stmt = select(GroupeCodev)
    if cycle_id:
        stmt = stmt.where(GroupeCodev.cycle_id == cycle_id)
    
    groupes = session.exec(stmt.order_by(GroupeCodev.nom_groupe)).all()
    
    # Récupérer les cycles pour le filtre
    cycles = session.exec(select(CycleCodev)).all()
    
    return templates.TemplateResponse(
        "codev/groupes.html",
        {
            "request": request,
            "utilisateur": current_user,
            "groupes": groupes,
            "cycles": cycles,
            "cycle_id": cycle_id,
            "settings": settings
        }
    )

@router.get("/groupes/creer", response_class=HTMLResponse)
async def codev_groupes_creer(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    cycle_id: Optional[int] = Query(None)
):
    """Formulaire de création d'un groupe de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer les cycles disponibles
    cycles = session.exec(select(CycleCodev)).all()
    
    # Récupérer les groupes disponibles
    groupes = session.exec(select(Groupe)).all()
    
    # Récupérer les utilisateurs pouvant être animateurs
    animateurs = session.exec(
        select(User).where(User.role.in_([
            UserRole.RESPONSABLE_PROGRAMME.value,
            UserRole.CONSEILLER.value,
            UserRole.COORDINATEUR.value,
            UserRole.FORMATEUR.value,
            UserRole.ACCOMPAGNATEUR.value
        ]))
    ).all()
    
    return templates.TemplateResponse(
        "codev/groupe_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycles": cycles,
            "groupes": groupes,
            "animateurs": animateurs,
            "cycle_id": cycle_id,
            "settings": settings
        }
    )

@router.post("/groupes/creer")
async def codev_groupes_creer_post(
    request: Request,
    cycle_id: int = Form(...),
    groupe_id: int = Form(...),
    nom_groupe: str = Form(...),
    animateur_id: Optional[int] = Form(None),
    capacite_max: int = Form(12),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Création d'un groupe de codéveloppement"""
    codev_access_required(current_user)
    
    try:
        groupe_codev = CodevService.create_groupe_codev(
            session=session,
            cycle_id=cycle_id,
            groupe_id=groupe_id,
            nom_groupe=nom_groupe,
            animateur_id=animateur_id,
            capacite_max=capacite_max
        )
        
        return RedirectResponse(
            url=f"/codev/groupes?cycle_id={cycle_id}&success=1&action=create",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur création groupe: {e}")
        return RedirectResponse(
            url=f"/codev/groupes/creer?error=1&message={str(e)}",
            status_code=303
        )

@router.get("/statistiques", response_class=HTMLResponse)
async def codev_statistiques(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Statistiques du système de codéveloppement"""
    codev_access_required(current_user)
    
    # Statistiques générales
    nb_cycles = session.exec(select(func.count()).select_from(CycleCodev)).one()
    nb_groupes = session.exec(select(func.count()).select_from(GroupeCodev)).one()
    nb_membres = session.exec(select(func.count()).select_from(MembreGroupeCodev)).one()
    nb_seances = session.exec(select(func.count()).select_from(SeanceCodev)).one()
    nb_presentations = session.exec(select(func.count()).select_from(PresentationCodev)).one()
    
    # Cycles par statut
    cycles_par_statut = session.exec(
        select(CycleCodev.statut, func.count())
        .group_by(CycleCodev.statut)
    ).all()
    
    # Groupes par statut
    groupes_par_statut = session.exec(
        select(GroupeCodev.statut, func.count())
        .group_by(GroupeCodev.statut)
    ).all()
    
    # Séances par statut
    seances_par_statut = session.exec(
        select(SeanceCodev.statut, func.count())
        .group_by(SeanceCodev.statut)
    ).all()
    
    # Présentations par statut
    presentations_par_statut = session.exec(
        select(PresentationCodev.statut, func.count())
        .group_by(PresentationCodev.statut)
    ).all()
    
    # Cycles récents
    cycles_recents = session.exec(
        select(CycleCodev)
        .order_by(CycleCodev.cree_le.desc())
        .limit(5)
    ).all()
    
    # Groupes avec le plus de membres
    groupes_populaires = session.exec(
        select(GroupeCodev, func.count(MembreGroupeCodev.id).label('nb_membres'))
        .select_from(GroupeCodev)
        .join(MembreGroupeCodev, GroupeCodev.id == MembreGroupeCodev.groupe_codev_id)
        .group_by(GroupeCodev.id)
        .order_by(func.count(MembreGroupeCodev.id).desc())
        .limit(5)
    ).all()
    
    return templates.TemplateResponse(
        "codev/statistiques.html",
        {
            "request": request,
            "utilisateur": current_user,
            "nb_cycles": nb_cycles,
            "nb_groupes": nb_groupes,
            "nb_membres": nb_membres,
            "nb_seances": nb_seances,
            "nb_presentations": nb_presentations,
            "cycles_par_statut": cycles_par_statut,
            "groupes_par_statut": groupes_par_statut,
            "seances_par_statut": seances_par_statut,
            "presentations_par_statut": presentations_par_statut,
            "cycles_recents": cycles_recents,
            "groupes_populaires": groupes_populaires,
            "settings": settings
        }
    )

@router.get("/seances", response_class=HTMLResponse)
async def codev_seances(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    groupe_id: Optional[int] = Query(None),
    statut: Optional[str] = Query(None)
):
    """Liste des séances de codéveloppement"""
    codev_access_required(current_user)
    
    stmt = select(SeanceCodev)
    if groupe_id:
        stmt = stmt.where(SeanceCodev.groupe_id == groupe_id)
    if statut:
        stmt = stmt.where(SeanceCodev.statut == statut)
    
    seances = session.exec(stmt.order_by(SeanceCodev.date_seance.desc())).all()
    
    # Récupérer les groupes pour le filtre
    groupes = session.exec(select(GroupeCodev)).all()
    
    return templates.TemplateResponse(
        "codev/seances.html",
        {
            "request": request,
            "utilisateur": current_user,
            "seances": seances,
            "groupes": groupes,
            "groupe_id": groupe_id,
            "statut": statut,
            "settings": settings
        }
    )

@router.get("/seances/creer", response_class=HTMLResponse)
async def codev_seance_creer_form(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire de création d'une séance"""
    codev_access_required(current_user)
    
    # Récupérer les groupes disponibles
    groupes = session.exec(select(GroupeCodev)).all()
    
    # Récupérer les utilisateurs animateurs
    animateurs = session.exec(
        select(User).where(User.role.in_([
            UserRole.ADMINISTRATEUR.value, 
            UserRole.COACH_EXTERNE.value,
            UserRole.FORMATEUR.value,
            UserRole.ACCOMPAGNATEUR.value
        ]))
    ).all()
    
    return templates.TemplateResponse(
        "codev/seance_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "groupes": groupes,
            "animateurs": animateurs,
            "settings": settings
        }
    )

@router.post("/seances/creer")
async def codev_seance_creer(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    groupe_id: int = Form(...),
    numero_seance: int = Form(...),
    date_seance: str = Form(...),
    lieu: Optional[str] = Form(None),
    animateur_id: Optional[int] = Form(None),
    duree_minutes: int = Form(180),
    objectifs: Optional[str] = Form(None)
):
    """Création d'une séance de codéveloppement"""
    codev_access_required(current_user)
    
    try:
        # Convertir la date
        date_seance_dt = datetime.fromisoformat(date_seance.replace('Z', '+00:00'))
        
        # Créer la séance
        seance_data = SeanceCodevCreate(
            groupe_id=groupe_id,
            numero_seance=numero_seance,
            date_seance=date_seance_dt,
            lieu=lieu,
            animateur_id=animateur_id,
            duree_minutes=duree_minutes,
            objectifs=objectifs,
            statut=StatutSeanceCodev.PLANIFIEE.value
        )
        
        seance = CodevService.create_seance(session, seance_data)
        
        return RedirectResponse(
            url=f"/codev/seances?success=1&message=Séance créée avec succès",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur création séance: {e}")
        return RedirectResponse(
            url=f"/codev/seances/creer?error=1&message={str(e)}",
            status_code=303
        )

@router.get("/presentations/{presentation_id}", response_class=HTMLResponse)
async def codev_presentation_detail(
    presentation_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Détail d'une présentation de codéveloppement"""
    codev_access_required(current_user)
    
    presentation = session.get(PresentationCodev, presentation_id)
    if not presentation:
        raise HTTPException(status_code=404, detail="Présentation introuvable")
    
    # Récupérer la séance associée
    seance = session.get(SeanceCodev, presentation.seance_id)
    
    # Récupérer le candidat
    candidat = session.get(Inscription, presentation.candidat_id)
    
    return templates.TemplateResponse(
        "codev/presentation_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "presentation": presentation,
            "seance": seance,
            "candidat": candidat,
            "settings": settings
        }
    )

# ===== ROUTES API =====

@router.get("/api/codev/cycles", response_model=List[CycleCodevResponse])
async def api_cycles(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    statut: Optional[StatutCycleCodev] = Query(None)
):
    """API: Liste des cycles de codéveloppement"""
    codev_access_required(current_user)
    
    stmt = select(CycleCodev)
    if statut:
        stmt = stmt.where(CycleCodev.statut == statut)
    
    cycles = session.exec(stmt.order_by(CycleCodev.date_debut.desc())).all()
    return cycles

@router.post("/api/codev/cycles", response_model=CycleCodevResponse)
async def api_create_cycle(
    cycle_data: CycleCodevCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Création d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    cycle = CodevService.create_cycle_codev(
        session=session,
        nom=cycle_data.nom,
        programme_id=cycle_data.programme_id,
        promotion_id=cycle_data.promotion_id,
        date_debut=cycle_data.date_debut,
        date_fin=cycle_data.date_fin,
        nombre_seances=cycle_data.nombre_seances_prevues,
        animateur_principal_id=cycle_data.animateur_principal_id
    )
    
    return cycle

@router.get("/api/codev/cycles/{cycle_id}/statistiques", response_model=StatistiquesCycleCodev)
async def api_cycle_stats(
    cycle_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Statistiques d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    stats = CodevService.get_statistiques_cycle(session, cycle_id)
    return stats

@router.post("/api/codev/seances/{seance_id}/planifier")
async def api_planifier_seance(
    seance_id: int,
    planification: PlanificationSeance,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Planifier les présentations d'une séance"""
    codev_access_required(current_user)
    
    presentations = CodevService.planifier_presentations_seance(
        session=session,
        seance_id=seance_id,
        candidats_ids=planification.candidats_ids,
        ordre_presentations=planification.ordre_presentations
    )
    
    return {"message": f"{len(presentations)} présentations planifiées"}

@router.post("/api/codev/presentations/{presentation_id}/engagement")
async def api_prendre_engagement(
    presentation_id: int,
    engagement: EngagementCandidat,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Prendre un engagement pour une présentation"""
    codev_access_required(current_user)
    
    presentation = CodevService.marquer_engagement_pris(
        session=session,
        presentation_id=presentation_id,
        engagement=engagement.engagement,
        delai_engagement=engagement.delai_engagement
    )
    
    return {"message": "Engagement pris avec succès"}

@router.post("/api/codev/presentations/{presentation_id}/retour")
async def api_ajouter_retour(
    presentation_id: int,
    retour: RetourExperience,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Ajouter un retour d'expérience"""
    codev_access_required(current_user)
    
    presentation = CodevService.ajouter_retour_experience(
        session=session,
        presentation_id=presentation_id,
        notes_candidat=retour.notes_candidat
    )
    
    return {"message": "Retour d'expérience ajouté avec succès"}

import logging
logger = logging.getLogger(__name__)
