"""
Router pour le tableau de bord et les statistiques
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from ..core.database import get_session
from ..core.security import get_current_user
from ..models.base import User, Preinscription, Inscription, Programme, Jury, Candidat
from ..models.enums import UserRole, StatutDossier
from ..schemas import StatistiquesResponse
from ..services import StatistiquesService

router = APIRouter()


@router.get("/dashboard/stats", response_model=StatistiquesResponse)
async def get_dashboard_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les statistiques du tableau de bord"""
    stats = StatistiquesService.get_dashboard_stats(session)
    return stats


@router.get("/dashboard/stats-detaillees")
async def get_detailed_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère des statistiques détaillées pour le tableau de bord"""
    # Statistiques par programme
    stats_par_programme = []
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    
    for programme in programmes:
        preinscriptions_count = session.exec(
            select(Preinscription).where(Preinscription.programme_id == programme.id)
        ).count()
        
        inscriptions_count = session.exec(
            select(Inscription).where(Inscription.programme_id == programme.id)
        ).count()
        
        jurys_count = session.exec(
            select(Jury).where(Jury.programme_id == programme.id)
        ).count()
        
        stats_par_programme.append({
            "programme": programme.nom,
            "code": programme.code,
            "preinscriptions": preinscriptions_count,
            "inscriptions": inscriptions_count,
            "jurys": jurys_count
        })
    
    # Statistiques par statut
    stats_par_statut = {
        "preinscriptions": {},
        "inscriptions": {}
    }
    
    # Préinscriptions par statut
    for statut in StatutDossier:
        count = session.exec(
            select(Preinscription).where(Preinscription.statut == statut)
        ).count()
        stats_par_statut["preinscriptions"][statut.value] = count
    
    # Inscriptions par statut
    for statut in StatutDossier:
        count = session.exec(
            select(Inscription).where(Inscription.statut == statut)
        ).count()
        stats_par_statut["inscriptions"][statut.value] = count
    
    # Évolution sur les 30 derniers jours
    date_30_jours = datetime.now(timezone.utc) - timedelta(days=30)
    
    preinscriptions_30_jours = session.exec(
        select(Preinscription).where(Preinscription.cree_le >= date_30_jours)
    ).count()
    
    inscriptions_30_jours = session.exec(
        select(Inscription).where(Inscription.cree_le >= date_30_jours)
    ).count()
    
    return {
        "stats_par_programme": stats_par_programme,
        "stats_par_statut": stats_par_statut,
        "evolution_30_jours": {
            "preinscriptions": preinscriptions_30_jours,
            "inscriptions": inscriptions_30_jours
        }
    }


@router.get("/dashboard/actions-recentes")
async def get_recent_actions(
    limit: int = 10,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les actions récentes pour le tableau de bord"""
    actions = []
    
    # Préinscriptions récentes
    recent_preinscriptions = session.exec(
        select(Preinscription)
        .order_by(Preinscription.cree_le.desc())
        .limit(limit)
    ).all()
    
    for preinscription in recent_preinscriptions:
        candidat = session.get(Candidat, preinscription.candidat_id)
        programme = session.get(Programme, preinscription.programme_id)
        
        actions.append({
            "type": "preinscription",
            "date": preinscription.cree_le,
            "description": f"Nouvelle préinscription de {candidat.nom} {candidat.prenom} pour {programme.nom}",
            "statut": preinscription.statut.value,
            "id": preinscription.id
        })
    
    # Inscriptions récentes
    recent_inscriptions = session.exec(
        select(Inscription)
        .order_by(Inscription.cree_le.desc())
        .limit(limit)
    ).all()
    
    for inscription in recent_inscriptions:
        candidat = session.get(Candidat, inscription.candidat_id)
        programme = session.get(Programme, inscription.programme_id)
        
        actions.append({
            "type": "inscription",
            "date": inscription.cree_le,
            "description": f"Nouvelle inscription de {candidat.nom} {candidat.prenom} pour {programme.nom}",
            "statut": inscription.statut.value,
            "id": inscription.id
        })
    
    # Jurys récents
    recent_jurys = session.exec(
        select(Jury)
        .order_by(Jury.session_le.desc())
        .limit(limit)
    ).all()
    
    for jury in recent_jurys:
        programme = session.get(Programme, jury.programme_id)
        
        actions.append({
            "type": "jury",
            "date": jury.session_le,
            "description": f"Session de jury programmée pour {programme.nom}",
            "statut": jury.statut,
            "id": jury.id
        })
    
    # Trier par date et limiter
    actions.sort(key=lambda x: x["date"], reverse=True)
    return actions[:limit]


@router.get("/dashboard/alerts")
async def get_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les alertes pour le tableau de bord"""
    alerts = []
    
    # Préinscriptions en attente depuis plus de 7 jours
    date_7_jours = datetime.now(timezone.utc) - timedelta(days=7)
    preinscriptions_en_attente = session.exec(
        select(Preinscription)
        .where(
            Preinscription.statut == StatutDossier.SOUMIS,
            Preinscription.cree_le <= date_7_jours
        )
    ).all()
    
    if preinscriptions_en_attente:
        alerts.append({
            "type": "warning",
            "message": f"{len(preinscriptions_en_attente)} préinscription(s) en attente depuis plus de 7 jours",
            "count": len(preinscriptions_en_attente)
        })
    
    # Jurys programmés dans les 3 prochains jours
    date_3_jours = datetime.now(timezone.utc) + timedelta(days=3)
    jurys_prochains = session.exec(
        select(Jury)
        .where(
            Jury.session_le <= date_3_jours,
            Jury.session_le >= datetime.now(timezone.utc)
        )
    ).all()
    
    if jurys_prochains:
        alerts.append({
            "type": "info",
            "message": f"{len(jurys_prochains)} session(s) de jury programmée(s) dans les 3 prochains jours",
            "count": len(jurys_prochains)
        })
    
    # Programmes sans responsable
    programmes_sans_responsable = session.exec(
        select(Programme)
        .where(
            Programme.actif == True,
            Programme.responsable_id == None
        )
    ).all()
    
    if programmes_sans_responsable:
        alerts.append({
            "type": "error",
            "message": f"{len(programmes_sans_responsable)} programme(s) sans responsable",
            "count": len(programmes_sans_responsable)
        })
    
    return alerts


@router.get("/dashboard/user-stats")
async def get_user_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les statistiques spécifiques à l'utilisateur connecté"""
    user_stats = {}
    
    if current_user.role == UserRole.RESPONSABLE_PROGRAMME.value:
        # Statistiques pour un responsable de programme
        programmes_responsable = session.exec(
            select(Programme).where(Programme.responsable_id == current_user.id)
        ).all()
        
        total_preinscriptions = 0
        total_inscriptions = 0
        
        for programme in programmes_responsable:
            preinscriptions = session.exec(
                select(Preinscription).where(Preinscription.programme_id == programme.id)
            ).count()
            
            inscriptions = session.exec(
                select(Inscription).where(Inscription.programme_id == programme.id)
            ).count()
            
            total_preinscriptions += preinscriptions
            total_inscriptions += inscriptions
        
        user_stats = {
            "programmes_geres": len(programmes_responsable),
            "total_preinscriptions": total_preinscriptions,
            "total_inscriptions": total_inscriptions
        }
    
    elif current_user.role == UserRole.CONSEILLER.value:
        # Statistiques pour un conseiller
        inscriptions_conseiller = session.exec(
            select(Inscription).where(Inscription.conseiller_id == current_user.id)
        ).all()
        
        user_stats = {
            "candidats_accompagnes": len(inscriptions_conseiller),
            "inscriptions_en_cours": len([i for i in inscriptions_conseiller if i.statut == StatutDossier.VALIDE])
        }
    
    elif current_user.role == UserRole.ADMINISTRATEUR.value:
        # Statistiques pour un administrateur
        total_users = session.exec(select(User)).count()
        total_programmes = session.exec(select(Programme)).count()
        total_candidats = session.exec(select(Candidat)).count()
        
        user_stats = {
            "total_users": total_users,
            "total_programmes": total_programmes,
            "total_candidats": total_candidats
        }
    
    return user_stats
