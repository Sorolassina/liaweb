# app/routers/emargement_router.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import logging
from datetime import datetime, timezone
import json

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user, get_current_user_optional
from app_lia_web.app.models.base import User, RendezVous, EmargementRDV, Candidat, Inscription
from app_lia_web.core.config import settings
from app_lia_web.core.utils import EmailUtils

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/emargement/{rdv_id}")
async def page_emargement_conseiller(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page d'émargement pour le conseiller"""
    logger.info(f"📝 Page émargement conseiller - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer le RDV avec toutes les relations
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Charger les relations
        inscription = session.get(Inscription, rdv.inscription_id)
        if not inscription:
            raise HTTPException(status_code=404, detail="Inscription non trouvée")
        
        candidat = session.get(Candidat, inscription.candidat_id)
        if not candidat:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de voir ce rendez-vous")
        
        # Récupérer l'émargement existant
        emargement_query = select(EmargementRDV).where(EmargementRDV.rdv_id == rdv_id)
        emargement = session.exec(emargement_query).first()
        
        # Si pas d'émargement, en créer un
        if not emargement:
            emargement = EmargementRDV(
                rdv_id=rdv_id,
                type_signataire="conseiller",
                signataire_id=current_user.id,
                candidat_id=candidat.id
            )
            session.add(emargement)
            session.commit()
            session.refresh(emargement)
        
        logger.info(f"✅ Page émargement chargée pour RDV {rdv_id}")
        
        return templates.TemplateResponse("emargement/conseiller.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "emargement": emargement,
            "utilisateur": current_user,
            "settings": settings
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans page_emargement_conseiller: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans page_emargement_conseiller: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.get("/emargement/{rdv_id}/candidat/{token}")
async def page_emargement_candidat(
    request: Request,
    rdv_id: int,
    token: str,
    session: Session = Depends(get_session)
):
    """Page d'émargement pour le candidat (via token)"""
    logger.info(f"📝 Page émargement candidat - RDV ID: {rdv_id}, Token: {token[:10]}...")
    
    try:
        # Récupérer le RDV avec toutes les relations
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Charger les relations
        inscription = session.get(Inscription, rdv.inscription_id)
        if not inscription:
            raise HTTPException(status_code=404, detail="Inscription non trouvée")
        
        candidat = session.get(Candidat, inscription.candidat_id)
        if not candidat:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # TODO: Valider le token (pour l'instant on accepte tout)
        # En production, il faudrait vérifier que le token est valide et non expiré
        
        # Récupérer l'émargement existant
        emargement_query = select(EmargementRDV).where(EmargementRDV.rdv_id == rdv_id)
        emargement = session.exec(emargement_query).first()
        
        # Si pas d'émargement, en créer un
        if not emargement:
            emargement = EmargementRDV(
                rdv_id=rdv_id,
                type_signataire="candidat",
                candidat_id=candidat.id
            )
            session.add(emargement)
            session.commit()
            session.refresh(emargement)
        
        logger.info(f"✅ Page émargement candidat chargée pour RDV {rdv_id}")
        
        # Créer un utilisateur fictif pour le template (candidat non connecté)
        utilisateur_fictif = type('User', (), {
            'id': candidat.id,
            'email': candidat.email,
            'nom_complet': f"{candidat.prenom} {candidat.nom}",
            'role': 'candidat'
        })()
        
        return templates.TemplateResponse("emargement/candidat.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "emargement": emargement,
            "token": token,
            "utilisateur": utilisateur_fictif,
            "settings": settings
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans page_emargement_candidat: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans page_emargement_candidat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.post("/emargement/{rdv_id}/signer")
async def signer_emargement_conseiller(
    request: Request,
    rdv_id: int,
    signature_data: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Enregistrer la signature d'émargement du conseiller"""
    logger.info(f"✍️ Signature émargement conseiller - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer l'émargement
        emargement_query = select(EmargementRDV).where(EmargementRDV.rdv_id == rdv_id)
        emargement = session.exec(emargement_query).first()
        
        if not emargement:
            raise HTTPException(status_code=404, detail="Émargement non trouvé")
        
        signature_content = signature_data.get("signature")  # Base64 de la signature
        
        if not signature_content:
            raise HTTPException(status_code=400, detail="Signature manquante")
        
        # Enregistrer la signature du conseiller
        emargement.signature_conseiller = signature_content
        emargement.date_signature_conseiller = datetime.now(timezone.utc)
        emargement.signataire_id = current_user.id
        
        # Enregistrer les informations de traçabilité
        emargement.ip_address = request.client.host if request.client else None
        emargement.user_agent = request.headers.get("user-agent")
        
        session.add(emargement)
        session.commit()
        
        logger.info(f"✅ Signature conseiller enregistrée pour RDV {rdv_id}")
        
        return {
            "status": "success",
            "message": "Signature conseiller enregistrée avec succès",
            "date_signature": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans signer_emargement_conseiller: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans signer_emargement_conseiller: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.post("/emargement/{rdv_id}/candidat/signer")
async def signer_emargement_candidat(
    request: Request,
    rdv_id: int,
    signature_data: dict,
    session: Session = Depends(get_session)
):
    """Enregistrer la signature d'émargement du candidat (sans authentification)"""
    logger.info(f"✍️ Signature émargement candidat - RDV ID: {rdv_id}")
    
    try:
        # Récupérer l'émargement
        emargement_query = select(EmargementRDV).where(EmargementRDV.rdv_id == rdv_id)
        emargement = session.exec(emargement_query).first()
        
        if not emargement:
            raise HTTPException(status_code=404, detail="Émargement non trouvé")
        
        signature_content = signature_data.get("signature")  # Base64 de la signature
        
        if not signature_content:
            raise HTTPException(status_code=400, detail="Signature manquante")
        
        # Pour le candidat, récupérer le candidat via le RDV
        rdv_query = select(RendezVous).where(RendezVous.id == rdv_id)
        rdv = session.exec(rdv_query).first()
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Récupérer le candidat via l'inscription
        inscription_query = select(Inscription).where(Inscription.id == rdv.inscription_id)
        inscription = session.exec(inscription_query).first()
        if not inscription:
            raise HTTPException(status_code=404, detail="Inscription non trouvée")
        
        emargement.signature_candidat = signature_content
        emargement.date_signature_candidat = datetime.now(timezone.utc)
        emargement.candidat_id = inscription.candidat_id
        
        # Enregistrer les informations de traçabilité
        emargement.ip_address = request.client.host if request.client else None
        emargement.user_agent = request.headers.get("user-agent")
        
        session.add(emargement)
        session.commit()
        
        logger.info(f"✅ Signature candidat enregistrée pour RDV {rdv_id}")
        
        return {
            "status": "success",
            "message": "Signature candidat enregistrée avec succès",
            "date_signature": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans signer_emargement_candidat: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans signer_emargement_candidat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.get("/emargement/{rdv_id}/statut")
async def get_statut_emargement(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupérer le statut de l'émargement d'un RDV"""
    logger.info(f"📊 Statut émargement - RDV ID: {rdv_id}")
    
    try:
        # Récupérer l'émargement
        emargement_query = select(EmargementRDV).where(EmargementRDV.rdv_id == rdv_id)
        emargement = session.exec(emargement_query).first()
        
        if not emargement:
            return {
                "status": "not_found",
                "conseiller_signe": False,
                "candidat_signe": False,
                "peut_commencer": False
            }
        
        conseiller_signe = bool(emargement.signature_conseiller and emargement.date_signature_conseiller)
        candidat_signe = bool(emargement.signature_candidat and emargement.date_signature_candidat)
        peut_commencer = conseiller_signe and candidat_signe
        
        return {
            "status": "found",
            "conseiller_signe": conseiller_signe,
            "candidat_signe": candidat_signe,
            "peut_commencer": peut_commencer,
            "date_signature_conseiller": emargement.date_signature_conseiller.isoformat() if emargement.date_signature_conseiller else None,
            "date_signature_candidat": emargement.date_signature_candidat.isoformat() if emargement.date_signature_candidat else None
        }
        
    except Exception as e:
        logger.error(f"💥 Erreur dans get_statut_emargement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@router.post("/emargement/{rdv_id}/envoyer-lien-candidat")
async def envoyer_lien_emargement_candidat(
    rdv_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer le lien d'émargement au candidat par email"""
    logger.info(f"📧 Envoi lien émargement candidat - RDV ID: {rdv_id}")
    
    try:
        # Récupérer le RDV avec toutes les relations
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Charger les relations
        inscription = session.get(Inscription, rdv.inscription_id)
        if not inscription:
            raise HTTPException(status_code=404, detail="Inscription non trouvée")
        
        candidat = session.get(Candidat, inscription.candidat_id)
        if not candidat:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation")
        
        # Générer un token simple (en production, utiliser un token sécurisé)
        token = f"emargement_{rdv_id}_{candidat.id}"
        lien_emargement = f"/emargement/{rdv_id}/candidat/{token}"
        
        # Envoyer l'email
        success = EmailUtils.send_emargement_invitation(
            to_email=candidat.email,
            candidat_nom=candidat.nom,
            candidat_prenom=candidat.prenom,
            rdv_id=rdv_id,
            rdv_date=rdv.debut.strftime("%d/%m/%Y à %H:%M") if rdv.debut else "Non définie",
            rdv_type=rdv.type_rdv,
            lien_emargement=lien_emargement
        )
        
        if success:
            logger.info(f"✅ Email émargement envoyé à {candidat.email}")
            return {
                "status": "success",
                "message": "Lien d'émargement envoyé au candidat par email"
            }
        else:
            logger.error(f"❌ Échec envoi email émargement à {candidat.email}")
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de l'email")
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans envoyer_lien_emargement_candidat: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans envoyer_lien_emargement_candidat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")
