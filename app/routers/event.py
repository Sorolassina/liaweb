from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime, date, timezone
from typing import List, Optional
import secrets
import string

from app_lia_web.core.database import get_session
from app_lia_web.app.models.base import User
from app_lia_web.app.models.event import Event, InvitationEvent, PresenceEvent
from app_lia_web.app.models.seminaire import Programme, Inscription
from app_lia_web.app.schemas.event_schemas import EventCreate, EventUpdate, InvitationEventCreate, PresenceEventCreate
from app_lia_web.app.services.event_service import EventService
from app_lia_web.core.security import get_current_user
from app_lia_web.app.templates import templates

router = APIRouter()
event_service = EventService()

# === ROUTES PRINCIPALES ===

@router.get("/", name="liste_events", response_class=HTMLResponse)
async def liste_events(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Liste des événements"""
    events = event_service.get_events(db)
    stats = event_service.get_event_stats(db)
    
    return templates.TemplateResponse("events/liste.html", {
        "request": request,
        "events": events,
        "stats": stats,
        "utilisateur": current_user
    })

@router.get("/nouveau", name="form_event", response_class=HTMLResponse)
async def form_event(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire de création d'événement"""
    programmes = db.exec(select(Programme)).all()
    
    return templates.TemplateResponse("events/form.html", {
        "request": request,
        "programmes": programmes,
        "utilisateur": current_user
    })

@router.post("/nouveau", name="creer_event")
async def creer_event(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    heure_debut: str = Form(""),
    heure_fin: str = Form(""),
    lieu: str = Form(""),
    programme_id: int = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Créer un nouvel événement"""
    # Conversion des heures
    heure_debut_dt = None
    heure_fin_dt = None
    
    if heure_debut:
        try:
            heure_debut_dt = datetime.strptime(f"{date_debut} {heure_debut}", "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    
    if heure_fin:
        try:
            heure_fin_dt = datetime.strptime(f"{date_fin} {heure_fin}", "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    
    event_data = EventCreate(
        titre=titre,
        description=description if description else None,
        date_debut=date_debut,
        date_fin=date_fin,
        heure_debut=heure_debut_dt,
        heure_fin=heure_fin_dt,
        lieu=lieu if lieu else None,
        programme_id=programme_id,
        organisateur_id=current_user.id
    )
    
    event = event_service.create_event(event_data, db)
    
    return templates.TemplateResponse("events/detail.html", {
        "request": request,
        "event": event,
        "utilisateur": current_user
    })

@router.get("/{event_id}", name="detail_event", response_class=HTMLResponse)
async def detail_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Détail d'un événement"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    invitations = event_service.get_invitations_by_event(event_id, db)
    presences = event_service.get_presences_by_event(event_id, db)
    stats = event_service.get_presence_stats(event_id, db)
    
    return templates.TemplateResponse("events/detail.html", {
        "request": request,
        "event": event,
        "invitations": invitations,
        "presences": presences,
        "stats": stats,
        "utilisateur": current_user
    })

# === ROUTES D'ÉMARGEMENT ===

@router.get("/{event_id}/emargement", name="emargement_event", response_class=HTMLResponse)
async def emargement_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page d'émargement pour un événement"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    presences = event_service.get_presences_with_invitations(event_id, db)
    stats = event_service.get_presence_stats_with_invitations(event_id, db)
    
    return templates.TemplateResponse("events/emargement.html", {
        "request": request,
        "event": event,
        "presences": presences,
        "stats": stats,
        "utilisateur": current_user
    })

@router.get("/{event_id}/emargement-direct", name="emargement_direct_event", response_class=HTMLResponse)
async def emargement_direct_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session)
):
    """Page publique d'émargement direct pour un événement"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    presences = event_service.get_presences_with_invitations(event_id, db)
    
    return templates.TemplateResponse("events/emargement_direct.html", {
        "request": request,
        "event": event,
        "presences": presences
    })

@router.post("/{event_id}/emargement", name="marquer_presence_event")
async def marquer_presence_event(
    event_id: int,
    request: Request,
    inscription_id: int = Form(...),
    presence: str = Form("present"),
    methode_signature: str = Form("manuel"),
    signature_data: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Marquer la présence d'un candidat à un événement"""
    presence_data = PresenceEventCreate(
        event_id=event_id,
        inscription_id=inscription_id,
        presence=presence,
        methode_signature=methode_signature,
        signature_manuelle=signature_data if methode_signature == "manuel" else None,
        signature_digitale=signature_data if methode_signature == "digital" else None,
        heure_arrivee=datetime.now(timezone.utc),
        commentaire=note if note else None,
        ip_signature=request.client.host
    )
    
    presence_obj = event_service.mark_presence(presence_data, db)
    
    return templates.TemplateResponse("events/emargement_confirmation.html", {
        "request": request,
        "event": event_service.get_event(event_id, db),
        "presence": presence_obj,
        "utilisateur": current_user
    })

# === ROUTES PUBLIQUES (pour les invitations) ===

@router.get("/invitation/{token}", name="invitation_event_page", response_class=HTMLResponse)
async def invitation_event_page(
    token: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """Page publique d'invitation d'événement"""
    invitation = event_service.get_invitation_by_token(token, db)
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    event = event_service.get_event(invitation.event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    return templates.TemplateResponse("events/invitation_public.html", {
        "request": request,
        "invitation": invitation,
        "event": event
    })

@router.get("/invitation/{token}/accepter", name="accepter_invitation_event", response_class=HTMLResponse)
async def accepter_invitation_event(
    token: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """Accepter une invitation d'événement"""
    invitation = event_service.get_invitation_by_token(token, db)
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    event_service.update_invitation_status(invitation.id, "acceptee", db)
    
    return templates.TemplateResponse("events/invitation_confirmation.html", {
        "request": request,
        "invitation": invitation,
        "action": "acceptée"
    })

@router.get("/invitation/{token}/refuser", name="refuser_invitation_event", response_class=HTMLResponse)
async def refuser_invitation_event(
    token: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """Refuser une invitation d'événement"""
    invitation = event_service.get_invitation_by_token(token, db)
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    event_service.update_invitation_status(invitation.id, "refusee", db)
    
    return templates.TemplateResponse("events/invitation_confirmation.html", {
        "request": request,
        "invitation": invitation,
        "action": "refusée"
    })
