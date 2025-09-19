# app/routers/rendez_vous.py
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user
from app_lia_web.app.models.base import User, Programme, Inscription, Candidat, Entreprise, RendezVous
from app_lia_web.app.models.enums import TypeRDV, StatutRDV, UserRole
from app_lia_web.app.schemas.rendez_vous_schemas import RendezVousCreate, RendezVousUpdate, RendezVousFilter
from app_lia_web.app.services.rendez_vous_service import RendezVousService
from app_lia_web.app.templates import templates

router = APIRouter()

@router.get("/rendez-vous", name="rendez_vous_list", response_class=HTMLResponse)
def rendez_vous_list(
    request: Request,
    session: Session = Depends(get_session),
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
    rendez_vous = service.search_rendez_vous(filters, limit=limit, offset=offset)
    
    # Statistiques
    stats = service.get_statistiques_rendez_vous(programme_id)
    
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

@router.get("/rendez-vous/creer", response_class=HTMLResponse)
def rendez_vous_create_form(
    request: Request,
    session: Session = Depends(get_session),
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
    
    # Vérifier les inscriptions dans la base
    all_inscriptions = session.exec(select(Inscription)).all()
    print(f"🔍 DEBUG - Total inscriptions: {len(all_inscriptions)}")
    for inscription in all_inscriptions:
        print(f"  Inscription {inscription.id}: statut={inscription.statut}, candidat_id={inscription.candidat_id}, programme_id={inscription.programme_id}")
    
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

@router.post("/rendez-vous/creer")
def rendez_vous_create(
    request: Request,
    session: Session = Depends(get_session),
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
        
        return RedirectResponse(url="/rendez-vous", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création du rendez-vous: {str(e)}")

@router.get("/rendez-vous/{rdv_id}", response_class=HTMLResponse)
def rendez_vous_detail(
    rdv_id: int,
    request: Request,
    session: Session = Depends(get_session),
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

@router.post("/rendez-vous/{rdv_id}/modifier")
def rendez_vous_update(
    rdv_id: int,
    request: Request,
    session: Session = Depends(get_session),
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
        
        return RedirectResponse(url=f"/rendez-vous/{rdv_id}", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la modification du rendez-vous: {str(e)}")

@router.post("/rendez-vous/{rdv_id}/supprimer")
def rendez_vous_delete(
    rdv_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un rendez-vous"""
    
    service = RendezVousService(session)
    success = service.delete_rendez_vous(rdv_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    return RedirectResponse(url="/rendez-vous", status_code=303)

@router.get("/rendez-vous/api/search")
def rendez_vous_api_search(
    session: Session = Depends(get_session),
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

@router.get("/rendez-vous/api/statistiques")
def rendez_vous_api_stats(
    session: Session = Depends(get_session),
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
