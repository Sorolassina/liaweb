from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
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
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = None
):
    """Liste des événements"""
    events = event_service.get_events(db, programme_id=programme_id)
    stats = event_service.get_event_stats(db)
    programmes = db.exec(select(Programme).where(Programme.actif == True)).all()
    
    return templates.TemplateResponse("events/liste.html", {
        "request": request,
        "events": events,
        "stats": stats,
        "programmes": programmes,
        "utilisateur": current_user,
        "programme_id": programme_id
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
    
    presences_data = event_service.get_presences_with_combined_status(event.id, db)
    stats = event_service.get_presence_stats_with_invitations(event.id, db)
    
    return templates.TemplateResponse("events/detail.html", {
        "request": request,
        "event": event,
        "presences_data": presences_data,
        "stats": stats,
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
    
    presences_data = event_service.get_presences_with_combined_status(event_id, db)
    stats = event_service.get_presence_stats_with_invitations(event_id, db)
    
    return templates.TemplateResponse("events/detail.html", {
        "request": request,
        "event": event,
        "presences_data": presences_data,
        "stats": stats,
        "utilisateur": current_user
    })

@router.get("/{event_id}/edit", name="edit_event", response_class=HTMLResponse)
async def edit_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire d'édition d'un événement"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    programmes = db.exec(select(Programme)).all()
    
    return templates.TemplateResponse("events/edit.html", {
        "request": request,
        "event": event,
        "programmes": programmes,
        "utilisateur": current_user
    })

@router.post("/{event_id}/update", name="update_event")
async def update_event(
    event_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    heure_debut: str = Form(""),
    heure_fin: str = Form(""),
    lieu: str = Form(""),
    programme_id: int = Form(...),
    statut: str = Form("planifie"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour un événement"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
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
    
    # Préparer les données de mise à jour
    update_data = EventUpdate(
        titre=titre,
        description=description if description else None,
        date_debut=date_debut,
        date_fin=date_fin,
        heure_debut=heure_debut_dt,
        heure_fin=heure_fin_dt,
        lieu=lieu if lieu else None,
        programme_id=programme_id,
        statut=statut
    )
    
    # Mettre à jour l'événement
    updated_event = event_service.update_event(event_id, update_data, db)
    
    # Rediriger vers la page de détail
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)

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
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page d'émargement direct pour un événement (mode tablette avec authentification)"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    presences = event_service.get_presences_with_invitations(event_id, db)
    
    return templates.TemplateResponse("events/emargement_direct.html", {
        "request": request,
        "event": event,
        "presences": presences,
        "utilisateur": current_user
    })

@router.get("/{event_id}/invitations", name="invitations_event", response_class=HTMLResponse)
async def invitations_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de gestion des invitations"""
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    invitations = event_service.get_invitations_by_event(event_id, db)
    
    # Récupérer les candidats disponibles pour invitation
    from app_lia_web.app.models.base import Inscription, Candidat
    
    inscriptions = db.exec(
        select(Inscription)
        .join(Candidat)
        .where(Inscription.programme_id == event.programme_id)
    ).all()
    
    return templates.TemplateResponse("events/invitations.html", {
        "request": request,
        "event": event,
        "invitations": invitations,
        "inscriptions": inscriptions,
        "utilisateur": current_user
    })

@router.post("/{event_id}/invitations/envoyer", name="envoyer_invitations_event")
async def envoyer_invitations_event(
    event_id: int,
    request: Request,
    type_invitation: str = Form(...),
    candidats_ids: List[int] = Form([]),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer des invitations"""
    from app_lia_web.app.models.enums import TypeInvitation
    
    type_inv = TypeInvitation(type_invitation)
    invitations = event_service.send_invitations_bulk(event_id, type_inv, candidats_ids, db)
    
    return RedirectResponse(url=f"/events/{event_id}/invitations", status_code=303)


@router.post("/{event_id}/emargement-direct", name="marquer_presence_event_direct")
async def marquer_presence_event_direct(
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
    """Marquer la présence d'un candidat à un événement (mode tablette avec authentification)"""
    # Vérifier que l'événement existe
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
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
    
    # Rediriger vers la page d'émargement principale après validation
    return RedirectResponse(url=f"/events/{event_id}/emargement", status_code=303)

# === ROUTES D'ÉMARGEMENT PAR LIEN (MODE DISTANCE) ===

@router.get("/{event_id}/emargement/liens", name="generer_liens_emargement_event", response_class=HTMLResponse)
async def generer_liens_emargement_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de génération des liens d'émargement pour un événement"""
    # Récupérer l'événement
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer les invitations de l'événement
    invitations = event_service.get_invitations_by_event(event_id, db)
    
    return templates.TemplateResponse("events/generer_liens_emargement.html", {
        "request": request,
        "event": event,
        "invitations": invitations,
        "utilisateur": current_user
    })

@router.post("/{event_id}/emargement/liens/envoyer", name="envoyer_liens_emargement_event")
async def envoyer_liens_emargement_event(
    event_id: int,
    request: Request,
    invitation_ids: List[int] = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer les liens d'émargement par email pour un événement"""
    # Récupérer l'événement
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Récupérer les invitations sélectionnées
    invitations = []
    for invitation_id in invitation_ids:
        invitation = db.get(InvitationEvent, invitation_id)
        if invitation and invitation.event_id == event_id:
            invitations.append(invitation)
    
    # Envoyer les emails avec les liens d'émargement
    sent_count = 0
    for invitation in invitations:
        try:
            # Générer le lien d'émargement
            from app_lia_web.core.config import settings
            base_url = settings.get_base_url_for_email()
            emargement_url = f"{base_url}/events/{event_id}/emargement/lien/{invitation.token_invitation}"
            
            # Préparer l'email
            subject = f"Lien d'émargement - {event.titre}"
            template_data = {
                'nom': f"{invitation.inscription.candidat.prenom} {invitation.inscription.candidat.nom}",
                'event_titre': event.titre,
                'date_event': event.date_debut.strftime('%d/%m/%Y'),
                'lieu': event.lieu or "À définir",
                'emargement_url': emargement_url,
                'base_url': base_url
            }
            
            # Envoyer l'email
            event_service.email_service.send_template_email(
                to_email=invitation.inscription.candidat.email,
                subject=subject,
                template="event_emargement_lien",
                data=template_data
            )
            sent_count += 1
            
        except Exception as e:
            print(f"Erreur envoi email émargement événement: {e}")
    
    return RedirectResponse(url=f"/events/{event_id}/emargement", status_code=303)

@router.get("/{event_id}/emargement/lien/{token}", name="emargement_lien_event", response_class=HTMLResponse)
async def emargement_lien_event(
    event_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """Page d'émargement via lien unique pour un événement"""
    # Vérifier le token et récupérer l'invitation
    invitation = event_service.get_invitation_by_token(token, db)
    if not invitation:
        raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
    
    # Vérifier que l'invitation est pour cet événement
    if invitation.event_id != event_id:
        raise HTTPException(status_code=400, detail="Lien d'émargement incorrect")
    
    # Récupérer l'événement
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Vérifier si déjà présent
    presence = event_service.get_presence_candidat(event_id, invitation.inscription_id, db)
    
    return templates.TemplateResponse("events/emargement_lien.html", {
        "request": request,
        "event": event,
        "invitation": invitation,
        "presence": presence
    })

@router.post("/{event_id}/emargement/lien/{token}", name="signer_emargement_lien_event")
async def signer_emargement_lien_event(
    event_id: int,
    token: str,
    request: Request,
    methode_signature: str = Form("digital"),
    signature_data: str = Form(""),
    nom_signature: str = Form(""),
    photo_data: str = Form(""),
    commentaire: str = Form(""),
    db: Session = Depends(get_session)
):
    """Signer l'émargement via lien pour un événement"""
    # Vérifier le token
    invitation = event_service.get_invitation_by_token(token, db)
    if not invitation:
        raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
    
    # Vérifier que l'invitation est pour cet événement
    if invitation.event_id != event_id:
        raise HTTPException(status_code=400, detail="Lien d'émargement incorrect")
    
    # Préparer les données selon la méthode
    signature_manuelle = None
    signature_digitale = None
    photo_signature = photo_data if photo_data else None
    
    if methode_signature == "manuel":
        signature_manuelle = nom_signature
    elif methode_signature == "digital":
        signature_digitale = signature_data
    
    # Créer la présence
    presence_data = PresenceEventCreate(
        event_id=event_id,
        inscription_id=invitation.inscription_id,
        presence="present",
        methode_signature=methode_signature,
        signature_manuelle=signature_manuelle,
        signature_digitale=signature_digitale,
        photo_signature=photo_signature,
        heure_arrivee=datetime.now(timezone.utc),
        commentaire=commentaire if commentaire else None,
        ip_signature=request.client.host
    )
    
    presence_obj = event_service.mark_presence(presence_data, db)
    
    return templates.TemplateResponse("events/emargement_confirmation.html", {
        "request": request,
        "event": event,
        "presence": presence_obj
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

@router.post("/{event_id}/participant/{inscription_id}/supprimer", name="supprimer_participant_event")
async def supprimer_participant_event(
    event_id: int,
    inscription_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un participant d'un événement"""
    # Vérifier que l'événement existe
    event = event_service.get_event(event_id, db)
    if not event:
        raise HTTPException(status_code=404, detail="Événement non trouvé")
    
    # Supprimer le participant
    success = event_service.remove_participant_from_event(event_id, inscription_id, db)
    
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression du participant")
    
    # Rediriger vers la page d'origine (Referer) ou vers la page de détail par défaut
    referer = request.headers.get("referer")
    if referer and f"/events/{event_id}" in referer:
        return RedirectResponse(url=referer, status_code=303)
    else:
        return RedirectResponse(url=f"/events/{event_id}", status_code=303)