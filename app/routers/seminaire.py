# app/routers/seminaire.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, date, timezone
import os
import uuid

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user
from app_lia_web.app.models.base import User
from app_lia_web.app.models.seminaire import Seminaire, SessionSeminaire, InvitationSeminaire, PresenceSeminaire, LivrableSeminaire, RenduLivrable
from app_lia_web.app.models.enums import StatutSeminaire, TypeInvitation, StatutPresence, MethodeSignature
from app_lia_web.app.schemas.seminaire_schemas import (
    SeminaireCreate, SeminaireUpdate, SessionSeminaireCreate,
    InvitationSeminaireCreate, PresenceSeminaireCreate, LivrableSeminaireCreate,
    SeminaireFilter, PresenceFilter
)
from app_lia_web.app.services.seminaire_service import SeminaireService
from app_lia_web.app.templates import templates

router = APIRouter()
seminaire_service = SeminaireService()

# === ROUTES WEB ===

@router.get("/", name="liste_seminaires", response_class=HTMLResponse)
async def liste_seminaires(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = None
):
    """Page de liste des séminaires"""
    filters = {}
    if programme_id:
        filters['programme_id'] = programme_id
    
    seminaires = seminaire_service.get_seminaires(db, filters)
    stats = seminaire_service.get_seminaire_stats(db)
    programmes = db.exec(select(Programme).where(Programme.actif == True)).all()
    
    return templates.TemplateResponse("seminaires/liste.html", {
        "request": request,
        "seminaires": seminaires,
        "stats": stats,
        "programmes": programmes,
        "current_user": current_user,
        "utilisateur": current_user,
        "programme_id": programme_id
    })

@router.get("/nouveau", name="form_seminaire", response_class=HTMLResponse)
async def nouveau_seminaire_form(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire de création d'un nouveau séminaire"""
    from app_lia_web.app.models.base import Programme
    
    programmes = db.exec(select(Programme)).all()
    return templates.TemplateResponse("seminaires/nouveau.html", {
        "request": request,
        "programmes": programmes,
        "current_user": current_user,
        "utilisateur": current_user
    })

@router.post("/nouveau",name="creer_seminaire")
async def creer_seminaire(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    programme_id: int = Form(...),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    lieu: str = Form(""),
    adresse_complete: str = Form(""),
    capacite_max: int = Form(None),
    invitation_auto: bool = Form(False),
    invitation_promos: bool = Form(False),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Créer un nouveau séminaire"""
    seminaire_data = SeminaireCreate(
        titre=titre,
        description=description,
        programme_id=programme_id,
        date_debut=date_debut,
        date_fin=date_fin,
        lieu=lieu,
        adresse_complete=adresse_complete,
        organisateur_id=current_user.id,
        capacite_max=capacite_max,
        invitation_auto=invitation_auto,
        invitation_promos=invitation_promos
    )
    
    seminaire = seminaire_service.create_seminaire(seminaire_data, db)
    return RedirectResponse(url=f"/seminaires/{seminaire.id}", status_code=303)

@router.get("/{seminaire_id}",name="detail_seminaire", response_class=HTMLResponse)
async def detail_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de détail d'un séminaire"""
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    sessions = seminaire_service.get_sessions_seminaire(seminaire_id, db)
    invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db)
    livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db)
    
    return templates.TemplateResponse("seminaires/detail.html", {
        "request": request,
        "seminaire": seminaire,
        "sessions": sessions,
        "invitations": invitations,
        "livrables": livrables,
        "current_user": current_user,
        "utilisateur": current_user
    })

@router.get("/{seminaire_id}/sessions/nouvelle",name="nouvelle_session_seminaire", response_class=HTMLResponse)
async def nouvelle_session_form(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire de création d'une nouvelle session"""
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    return templates.TemplateResponse("seminaires/session_nouvelle.html", {
        "request": request,
        "seminaire": seminaire,
        "current_user": current_user,
        "utilisateur": current_user
    })

@router.post("/{seminaire_id}/sessions/nouvelle",name="creer_session_seminaire")
async def creer_session(
    seminaire_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    date_session: date = Form(...),
    heure_debut: str = Form(...),  # Changé de datetime à str
    heure_fin: str = Form(None),  # Changé de datetime à str
    lieu: str = Form(""),
    visioconf_url: str = Form(""),
    capacite: int = Form(None),
    obligatoire: bool = Form(True),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Créer une nouvelle session"""
    
    # Combiner la date et l'heure pour créer des datetime
    from datetime import datetime, time
    
    # Parser les heures
    heure_debut_time = datetime.strptime(heure_debut, "%H:%M").time()
    heure_fin_time = datetime.strptime(heure_fin, "%H:%M").time() if heure_fin else None
    
    # Créer les datetime complets
    datetime_debut = datetime.combine(date_session, heure_debut_time)
    datetime_fin = datetime.combine(date_session, heure_fin_time) if heure_fin_time else None
    
    session_data = SessionSeminaireCreate(
        seminaire_id=seminaire_id,
        titre=titre,
        description=description,
        date_session=date_session,
        heure_debut=datetime_debut,  # Utiliser le datetime combiné
        heure_fin=datetime_fin,      # Utiliser le datetime combiné
        lieu=lieu,
        visioconf_url=visioconf_url,
        capacite=capacite,
        obligatoire=obligatoire
    )
    
    session = seminaire_service.create_session(session_data, db)
    return RedirectResponse(url=f"/seminaires/{seminaire_id}", status_code=303)

@router.get("/{seminaire_id}/invitations",name="invitations_seminaire", response_class=HTMLResponse)
async def invitations_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de gestion des invitations"""
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db)
    
    # Récupérer les candidats disponibles pour invitation (exclure ceux déjà invités)
    from app_lia_web.app.models.base import Inscription, Candidat
    from sqlmodel import select
    
    # Récupérer les IDs des inscriptions déjà invitées
    invitations_query = select(InvitationSeminaire.inscription_id).where(
        InvitationSeminaire.seminaire_id == seminaire_id
    )
    inscriptions_invitees = db.exec(invitations_query).all()
    
    # Récupérer toutes les inscriptions du programme sauf celles déjà invitées
    inscriptions_query = select(Inscription).join(Candidat).where(
        Inscription.programme_id == seminaire.programme_id
    )
    
    if inscriptions_invitees:
        inscriptions_query = inscriptions_query.where(
            Inscription.id.notin_(inscriptions_invitees)
        )
    
    inscriptions = db.exec(inscriptions_query).all()
    
    return templates.TemplateResponse("seminaires/invitations.html", {
        "request": request,
        "seminaire": seminaire,
        "invitations": invitations,
        "inscriptions": inscriptions,
        "current_user": current_user,
        "utilisateur": current_user
    })

@router.post("/{seminaire_id}/invitations/envoyer",name="envoyer_invitations_seminaire")
async def envoyer_invitations(
    seminaire_id: int,
    request: Request,
    type_invitation: str = Form(...),
    candidats_ids: List[int] = Form([]),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer des invitations"""
    type_inv = TypeInvitation(type_invitation)
    invitations = seminaire_service.send_invitations_bulk(seminaire_id, type_inv, candidats_ids, db)
    
    return RedirectResponse(url=f"/seminaires/{seminaire_id}/invitations", status_code=303)

@router.get("/{seminaire_id}/sessions/{session_id}/emargement/liens", name="generer_liens_emargement", response_class=HTMLResponse)
async def generer_liens_emargement(
    request: Request,
    seminaire_id: int,
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de génération des liens d'émargement"""
    # Récupérer le séminaire et la session
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    session = seminaire_service.get_session(session_id, db)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    
    # Récupérer les invitations du séminaire
    invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db)
    
    # Debug: afficher les informations
    print(f"DEBUG: {len(invitations)} invitations trouvées pour le séminaire {seminaire_id}")
    for i, inv in enumerate(invitations):
        print(f"  {i+1}. ID: {inv.id}, Candidat: {inv.inscription.candidat.nom if inv.inscription else 'N/A'}")
    
    return templates.TemplateResponse("seminaires/generer_liens_emargement.html", {
        "request": request,
        "seminaire": seminaire,
        "session": session,
        "invitations": invitations
    })

@router.post("/{seminaire_id}/sessions/{session_id}/emargement/liens/envoyer", name="envoyer_liens_emargement")
async def envoyer_liens_emargement(
    seminaire_id: int,
    session_id: int,
    request: Request,
    invitation_ids: List[int] = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer les liens d'émargement par email"""
    # Récupérer les invitations sélectionnées
    invitations = []
    for invitation_id in invitation_ids:
        invitation = seminaire_service.get_invitation(invitation_id, db)
        if invitation:
            invitations.append(invitation)
    
    # Envoyer les emails avec les liens d'émargement
    sent_count = 0
    for invitation in invitations:
        try:
            # Générer le lien d'émargement
            from app_lia_web.core.config import settings
            base_url = settings.get_base_url_for_email()
            emargement_url = f"{base_url}/seminaires/{seminaire_id}/sessions/{session_id}/emargement/lien/{invitation.token_invitation}"
            
            # Préparer l'email
            subject = f"Lien d'émargement - {invitation.seminaire.titre}"
            template_data = {
                'nom': f"{invitation.inscription.candidat.prenom} {invitation.inscription.candidat.nom}",
                'seminaire_titre': invitation.seminaire.titre,
                'session_titre': invitation.seminaire.sessions[0].titre if invitation.seminaire.sessions else "Session",
                'date_session': invitation.seminaire.sessions[0].date_session.strftime('%d/%m/%Y') if invitation.seminaire.sessions else "",
                'emargement_url': emargement_url,
                'base_url': base_url
            }
            
            # Envoyer l'email
            seminaire_service.email_service.send_template_email(
                to_email=invitation.inscription.candidat.email,
                subject=subject,
                template="emargement_lien",
                data=template_data
            )
            sent_count += 1
            
        except Exception as e:
            print(f"Erreur envoi email émargement: {e}")
    
    return RedirectResponse(url=f"/seminaires/{seminaire_id}/sessions/{session_id}/emargement", status_code=303)

@router.get("/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}", name="emargement_lien", response_class=HTMLResponse)
async def emargement_lien(
    request: Request,
    seminaire_id: int,
    session_id: int,
    token: str,
    db: Session = Depends(get_session)
):
    """Page d'émargement via lien unique"""
    # Vérifier le token et récupérer l'invitation
    invitation = seminaire_service.get_invitation_by_token(token, db)
    if not invitation:
        raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
    
    # Vérifier que l'invitation est pour cette session
    if invitation.seminaire_id != seminaire_id:
        raise HTTPException(status_code=400, detail="Lien d'émargement incorrect")
    
    # Récupérer la session
    session = seminaire_service.get_session(session_id, db)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    
    # Vérifier si déjà présent
    presence = seminaire_service.get_presence_candidat(session_id, invitation.inscription_id, db)
    
    return templates.TemplateResponse("seminaires/emargement_lien.html", {
        "request": request,
        "seminaire": invitation.seminaire,
        "session": session,
        "invitation": invitation,
        "presence": presence
    })

@router.post("/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}", name="signer_emargement_lien")
async def signer_emargement_lien(
    seminaire_id: int,
    session_id: int,
    token: str,
    request: Request,
    methode_signature: str = Form("digital"),
    signature_data: str = Form(""),
    nom_signature: str = Form(""),
    photo_data: str = Form(""),
    commentaire: str = Form(""),
    db: Session = Depends(get_session)
):
    """Signer l'émargement via lien"""
    # Vérifier le token
    invitation = seminaire_service.get_invitation_by_token(token, db)
    if not invitation:
        raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
    
    # Préparer les données selon la méthode
    signature_manuelle = None
    signature_digitale = None
    photo_signature = photo_data  # Photo requise pour les deux méthodes
    
    if methode_signature == "manuel":
        signature_manuelle = nom_signature  # Le nom saisi
    elif methode_signature == "digital":
        signature_digitale = signature_data  # L'image de signature
    
    # Créer la présence
    presence_data = PresenceSeminaireCreate(
        session_id=session_id,
        inscription_id=invitation.inscription_id,
        presence="present",  # Texte simple
        heure_arrivee=datetime.now(timezone.utc),
        methode_signature=MethodeSignature(methode_signature),
        signature_manuelle=signature_manuelle,
        signature_digitale=signature_digitale,
        photo_signature=photo_signature,
        commentaire=commentaire,
        ip_signature=request.client.host
    )
    
    presence = seminaire_service.mark_presence(presence_data, db)
    
    # Récupérer la session pour le template
    session_obj = seminaire_service.get_session(session_id, db)
    
    return templates.TemplateResponse("seminaires/emargement_confirmation.html", {
        "request": request,
        "seminaire": invitation.seminaire,
        "session": session_obj,
        "presence": presence,
        "candidat": invitation.inscription.candidat
    })

@router.get("/{seminaire_id}/sessions/{session_id}/emargement",name="emargement_session", response_class=HTMLResponse)
async def emargement_session(
    seminaire_id: int,
    session_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page d'émargement pour une session"""
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    session = db.get(SessionSeminaire, session_id)
    
    if not seminaire or not session:
        raise HTTPException(status_code=404, detail="Séminaire ou session non trouvé")
    
    presences_data = seminaire_service.get_presences_with_invitation_details(seminaire_id, session_id, db)
    stats = seminaire_service.get_presence_stats_with_invitations(seminaire_id, session_id, db)
    
    return templates.TemplateResponse("seminaires/emargement.html", {
        "request": request,
        "seminaire": seminaire,
        "session": session,
        "presences_data": presences_data,
        "stats": stats,
        "current_user": current_user,
        "utilisateur": current_user
    })

@router.post("/{seminaire_id}/sessions/{session_id}/emargement",name="marquer_presence_session")
async def marquer_presence(
    seminaire_id: int,
    session_id: int,
    request: Request,
    inscription_id: int = Form(...),
    presence: str = Form(...),
    methode_signature: str = Form("MANUEL"),
    signature_data: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Marquer la présence d'un participant"""
    presence_data = PresenceSeminaireCreate(
        session_id=session_id,
        inscription_id=inscription_id,
        presence=StatutPresence(presence),
        methode_signature=MethodeSignature(methode_signature),
        signature_manuelle=signature_data if methode_signature == "manuel" else None,
        signature_digitale=signature_data if methode_signature == "digital" else None,
        photo_signature=None,  # Pas de photo pour l'émargement tablette
        note=note
    )
    
    presence_obj = seminaire_service.mark_presence(presence_data, db)
    return RedirectResponse(url=f"/seminaires/{seminaire_id}/sessions/{session_id}/emargement", status_code=303)

@router.get("/{seminaire_id}/livrables",name="livrables_seminaire", response_class=HTMLResponse)
async def livrables_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de gestion des livrables"""
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db)
    
    return templates.TemplateResponse("seminaires/livrables.html", {
        "request": request,
        "seminaire": seminaire,
        "livrables": livrables,
        "current_user": current_user,
        "utilisateur": current_user
    })

@router.post("/{seminaire_id}/livrables/nouveau",name="creer_livrable_seminaire")
async def creer_livrable(
    seminaire_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    type_livrable: str = Form(...),
    obligatoire: bool = Form(True),
    date_limite: datetime = Form(None),
    consignes: str = Form(""),
    format_accepte: str = Form(""),
    taille_max_mb: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Créer un nouveau livrable"""
    # Convertir taille_max_mb en entier ou None
    taille_max_mb_value = None
    if taille_max_mb and taille_max_mb.strip():
        try:
            taille_max_mb_value = int(taille_max_mb)
        except ValueError:
            taille_max_mb_value = None
    
    livrable_data = LivrableSeminaireCreate(
        seminaire_id=seminaire_id,
        titre=titre,
        description=description,
        type_livrable=type_livrable,
        obligatoire=obligatoire,
        date_limite=date_limite,
        consignes=consignes,
        format_accepte=format_accepte,
        taille_max_mb=taille_max_mb_value
    )
    
    livrable = seminaire_service.create_livrable(livrable_data, db)
    return RedirectResponse(url=f"/seminaires/{seminaire_id}/livrables", status_code=303)

@router.get("/{seminaire_id}/livrables/candidat", name="livrables_candidat", response_class=HTMLResponse)
async def livrables_candidat(
    request: Request,
    seminaire_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page des livrables pour un candidat"""
    # Récupérer le séminaire
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    # Récupérer l'inscription du candidat
    inscription = seminaire_service.get_inscription_candidat(seminaire_id, current_user.email, db)
    if not inscription:
        raise HTTPException(status_code=404, detail="Vous n'êtes pas inscrit à ce séminaire")
    
    # Récupérer les livrables du séminaire
    livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db)
    
    # Récupérer les rendus du candidat
    rendus = seminaire_service.get_rendus_candidat(inscription.id, db)
    
    return templates.TemplateResponse("seminaires/livrables_candidat.html", {
        "request": request,
        "seminaire": seminaire,
        "inscription": inscription,
        "livrables": livrables,
        "rendus": rendus
    })

@router.post("/{seminaire_id}/livrables/{livrable_id}/rendre",name="rendre_livrable_seminaire")
async def rendre_livrable(
    seminaire_id: int,
    livrable_id: int,
    request: Request,
    inscription_id: int = Form(...),
    fichier: UploadFile = File(...),
    commentaire: str = Form(""),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Rendre un livrable"""
    # Vérifier le fichier
    if not fichier.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")
    
    # Créer le répertoire de stockage
    upload_dir = f"uploads/seminaires/{seminaire_id}/livrables"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Générer un nom de fichier unique
    file_extension = os.path.splitext(fichier.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Sauvegarder le fichier
    with open(file_path, "wb") as buffer:
        content = await fichier.read()
        buffer.write(content)
    
    # Créer le rendu
    file_data = {
        'nom_fichier': fichier.filename,
        'chemin_fichier': file_path,
        'taille_fichier': len(content),
        'type_mime': fichier.content_type or 'application/octet-stream',
        'commentaire_candidat': commentaire
    }
    
    rendu = seminaire_service.submit_livrable(livrable_id, inscription_id, file_data, db)
    return RedirectResponse(url=f"/seminaires/{seminaire_id}/livrables", status_code=303)

# === ROUTES API ===

@router.get("/api/stats",name="get_seminaire_stats_api")
async def get_seminaire_stats(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Statistiques des séminaires"""
    return seminaire_service.get_seminaire_stats(db)

@router.get("/api/{seminaire_id}/sessions/{session_id}/stats",name="get_session_stats_api")
async def get_session_stats(
    seminaire_id: int,
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """API: Statistiques d'une session"""
    stats = seminaire_service.get_presence_stats(session_id, db)
    return stats

# === ROUTES PUBLIQUES (pour les invitations) ===

@router.get("/{seminaire_id}/sessions/{session_id}/emargement-direct", name="emargement_direct", response_class=HTMLResponse)
async def emargement_direct(
    seminaire_id: int, session_id: int, request: Request,
    db: Session = Depends(get_session)
):
    """Page publique d'émargement direct"""
    seminaire = db.get(Seminaire, seminaire_id)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    session_obj = seminaire_service.get_session(session_id, db)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    
    # Récupérer les présences existantes pour l'émargement direct
    presences = seminaire_service.get_presences_for_direct_emargement(seminaire_id, session_id, db)
    
    # Récupérer toutes les invitations pour afficher tous les candidats
    from app_lia_web.app.models.seminaire import InvitationSeminaire
    from app_lia_web.app.models.base import Inscription
    from sqlmodel import select
    from sqlalchemy.orm import selectinload
    
    invitations_query = select(InvitationSeminaire).options(
        selectinload(InvitationSeminaire.inscription).selectinload(Inscription.candidat)
    ).where(InvitationSeminaire.seminaire_id == seminaire_id)
    invitations = db.exec(invitations_query).all()
    
    return templates.TemplateResponse("seminaires/emargement_direct.html", {
        "request": request, "seminaire": seminaire, "session": session_obj,
        "presences": presences,
        "invitations": invitations
    })

@router.post("/{seminaire_id}/supprimer", name="supprimer_seminaire")
async def supprimer_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un séminaire et toutes ses données associées"""
    try:
        # Vérifier que le séminaire existe
        seminaire = seminaire_service.get_seminaire(seminaire_id, db)
        if not seminaire:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Supprimer le séminaire (cascade supprimera les sessions, invitations, présences, etc.)
        success = seminaire_service.delete_seminaire(seminaire_id, db)
        
        if not success:
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression du séminaire")
        
        return {"message": "Séminaire supprimé avec succès"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/{seminaire_id}/sessions/{session_id}/supprimer", name="supprimer_session")
async def supprimer_session(
    seminaire_id: int,
    session_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer une session et toutes ses données associées"""
    try:
        # Vérifier que le séminaire et la session existent
        seminaire = seminaire_service.get_seminaire(seminaire_id, db)
        session = db.get(SessionSeminaire, session_id)
        
        if not seminaire or not session:
            raise HTTPException(status_code=404, detail="Séminaire ou session non trouvé")
        
        # Supprimer la session (cascade supprimera les présences, livrables, etc.)
        success = seminaire_service.delete_session(session_id, db)
        
        if not success:
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression de la session")
        
        return {"message": "Session supprimée avec succès"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/invitation/{token}",name="invitation_page", response_class=HTMLResponse)
async def invitation_page(
    token: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """Page publique d'invitation"""
    from sqlmodel import select
    
    invitation = db.exec(
        select(InvitationSeminaire).where(InvitationSeminaire.token_invitation == token)
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    seminaire = db.get(Seminaire, invitation.seminaire_id)
    if not seminaire:
        raise HTTPException(status_code=404, detail="Séminaire non trouvé")
    
    return templates.TemplateResponse("seminaires/invitation_public.html", {
        "request": request,
        "invitation": invitation,
        "seminaire": seminaire
    })

@router.get("/invitation/{token}/accepter", name="accepter_invitation", response_class=HTMLResponse)
async def accepter_invitation(
    request: Request,
    token: str,
    db: Session = Depends(get_session)
):
    """Accepter une invitation"""
    invitation = seminaire_service.accept_invitation(token, db)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    # Retourner une page HTML de confirmation
    return templates.TemplateResponse("seminaires/invitation_confirmation.html", {
        "request": request,
        "success": True,
        "message": "Invitation acceptée avec succès !",
        "seminaire": invitation.seminaire,
        "candidat": invitation.inscription.candidat
    })

@router.get("/invitation/{token}/refuser", name="refuser_invitation", response_class=HTMLResponse)
async def refuser_invitation(
    request: Request,
    token: str,
    db: Session = Depends(get_session)
):
    """Refuser une invitation"""
    invitation = seminaire_service.reject_invitation(token, db)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    # Retourner une page HTML de confirmation
    return templates.TemplateResponse("seminaires/invitation_confirmation.html", {
        "request": request,
        "success": False,
        "message": "Invitation refusée",
        "seminaire": invitation.seminaire,
        "candidat": invitation.inscription.candidat
    })

@router.post("/{seminaire_id}/sessions/{session_id}/participant/{inscription_id}/supprimer", name="supprimer_participant_session")
async def supprimer_participant_session(
    seminaire_id: int,
    session_id: int,
    inscription_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un participant d'une session de séminaire"""
    # Vérifier que le séminaire et la session existent
    seminaire = seminaire_service.get_seminaire(seminaire_id, db)
    session = db.get(SessionSeminaire, session_id)
    
    if not seminaire or not session:
        raise HTTPException(status_code=404, detail="Séminaire ou session non trouvé")
    
    # Supprimer le participant
    success = seminaire_service.remove_participant_from_session(seminaire_id, session_id, inscription_id, db)
    
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression du participant")
    
    # Rediriger vers la page d'origine (Referer) ou vers la page d'émargement par défaut
    referer = request.headers.get("referer")
    if referer and f"/seminaires/{seminaire_id}/sessions/{session_id}" in referer:
        return RedirectResponse(url=referer, status_code=303)
    else:
        return RedirectResponse(url=f"/seminaires/{seminaire_id}/sessions/{session_id}/emargement", status_code=303)