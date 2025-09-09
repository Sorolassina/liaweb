from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import os, secrets, string, time
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

from ..core.database import get_session
from ..core.security import get_current_user
from ..models.base import User, RendezVous, Inscription, Candidat, Programme, Entreprise
from ..templates import templates
from ..core.utils import EmailUtils

# ===== Config =====
APP_NAME = os.getenv("APP_NAME", "LIA Coaching • Visioconférence")
GOOGLE_MEET_DOMAIN = os.getenv("GOOGLE_MEET_DOMAIN", "meet.google.com")
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "client")
DEFAULT_DISPLAY_NAME = os.getenv("DEFAULT_DISPLAY_NAME", "Invité")

# ===== Router init =====
router = APIRouter()
#templates = Jinja2Templates(directory="app/templates")

# ===== Utils =====
ALPHABET = string.ascii_lowercase + string.digits
def generate_meet_link() -> str:
    """Génère un lien de visioconférence"""
    import random
    import string
    
    # Utiliser Jitsi Meet qui est plus flexible
    # Générer un nom de salle unique
    chars = string.ascii_lowercase + string.digits
    room_name = ''.join(random.choice(chars) for _ in range(12))
    
    return f"https://meet.jit.si/lia-{room_name}"

def sanitize_name(name: Optional[str]) -> str:
    if not name:
        return DEFAULT_DISPLAY_NAME
    allowed = string.ascii_letters + string.digits + " -_.'’éèêàçÉÈÊÀÇ"
    return "".join(c for c in name if c in allowed)[:48]

# ===== Routes =====
@router.get("/video-rdv/{rdv_id}/commencer", response_class=HTMLResponse)
def commencer_rdv_video(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Commencer un rendez-vous vidéo"""
    
    logger.info(f"🎥 Début commencer_rdv_video - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer le rendez-vous avec toutes les relations
        logger.info(f"🔍 Recherche du RDV {rdv_id}...")
        query = select(RendezVous).where(RendezVous.id == rdv_id)
        rdv = session.exec(query).first()
        
        if not rdv:
            logger.error(f"❌ RDV {rdv_id} non trouvé")
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        logger.info(f"✅ RDV trouvé: {rdv.id}, statut: {rdv.statut}")
        
        # Charger les relations
        logger.info(f"🔍 Chargement de l'inscription {rdv.inscription_id}...")
        inscription = session.get(Inscription, rdv.inscription_id)
        if not inscription:
            logger.error(f"❌ Inscription {rdv.inscription_id} non trouvée")
            raise HTTPException(status_code=404, detail="Inscription non trouvée")
        
        logger.info(f"✅ Inscription trouvée: {inscription.id}")
        
        logger.info(f"🔍 Chargement du candidat {inscription.candidat_id}...")
        candidat = session.get(Candidat, inscription.candidat_id)
        if not candidat:
            logger.error(f"❌ Candidat {inscription.candidat_id} non trouvé")
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        logger.info(f"✅ Candidat trouvé: {candidat.prenom} {candidat.nom}")
        
        logger.info(f"🔍 Chargement du programme {inscription.programme_id}...")
        programme = session.get(Programme, inscription.programme_id)
        if not programme:
            logger.error(f"❌ Programme {inscription.programme_id} non trouvé")
            raise HTTPException(status_code=404, detail="Programme non trouvé")
        
        logger.info(f"✅ Programme trouvé: {programme.nom}")
        
        # Récupérer l'entreprise si elle existe
        logger.info(f"🔍 Recherche de l'entreprise pour candidat {candidat.id}...")
        entreprise_query = select(Entreprise).where(Entreprise.candidat_id == candidat.id)
        entreprise = session.exec(entreprise_query).first()
        
        if entreprise:
            logger.info(f"✅ Entreprise trouvée: {entreprise.raison_sociale}")
        else:
            logger.info("ℹ️ Aucune entreprise trouvée pour ce candidat")
        
        # Vérifier les permissions (seul le conseiller ou admin peut commencer)
        logger.info(f"🔍 Vérification des permissions - User role: {current_user.role}, RDV conseiller: {rdv.conseiller_id}")
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            logger.error(f"❌ Permission refusée pour {current_user.email}")
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de commencer ce rendez-vous")
        
        logger.info("✅ Permissions validées")
        
        # Récupérer le nom du conseiller
        logger.info(f"🔍 Chargement du conseiller {rdv.conseiller_id}...")
        conseiller = session.get(User, rdv.conseiller_id)
        conseiller_nom = conseiller.nom_complet if conseiller else "Conseiller non assigné"
        logger.info(f"✅ Conseiller trouvé: {conseiller_nom}")
        
        # Générer un lien de visioconférence unique (seulement si pas déjà créé)
        if not rdv.meet_link:
            meet_link = generate_meet_link()
            rdv.meet_link = meet_link
            logger.info(f"🎯 Nouveau lien Jitsi généré: {meet_link}")
        else:
            meet_link = rdv.meet_link
            logger.info(f"🔄 Utilisation du lien existant: {meet_link}")
        
        # Mettre à jour le statut du rendez-vous
        logger.info(f"📝 Mise à jour du statut RDV {rdv_id} vers 'en_cours'...")
        rdv.statut = "en_cours"
        session.add(rdv)
        session.commit()
        logger.info("✅ Statut mis à jour avec succès")
        
        # Préparer les données pour la visioconférence
        logger.info("🎬 Préparation du contexte pour le template...")
        ctx = {
            "request": request,
            "rdv": rdv,
            "candidat_prenom": candidat.prenom,
            "candidat_nom": candidat.nom,
            "programme_nom": programme.nom,
            "entreprise_nom": entreprise.raison_sociale if entreprise else None,
            "meet_link": meet_link,  # Lien complet pour partage
            "room_name": meet_link.split('/')[-1],  # Nom de la salle pour Jitsi
            "display_name": current_user.nom_complet,
            "conseiller_nom": conseiller_nom,
            "role": "conseiller",
            "is_host": True,  # Le conseiller est l'hôte
            "google_meet_domain": GOOGLE_MEET_DOMAIN,
            "app_name": APP_NAME,
            "current_user": current_user
        }
        
        logger.info(f"✅ Contexte préparé - Template: video_rdv/google_meet.html")
        logger.info(f"🎉 Commencer RDV vidéo réussi pour {candidat.prenom} {candidat.nom}")
        
        return templates.TemplateResponse("video_rdv/seance_jitsi.html", ctx)
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans commencer_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans commencer_rdv_video: {str(e)}")
        logger.error(f"💥 Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.get("/video-rdv/{rdv_id}/invitation/{token}")
def generer_lien_invitation(
    request: Request,
    rdv_id: int,
    token: str,
    session: Session = Depends(get_session)
):
    """Génère un lien d'invitation pour le candidat (sans authentification)"""
    logger.info(f"🔗 Génération lien invitation - RDV ID: {rdv_id}, Token: {token}")
    
    try:
        # Vérifier le token (simple pour l'instant)
        if token != "candidat":
            raise HTTPException(status_code=403, detail="Token invalide")
        
        query = select(RendezVous).where(RendezVous.id == rdv_id)
        rdv = session.exec(query).first()
        
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        if rdv.statut not in ["planifie", "en_cours"]:
            raise HTTPException(status_code=400, detail="Rendez-vous non disponible")
        
        # Charger les données nécessaires
        inscription = session.get(Inscription, rdv.inscription_id)
        candidat = session.get(Candidat, inscription.candidat_id)
        programme = session.get(Programme, inscription.programme_id)
        entreprise = session.exec(
            select(Entreprise).where(Entreprise.candidat_id == candidat.id)
        ).first()
        
        # Récupérer le nom du conseiller
        conseiller_nom = "Conseiller non assigné"
        if rdv.conseiller_id:
            conseiller = session.get(User, rdv.conseiller_id)
            if conseiller:
                conseiller_nom = conseiller.nom_complet
        
        # Utiliser le lien existant ou en créer un nouveau
        if not rdv.meet_link:
            meet_link = generate_meet_link()
            rdv.meet_link = meet_link
            session.add(rdv)
            session.commit()
        else:
            meet_link = rdv.meet_link
        
        ctx = {
            "request": request,
            "rdv": rdv,
            "candidat_prenom": candidat.prenom,
            "candidat_nom": candidat.nom,
            "programme_nom": programme.nom,
            "entreprise_nom": entreprise.raison_sociale if entreprise else None,
            "meet_link": meet_link,  # Lien complet pour partage
            "room_name": meet_link.split('/')[-1],  # Nom de la salle pour Jitsi
            "display_name": f"{candidat.prenom} {candidat.nom}",
            "conseiller_nom": conseiller_nom,
            "role": "candidat",
            "is_host": False,  # Le candidat n'est jamais hôte
            "google_meet_domain": GOOGLE_MEET_DOMAIN,
            "app_name": APP_NAME,
            "current_user": None  # Pas d'utilisateur connecté
        }
        
        logger.info(f"✅ Lien d'invitation généré pour {candidat.prenom} {candidat.nom}")
        return templates.TemplateResponse("video_rdv/seance_jitsi.html", ctx)
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans generer_lien_invitation: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans generer_lien_invitation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.get("/video-rdv/{rdv_id}/rejoindre", response_class=HTMLResponse)
def rejoindre_rdv_video(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Rejoindre un rendez-vous vidéo en cours"""
    
    # Récupérer le rendez-vous avec toutes les relations
    query = select(RendezVous).where(RendezVous.id == rdv_id)
    rdv = session.exec(query).first()
    
    if not rdv:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    # Charger les relations
    inscription = session.get(Inscription, rdv.inscription_id)
    if not inscription:
        raise HTTPException(status_code=404, detail="Inscription non trouvée")
    
    candidat = session.get(Candidat, inscription.candidat_id)
    programme = session.get(Programme, inscription.programme_id)
    
    # Récupérer l'entreprise si elle existe
    entreprise_query = select(Entreprise).where(Entreprise.candidat_id == candidat.id)
    entreprise = session.exec(entreprise_query).first()
    
    # Récupérer le nom du conseiller
    conseiller_nom = "Conseiller non assigné"
    if rdv.conseiller_id:
        conseiller = session.get(User, rdv.conseiller_id)
        if conseiller:
            conseiller_nom = conseiller.nom_complet
    
    # Vérifier que le RDV est en cours
    if rdv.statut != "en_cours":
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est pas en cours")
    
    # Utiliser le lien existant ou en créer un nouveau
    if not rdv.meet_link:
        meet_link = generate_meet_link()
        rdv.meet_link = meet_link
        session.add(rdv)
        session.commit()
    else:
        meet_link = rdv.meet_link
    
    # Déterminer le rôle de l'utilisateur
    if rdv.conseiller_id == current_user.id:
        role = "conseiller"
    else:
        role = "candidat"
    
    ctx = {
        "request": request,
        "rdv": rdv,
        "candidat_prenom": candidat.prenom,
        "candidat_nom": candidat.nom,
        "programme_nom": programme.nom,
        "entreprise_nom": entreprise.raison_sociale if entreprise else None,
        "meet_link": meet_link,
        "display_name": current_user.nom_complet,
        "conseiller_nom": conseiller_nom,
        "role": role,
        "is_host": (role == "conseiller"),  # Seul le conseiller est hôte
        "google_meet_domain": GOOGLE_MEET_DOMAIN,
        "app_name": APP_NAME,
        "current_user": current_user
    }
    
    return templates.TemplateResponse("video_rdv/seance_jitsi.html", ctx)

@router.post("/video-rdv/{rdv_id}/terminer")
def terminer_rdv_video(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Terminer un rendez-vous vidéo"""
    
    # Récupérer le rendez-vous
    rdv = session.get(RendezVous, rdv_id)
    if not rdv:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    # Vérifier les permissions
    if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de terminer ce rendez-vous")
    
    # Mettre à jour le statut
    rdv.statut = "termine"
    session.add(rdv)
    session.commit()
    
    return {"message": "Rendez-vous terminé avec succès", "status": "success"}

@router.get("/video-rdv/{rdv_id}/notes")
def recuperer_notes(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupérer les notes d'un rendez-vous"""
    logger.info(f"📖 Récupération notes - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de voir ce rendez-vous")
        
        logger.info(f"✅ Notes récupérées pour RDV {rdv_id}")
        return {
            "status": "success", 
            "notes": rdv.notes or "",
            "rdv_id": rdv_id,
            "statut": rdv.statut,
            "date_rdv": rdv.debut.strftime("%d/%m/%Y à %H:%M") if rdv.debut else "Non définie"
        }
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans recuperer_notes: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans recuperer_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.post("/video-rdv/{rdv_id}/notes")
def sauvegarder_notes(
    rdv_id: int,
    notes_data: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Sauvegarder les notes d'un rendez-vous"""
    logger.info(f"📝 Sauvegarde notes - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de modifier ce rendez-vous")
        
        # Mettre à jour les notes
        notes_content = notes_data.get("notes", "")
        rdv.notes = notes_content
        
        session.add(rdv)
        session.commit()
        
        logger.info(f"✅ Notes sauvegardées pour RDV {rdv_id}")
        return {"status": "success", "message": "Notes sauvegardées avec succès"}
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans sauvegarder_notes: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans sauvegarder_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.get("/video-rdv/{rdv_id}/notes")
def recuperer_notes(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupérer les notes d'un rendez-vous"""
    logger.info(f"📖 Récupération notes - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de consulter ce rendez-vous")
        
        logger.info(f"✅ Notes récupérées pour RDV {rdv_id}")
        return {"status": "success", "notes": rdv.notes or ""}
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans recuperer_notes: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans recuperer_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.post("/video-rdv/{rdv_id}/envoyer-invitation")
def envoyer_invitation_email(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer l'invitation par email au candidat"""
    logger.info(f"📧 Envoi invitation email - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer le rendez-vous avec toutes les relations
        query = select(RendezVous).where(RendezVous.id == rdv_id)
        rdv = session.exec(query).first()
        
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation d'envoyer des invitations pour ce rendez-vous")
        
        # Charger les données nécessaires
        inscription = session.get(Inscription, rdv.inscription_id)
        candidat = session.get(Candidat, inscription.candidat_id)
        programme = session.get(Programme, inscription.programme_id)
        
        # Récupérer le nom du conseiller
        conseiller_nom = "Conseiller non assigné"
        if rdv.conseiller_id:
            conseiller = session.get(User, rdv.conseiller_id)
            if conseiller:
                conseiller_nom = conseiller.nom_complet
        
        if not candidat.email:
            raise HTTPException(status_code=400, detail="Aucune adresse email trouvée pour ce candidat")
        
        # Formater la date
        rdv_date = rdv.debut.strftime('%d/%m/%Y à %H:%M')
        
        # Envoyer l'email
        success = EmailUtils.send_rdv_invitation(
            to_email=candidat.email,
            candidat_nom=candidat.nom,
            candidat_prenom=candidat.prenom,
            rdv_id=rdv_id,
            rdv_date=rdv_date,
            rdv_type=rdv.type_rdv.title(),
            programme_nom=programme.nom,
            conseiller_nom=conseiller_nom
        )
        
        if success:
            logger.info(f"✅ Invitation email envoyée à {candidat.email} pour RDV {rdv_id}")
            return {"status": "success", "message": f"Invitation envoyée à {candidat.email}"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de l'email")
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans envoyer_invitation_email: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans envoyer_invitation_email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/terminer")
def terminer_rdv(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Terminer un rendez-vous et mettre à jour le statut"""
    try:
        logger.info(f"🔄 Tentative de finalisation du RDV {rdv_id} par {current_user.nom_complet}")
        
        # Récupérer le rendez-vous
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            logger.error(f"❌ RDV {rdv_id} non trouvé")
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role != UserRole.ADMIN and current_user.id != rdv.conseiller_id:
            logger.error(f"❌ Permission refusée pour {current_user.nom_complet} sur RDV {rdv_id}")
            raise HTTPException(status_code=403, detail="Permission refusée")
        
        # Mettre à jour le statut
        rdv.statut = "termine"
        rdv.fin = datetime.now()
        
        session.add(rdv)
        session.commit()
        
        logger.info(f"✅ RDV {rdv_id} terminé avec succès par {current_user.nom_complet}")
        return {"status": "success", "message": "Rendez-vous terminé avec succès"}
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans terminer_rdv: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans terminer_rdv: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")



