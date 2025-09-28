# app/routers/rendez_vous.py
from datetime import datetime, date, timezone
from typing import Optional, List
import logging
import os, secrets, string, time
import json
from fastapi import APIRouter, Depends, Request, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from app_lia_web.core.database import get_session
from app_lia_web.core.middleware import get_shared_session
from app_lia_web.core.security import get_current_user, get_current_user_optional
from app_lia_web.core.program_schema_integration import table_exists_anywhere
from app_lia_web.core.config import settings
from app_lia_web.core.utils import EmailUtils
from app_lia_web.app.models.base import User, Programme, Candidat, Entreprise
from app_lia_web.app.models.inscription import Inscription
from app_lia_web.app.models.rendez_vous import RendezVous, EmargementRDV
from app_lia_web.app.models.enums import TypeRDV, StatutRDV, UserRole
from app_lia_web.app.schemas.rendez_vous_schemas import RendezVousCreate, RendezVousUpdate, RendezVousFilter
from app_lia_web.app.services.rendez_vous_service import RendezVousService
from app_lia_web.app.templates import templates

# Configuration vidéo
APP_NAME = os.getenv("APP_NAME", "LIA Coaching • Visioconférence")
GOOGLE_MEET_DOMAIN = os.getenv("GOOGLE_MEET_DOMAIN", "meet.google.com")
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "client")
DEFAULT_DISPLAY_NAME = os.getenv("DEFAULT_DISPLAY_NAME", "Invité")

# Utils vidéo
ALPHABET = string.ascii_lowercase + string.digits

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/rendez-vous", name="rendez_vous_list", response_class=HTMLResponse)
def rendez_vous_list(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = Query(None),
    conseiller_id: Optional[int] = Query(None),
    type_rdv: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    date_debut: Optional[str] = Query(None),
    date_fin: Optional[str] = Query(None),
    candidat_nom: Optional[str] = Query(None),
    entreprise_nom: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Page de liste des rendez-vous"""
    
    # Récupération des programmes pour le filtre
    programmes = session.exec(select(Programme)).all()
    
    # Récupération des conseillers pour le filtre
    conseillers = session.exec(
        select(User).where(User.role.in_([UserRole.CONSEILLER, UserRole.COORDINATEUR]))
    ).all()
    
    # Construction des filtres
    filters = RendezVousFilter(
        programme_id=programme_id,
        conseiller_id=conseiller_id,
        type_rdv=TypeRDV(type_rdv) if type_rdv else None,
        statut=StatutRDV(statut) if statut else None,
        date_debut=datetime.fromisoformat(date_debut) if date_debut else None,
        date_fin=datetime.fromisoformat(date_fin) if date_fin else None,
        candidat_nom=candidat_nom,
        entreprise_nom=entreprise_nom
    )
    
    # Récupération des rendez-vous
    service = RendezVousService(session)
    offset = (page - 1) * limit
    
    try:
        rendez_vous = service.search_rendez_vous(filters, limit=limit, offset=offset)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la recherche des rendez-vous: {e}")
        rendez_vous = []
    
    # Statistiques
    try:
        stats = service.get_statistiques_rendez_vous(programme_id)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des statistiques rendez-vous: {e}")
        stats = {"total": 0, "a_venir": 0, "termines": 0, "annules": 0}
    
    return templates.TemplateResponse("rendez_vous/liste.html", {
        "request": request,
        "current_user": current_user,
        "utilisateur": current_user,
        "rendez_vous": rendez_vous,
        "programmes": programmes,
        "conseillers": conseillers,
        "filters": {
            "programme_id": programme_id,
            "conseiller_id": conseiller_id,
            "type_rdv": type_rdv,
            "statut": statut,
            "date_debut": date_debut,
            "date_fin": date_fin,
            "candidat_nom": candidat_nom,
            "entreprise_nom": entreprise_nom
        },
        "stats": stats,
        "page": page,
        "limit": limit,
        "has_next": len(rendez_vous) == limit,
        "has_prev": page > 1
    })

@router.get("/rendez-vous/creer", response_class=HTMLResponse, name="rendez_vous_create_form")
def rendez_vous_create_form(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    inscription_id: Optional[int] = Query(None)
):
    """Formulaire de création d'un rendez-vous"""
    
    # Récupération des programmes et conseillers
    programmes = session.exec(select(Programme)).all()
    conseillers = session.exec(
        select(User).where(User.role.in_([UserRole.CONSEILLER, UserRole.COORDINATEUR]))
    ).all()
    
    # Récupération des candidats validés avec leurs inscriptions
    candidats_query = (
        select(
            Inscription.id.label("inscription_id"),
            Candidat.id.label("candidat_id"),
            Candidat.nom,
            Candidat.prenom,
            Candidat.email,
            Programme.nom.label("programme_nom"),
            Programme.id.label("programme_id"),
            Entreprise.raison_sociale.label("entreprise_nom")
        )
        .join(Candidat, Inscription.candidat_id == Candidat.id)
        .join(Programme, Inscription.programme_id == Programme.id)
        .outerjoin(Entreprise, Candidat.id == Entreprise.candidat_id)
        .where(Inscription.statut == "VALIDE")
        .order_by(Candidat.nom, Candidat.prenom)
    )
    
    print(f"🔍 DEBUG - Requête SQL candidats: {candidats_query}")
    
    # Vérifier les inscriptions dans la base - Version sécurisée
    all_inscriptions = []
    if table_exists_anywhere("inscription", session):
        try:
            all_inscriptions = session.exec(select(Inscription)).all()
            print(f"🔍 DEBUG - Total inscriptions: {len(all_inscriptions)}")
            for inscription in all_inscriptions:
                print(f"  Inscription {inscription.id}: statut={inscription.statut}, candidat_id={inscription.candidat_id}, programme_id={inscription.programme_id}")
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des inscriptions: {e}")
            all_inscriptions = []
            print(f"🔍 DEBUG - Aucune inscription trouvée (table inexistante)")
    else:
        print(f"🔍 DEBUG - Table inscription n'existe pas")
    
    # Vérifier les statuts possibles
    from app_lia_web.app.models.enums import StatutDossier
    print(f"🔍 DEBUG - Statuts possibles: {[s.value for s in StatutDossier]}")
    
    # Mettre à jour quelques inscriptions en VALIDE pour test
    inscriptions_to_update = session.exec(select(Inscription).limit(2)).all()
    for inscription in inscriptions_to_update:
        inscription.statut = "VALIDE"
        session.add(inscription)
    session.commit()
    print(f"🔍 DEBUG - Mis à jour {len(inscriptions_to_update)} inscriptions en VALIDE")
    
    candidats_results = session.exec(candidats_query).all()
    
    print(f"🔍 DEBUG - Nombre de résultats candidats: {len(candidats_results)}")
    for i, result in enumerate(candidats_results):
        print(f"  Candidat {i+1}: {result.prenom} {result.nom} - {result.programme_nom} - Entreprise: {result.entreprise_nom}")
    
    candidats = []
    for result in candidats_results:
        candidats.append({
            "inscription_id": result.inscription_id,
            "candidat_id": result.candidat_id,
            "nom_complet": f"{result.prenom} {result.nom}",
            "email": result.email,
            "programme_nom": result.programme_nom,
            "programme_id": result.programme_id,
            "entreprise_nom": result.entreprise_nom or "Non renseignée"
        })
    
    print(f"🔍 DEBUG - Nombre de candidats final: {len(candidats)}")
    
    # Si une inscription est spécifiée, récupérer les détails
    inscription = None
    candidat = None
    if inscription_id:
        inscription = session.get(Inscription, inscription_id)
        if inscription:
            candidat = session.get(Candidat, inscription.candidat_id)
    
    return templates.TemplateResponse("rendez_vous/creer.html", {
        "request": request,
        "current_user": current_user,
        "utilisateur": current_user,
        "programmes": programmes,
        "conseillers": conseillers,
        "candidats": candidats,
        "inscription": inscription,
        "candidat": candidat,
        "types_rdv": [t.value for t in TypeRDV],
        "statuts_rdv": [s.value for s in StatutRDV]
    })

@router.post("/rendez-vous/creer", name="rendez_vous_create")
def rendez_vous_create(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    inscription_id: int = Form(...),
    conseiller_id: Optional[int] = Form(None),
    type_rdv: str = Form(...),
    statut: str = Form(...),
    debut: str = Form(...),
    fin: Optional[str] = Form(None),
    lieu: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """Créer un nouveau rendez-vous"""
    
    try:
        # Validation des données
        rdv_data = RendezVousCreate(
            inscription_id=inscription_id,
            conseiller_id=conseiller_id,
            type_rdv=TypeRDV(type_rdv),
            statut=StatutRDV(statut),
            debut=datetime.fromisoformat(debut),
            fin=datetime.fromisoformat(fin) if fin else None,
            lieu=lieu,
            notes=notes
        )
        
        service = RendezVousService(session)
        rdv = service.create_rendez_vous(rdv_data)
        
        return RedirectResponse(url=request.url_for("rendez_vous_list"), status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création du rendez-vous: {str(e)}")

@router.get("/rendez-vous/{rdv_id}", response_class=HTMLResponse, name="rendez_vous_detail")
def rendez_vous_detail(
    rdv_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Détail d'un rendez-vous"""
    
    service = RendezVousService(session)
    rdv_details = service.get_rendez_vous_with_details(rdv_id)
    
    if not rdv_details:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    # Récupération des conseillers pour l'édition
    conseillers = session.exec(
        select(User).where(User.role.in_([UserRole.CONSEILLER, UserRole.COORDINATEUR]))
    ).all()
    
    return templates.TemplateResponse("rendez_vous/detail.html", {
        "request": request,
        "current_user": current_user,
        "utilisateur": current_user,
        "rdv": rdv_details,
        "conseillers": conseillers,
        "types_rdv": [t.value for t in TypeRDV],
        "statuts_rdv": [s.value for s in StatutRDV]
    })

@router.post("/rendez-vous/{rdv_id}/modifier", name="rendez_vous_update")
def rendez_vous_update(
    rdv_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    conseiller_id: Optional[int] = Form(None),
    type_rdv: str = Form(...),
    statut: str = Form(...),
    debut: str = Form(...),
    fin: Optional[str] = Form(None),
    lieu: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """Modifier un rendez-vous"""
    
    try:
        rdv_data = RendezVousUpdate(
            conseiller_id=conseiller_id,
            type_rdv=TypeRDV(type_rdv),
            statut=StatutRDV(statut),
            debut=datetime.fromisoformat(debut),
            fin=datetime.fromisoformat(fin) if fin else None,
            lieu=lieu,
            notes=notes
        )
        
        service = RendezVousService(session)
        rdv = service.update_rendez_vous(rdv_id, rdv_data)
        
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        return RedirectResponse(url=request.url_for("rendez_vous_detail", rdv_id=rdv_id), status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la modification du rendez-vous: {str(e)}")

@router.post("/rendez-vous/{rdv_id}/supprimer", name="rendez_vous_delete")
def rendez_vous_delete(
    rdv_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un rendez-vous"""
    
    service = RendezVousService(session)
    success = service.delete_rendez_vous(rdv_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    return RedirectResponse(url=request.url_for("rendez_vous_list"), status_code=303)

@router.get("/rendez-vous/api/search", name="rendez_vous_api_search")
def rendez_vous_api_search(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = Query(None),
    conseiller_id: Optional[int] = Query(None),
    type_rdv: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    date_debut: Optional[str] = Query(None),
    date_fin: Optional[str] = Query(None),
    candidat_nom: Optional[str] = Query(None),
    entreprise_nom: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """API pour la recherche de rendez-vous"""
    
    filters = RendezVousFilter(
        programme_id=programme_id,
        conseiller_id=conseiller_id,
        type_rdv=TypeRDV(type_rdv) if type_rdv else None,
        statut=StatutRDV(statut) if statut else None,
        date_debut=datetime.fromisoformat(date_debut) if date_debut else None,
        date_fin=datetime.fromisoformat(date_fin) if date_fin else None,
        candidat_nom=candidat_nom,
        entreprise_nom=entreprise_nom
    )
    
    service = RendezVousService(session)
    rendez_vous = service.search_rendez_vous(filters, limit=limit)
    
    return {"rendez_vous": rendez_vous}

@router.get("/rendez-vous/api/statistiques", name="rendez_vous_api_stats")
def rendez_vous_api_stats(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = Query(None),
    date_debut: Optional[str] = Query(None),
    date_fin: Optional[str] = Query(None)
):
    """API pour les statistiques des rendez-vous"""
    
    service = RendezVousService(session)
    stats = service.get_statistiques_rendez_vous(
        programme_id=programme_id,
        date_debut=date.fromisoformat(date_debut) if date_debut else None,
        date_fin=date.fromisoformat(date_fin) if date_fin else None
    )
    
    return stats

@router.get("/emargement/{rdv_id}", name="emargement_rdv")
async def page_emargement_conseiller(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
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


# ============================================================================
# ROUTES ÉMARGEMENT (fusionnées depuis emargement_router.py)
# ============================================================================

@router.get("/emargement/{rdv_id}/candidat/{token}", name="page_emargement_candidat")
async def page_emargement_candidat(
    request: Request,
    rdv_id: int,
    token: str,
    session: Session = Depends(get_shared_session)
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


@router.post("/emargement/{rdv_id}/signer", name="signer_emargement_conseiller")
async def signer_emargement_conseiller(
    request: Request,
    rdv_id: int,
    signature_data: dict,
    session: Session = Depends(get_shared_session),
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


@router.post("/emargement/{rdv_id}/candidat/signer", name="signer_emargement_candidat")
async def signer_emargement_candidat(
    request: Request,
    rdv_id: int,
    signature_data: dict,
    session: Session = Depends(get_shared_session)
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


@router.get("/emargement/{rdv_id}/statut", name="get_statut_emargement")
async def get_statut_emargement(
    rdv_id: int,
    session: Session = Depends(get_shared_session),
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


@router.post("/emargement/{rdv_id}/envoyer-lien-candidat", name="envoyer_lien_emargement_candidat")
async def envoyer_lien_emargement_candidat(
    rdv_id: int,
    session: Session = Depends(get_shared_session),
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


# ============================================================================
# ROUTES VIDÉO (fusionnées depuis video_router.py)
# ============================================================================

def generate_meet_link():
    """Génère un lien Google Meet unique"""
    return f"https://{GOOGLE_MEET_DOMAIN}/" + ''.join(secrets.choice(ALPHABET) for _ in range(10))

@router.get("/video-rdv/{rdv_id}/commencer", response_class=HTMLResponse, name="video_rdv_start")
def commencer_rdv_video(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Page pour commencer un RDV vidéo"""
    logger.info(f"🎥 Début RDV vidéo - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer le RDV
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation")
        
        # Charger les relations
        inscription = session.get(Inscription, rdv.inscription_id)
        if not inscription:
            raise HTTPException(status_code=404, detail="Inscription non trouvée")
        
        candidat = session.get(Candidat, inscription.candidat_id)
        if not candidat:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Générer ou récupérer le lien Meet
        if not rdv.meet_link:
            rdv.meet_link = generate_meet_link()
            session.add(rdv)
            session.commit()
        
        logger.info(f"✅ Page RDV vidéo chargée pour RDV {rdv_id}")
        
        return templates.TemplateResponse("video/rdv_start.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "utilisateur": current_user,
            "app_name": APP_NAME,
            "meet_link": rdv.meet_link,
            "settings": settings
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans commencer_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans commencer_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/video-rdv/{rdv_id}/rejoindre", response_class=HTMLResponse, name="video_rdv_join")
def rejoindre_rdv_video(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Page pour rejoindre un RDV vidéo"""
    logger.info(f"🎥 Rejoindre RDV vidéo - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer le RDV
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
        
        # Vérifier que le RDV a un lien Meet
        if not rdv.meet_link:
            raise HTTPException(status_code=400, detail="Aucun lien de visioconférence configuré")
        
        logger.info(f"✅ Page rejoindre RDV vidéo chargée pour RDV {rdv_id}")
        
        return templates.TemplateResponse("video/rdv_join.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "utilisateur": current_user,
            "app_name": APP_NAME,
            "meet_link": rdv.meet_link,
            "settings": settings
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans rejoindre_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans rejoindre_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/terminer", name="terminer_rdv_video")
def terminer_rdv_video(
    rdv_id: int,
    notes: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Terminer un RDV vidéo"""
    logger.info(f"🏁 Fin RDV vidéo - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer le RDV
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation")
        
        # Mettre à jour le statut
        rdv.statut = StatutRDV.TERMINE
        rdv.fin = datetime.now(timezone.utc)
        if notes:
            rdv.notes = notes
        
        session.add(rdv)
        session.commit()
        
        logger.info(f"✅ RDV vidéo terminé pour RDV {rdv_id}")
        
        return {
            "status": "success",
            "message": "Rendez-vous vidéo terminé avec succès"
        }
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans terminer_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans terminer_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/video-rdv/{rdv_id}/notes", name="recuperer_notes")
def recuperer_notes(
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupérer les notes d'un RDV vidéo"""
    try:
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        return {
            "notes": rdv.notes or ""
        }
        
    except Exception as e:
        logger.error(f"💥 Erreur dans recuperer_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/notes", name="sauvegarder_notes")
def sauvegarder_notes(
    rdv_id: int,
    notes: str = Form(...),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Sauvegarder les notes d'un RDV vidéo"""
    try:
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        rdv.notes = notes
        session.add(rdv)
        session.commit()
        
        return {
            "status": "success",
            "message": "Notes sauvegardées avec succès"
        }
        
    except Exception as e:
        logger.error(f"💥 Erreur dans sauvegarder_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/envoyer-invitation", name="envoyer_invitation_email")
def envoyer_invitation_email(
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Envoyer l'invitation vidéo par email"""
    try:
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
        
        # Envoyer l'email d'invitation
        success = EmailUtils.send_video_invitation(
            to_email=candidat.email,
            candidat_nom=candidat.nom,
            candidat_prenom=candidat.prenom,
            rdv_id=rdv_id,
            rdv_date=rdv.debut.strftime("%d/%m/%Y à %H:%M") if rdv.debut else "Non définie",
            meet_link=rdv.meet_link or generate_meet_link()
        )
        
        if success:
            return {
                "status": "success",
                "message": "Invitation vidéo envoyée avec succès"
            }
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de l'email")
        
    except Exception as e:
        logger.error(f"💥 Erreur dans envoyer_invitation_email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

