from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from typing import List, Optional
from datetime import date, datetime, timezone

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user
from app_lia_web.app.models.base import User, Programme, Inscription, Candidat, SuiviMensuel
from app_lia_web.app.schemas.suivi_mensuel_schemas import (
    SuiviMensuelCreate, SuiviMensuelUpdate, SuiviMensuelFilter
)
from app_lia_web.app.services.suivi_mensuel_service import SuiviMensuelService
from app_lia_web.app.templates import templates
from app_lia_web.app.services.file_upload_service import FileUploadService

router = APIRouter()
suivi_mensuel_service = SuiviMensuelService()

def clean_form_data(data: str) -> Optional[str]:
    """Nettoie les données du formulaire en convertissant les chaînes vides en None"""
    if not data or data.strip() == "":
        return None
    return data.strip()

def clean_numeric_data(data: str) -> Optional[float]:
    """Nettoie les données numériques du formulaire"""
    if not data or data.strip() == "":
        return None
    try:
        return float(data.strip())
    except ValueError:
        return None

def clean_int_data(data: str) -> Optional[int]:
    """Nettoie les données entières du formulaire"""
    if not data or data.strip() == "":
        return None
    try:
        return int(data.strip())
    except ValueError:
        return None

# === ROUTES WEB ===

@router.get("/", name="liste_candidats_valides", response_class=HTMLResponse)
async def liste_candidats_valides(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = None,
    search_candidat: Optional[str] = None,
):
    """Liste des candidats validés pour créer des suivis mensuels"""
    print(f"🔍 DEBUG: Affichage des candidats validés - programme_id: {programme_id}")
    print(f"🔍 DEBUG: search_candidat: {search_candidat}")
    
    try:
        # D'abord, vérifier tous les statuts disponibles
        print(f"🔍 DEBUG: Vérification des statuts disponibles...")
        all_inscriptions = db.exec(select(Inscription.statut)).all()
        unique_statuts = set(all_inscriptions)
        print(f"🔍 DEBUG: Statuts trouvés: {unique_statuts}")
        
        # Récupérer les inscriptions validées avec informations candidat et programme
        query = select(
            Inscription.id,
            Inscription.cree_le,
            Inscription.statut,
            Candidat.prenom,
            Candidat.nom,
            Candidat.email,
            Candidat.photo_profil,
            Programme.nom.label("programme_nom"),
            Programme.code.label("programme_code")
        ).join(Candidat, Candidat.id == Inscription.candidat_id)\
        .join(Programme, Programme.id == Inscription.programme_id)\
        .where(Inscription.statut == "VALIDE")  # Seulement les candidats validés
        
        print(f"🔍 DEBUG: Requête de base créée : {query}")
        
        if programme_id:
            query = query.where(Inscription.programme_id == programme_id)
            print(f"🔍 DEBUG: Filtre programme_id ajouté: {programme_id}")
        
        if search_candidat:
            search_pattern = f"%{search_candidat}%"
            query = query.where(
                (Candidat.prenom.ilike(search_pattern)) |
                (Candidat.nom.ilike(search_pattern))
            )
            print(f"🔍 DEBUG: Filtre recherche ajouté: {search_candidat}")
        
        query = query.order_by(Programme.nom, Candidat.nom, Candidat.prenom)
        
        print(f"🔍 DEBUG: Exécution de la requête...")
        candidats_valides = db.exec(query).all()
        print(f"🔍 DEBUG: {len(candidats_valides)} candidats validés trouvés")
        
        # Si aucun candidat validé, essayer avec d'autres statuts pour debug
        if len(candidats_valides) == 0:
            print(f"🔍 DEBUG: Aucun candidat validé trouvé, vérification des autres statuts...")
            for statut in unique_statuts:
                count = db.exec(
                    select(Inscription.id)
                    .where(Inscription.statut == statut)
                ).all()
                print(f"🔍 DEBUG: Statut '{statut}': {len(count)} inscriptions")
        
        # Récupérer les programmes pour le filtre
        programmes = db.exec(select(Programme)).all()
        print(f"🔍 DEBUG: {len(programmes)} programmes trouvés")
        
        # Statistiques
        total_candidats = len(candidats_valides)
        programmes_count = len(set(candidat.programme_nom for candidat in candidats_valides)) if candidats_valides else 0
        
        print(f"🔍 DEBUG: Statistiques - total_candidats: {total_candidats}, programmes_count: {programmes_count}")
        
        return templates.TemplateResponse(
            "suivi_mensuel/liste_candidat.html",
            {
                "request": request,
                "utilisateur": current_user,
                "candidats_valides": candidats_valides,
                "programmes": programmes,
                "programme_id": programme_id,
                "search_candidat": search_candidat,
                "total_candidats": total_candidats,
                "programmes_count": programmes_count,
                "current_date": date.today()
                
            }
        )
    except Exception as e:
        print(f"❌ DEBUG: Erreur dans liste_candidats_valides: {e}")
        import traceback
        traceback.print_exc()
        raise

@router.get("/suivis", name="liste_suivis_mensuels", response_class=HTMLResponse)
async def liste_suivis_mensuels(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = None,
    mois_debut: Optional[str] = None,
    mois_fin: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    has_commentaire: Optional[bool] = None,
    search_candidat: Optional[str] = None,
):
    """Liste des suivis mensuels avec filtres"""
    print(f"🔍 DEBUG: Paramètres reçus - mois_debut: {mois_debut} (type: {type(mois_debut)})")
    print(f"🔍 DEBUG: Paramètres reçus - mois_fin: {mois_fin} (type: {type(mois_fin)})")
    
    filters = SuiviMensuelFilter(
        programme_id=programme_id,
        mois_debut=mois_debut,
        mois_fin=mois_fin,
        score_min=score_min,
        score_max=score_max,
        has_commentaire=has_commentaire,
        search_candidat=search_candidat
    )
    suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters)
    stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters)
    programmes = db.exec(select(Programme)).all()

    return templates.TemplateResponse(
        "suivi_mensuel/liste_candidat.html",
        {
            "request": request,
            "utilisateur": current_user,
            "suivis": suivis,
            "stats": stats,
            "programmes": programmes,
            "filters": filters,
            "current_date": date.today()
        }
    )

@router.get("/creer", name="creer_suivi_mensuel_form", response_class=HTMLResponse)
async def creer_suivi_mensuel_form(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    inscription_id: Optional[int] = None,
    mois: Optional[date] = None
):
    """Formulaire de création d'un suivi mensuel"""
    inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db)
    
    initial_data = {
        "inscription_id": inscription_id,
        "mois": mois.strftime("%Y-%m") if mois else date.today().strftime("%Y-%m")
    }

    return templates.TemplateResponse(
        "suivi_mensuel/form_business.html",
        {
            "request": request,
            "utilisateur": current_user,
            "inscriptions": inscriptions,
            "initial_data": initial_data,
            "edit_mode": False,
            "inscription_id": inscription_id
        }
    )

@router.post("/creer", name="creer_suivi_mensuel")
async def creer_suivi_mensuel(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    inscription_id: int = Form(...),
    mois: str = Form(...),  # Changé en str pour debug
    # Métriques business
    chiffre_affaires_actuel: str = Form(""),
    nb_stagiaires: str = Form(""),
    nb_alternants: str = Form(""),
    nb_cdd: str = Form(""),
    nb_cdi: str = Form(""),
    montant_subventions_obtenues: str = Form(""),
    organismes_financeurs: str = Form(""),
    montant_dettes_effectuees: str = Form(""),
    montant_dettes_encours: str = Form(""),
    montant_dettes_envisagees: str = Form(""),
    montant_equity_effectue: str = Form(""),
    montant_equity_encours: str = Form(""),
    statut_juridique: str = Form(""),
    adresse_entreprise: str = Form(""),
    situation_socioprofessionnelle: str = Form(""),
    # Métriques générales
    score_objectifs: str = Form(""),
    commentaire: str = Form("")
):
    """Créer un nouveau suivi mensuel avec métriques business"""
    print(f"🔍 DEBUG: Données reçues - inscription_id: {inscription_id}, mois: {mois} (type: {type(mois)})")
    print(f"🔍 DEBUG: chiffre_affaires_actuel: {chiffre_affaires_actuel}")
    print(f"🔍 DEBUG: nb_stagiaires: {nb_stagiaires}")
    
    try:
        # Convertir le mois string en date
        from datetime import datetime
        try:
            mois_date = datetime.strptime(mois, '%Y-%m').date().replace(day=1)
            print(f"🔍 DEBUG: mois converti: {mois_date}")
        except ValueError as e:
            print(f"❌ DEBUG: Erreur conversion mois: {e}")
            raise ValueError(f"Format de mois invalide: {mois}")
        
        suivi_create = SuiviMensuelCreate(
            inscription_id=inscription_id,
            mois=mois_date,
            chiffre_affaires_actuel=clean_numeric_data(chiffre_affaires_actuel),
            nb_stagiaires=clean_int_data(nb_stagiaires),
            nb_alternants=clean_int_data(nb_alternants),
            nb_cdd=clean_int_data(nb_cdd),
            nb_cdi=clean_int_data(nb_cdi),
            montant_subventions_obtenues=clean_numeric_data(montant_subventions_obtenues),
            organismes_financeurs=clean_form_data(organismes_financeurs),
            montant_dettes_effectuees=clean_numeric_data(montant_dettes_effectuees),
            montant_dettes_encours=clean_numeric_data(montant_dettes_encours),
            montant_dettes_envisagees=clean_numeric_data(montant_dettes_envisagees),
            montant_equity_effectue=clean_numeric_data(montant_equity_effectue),
            montant_equity_encours=clean_numeric_data(montant_equity_encours),
            statut_juridique=clean_form_data(statut_juridique),
            adresse_entreprise=clean_form_data(adresse_entreprise),
            situation_socioprofessionnelle=clean_form_data(situation_socioprofessionnelle),
            score_objectifs=clean_numeric_data(score_objectifs),
            commentaire=clean_form_data(commentaire)
        )
        suivi_mensuel_service.create_suivi_mensuel(db, suivi_create)
        return RedirectResponse(
            url=request.url_for("suivis_par_inscription", inscription_id=inscription_id), status_code=status.HTTP_303_SEE_OTHER
        )
    except ValueError as e:
        inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db)
        return templates.TemplateResponse(
            "suivi_mensuel/form_business.html",
            {
                "request": request,
                "utilisateur": current_user,
                "inscriptions": inscriptions,
                "initial_data": {
                    "inscription_id": inscription_id,
                    "mois": mois.strftime("%Y-%m"),
                    "chiffre_affaires_actuel": chiffre_affaires_actuel,
                    "nb_stagiaires": nb_stagiaires,
                    "nb_alternants": nb_alternants,
                    "nb_cdd": nb_cdd,
                    "nb_cdi": nb_cdi,
                    "montant_subventions_obtenues": montant_subventions_obtenues,
                    "organismes_financeurs": organismes_financeurs,
                    "montant_dettes_effectuees": montant_dettes_effectuees,
                    "montant_dettes_encours": montant_dettes_encours,
                    "montant_dettes_envisagees": montant_dettes_envisagees,
                    "montant_equity_effectue": montant_equity_effectue,
                    "montant_equity_encours": montant_equity_encours,
                    "statut_juridique": statut_juridique,
                    "adresse_entreprise": adresse_entreprise,
                    "situation_socioprofessionnelle": situation_socioprofessionnelle,
                    "score_objectifs": score_objectifs,
                    "commentaire": commentaire
                },
                "error_message": str(e),
                "edit_mode": False,
                "inscription_id": inscription_id
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/modifier/{suivi_id}", name="modifier_suivi_mensuel_form", response_class=HTMLResponse)
async def modifier_suivi_mensuel_form(
    request: Request,
    suivi_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Formulaire de modification d'un suivi mensuel"""
    suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
    if not suivi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
    
    inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db)

    return templates.TemplateResponse(
        "suivi_mensuel/form_business.html",
        {
            "request": request,
            "utilisateur": current_user,
            "suivi": suivi,
            "inscriptions": inscriptions,
            "initial_data": {
                "inscription_id": suivi.inscription_id,
                "mois": suivi.mois.strftime("%Y-%m"),
                "chiffre_affaires_actuel": suivi.chiffre_affaires_actuel,
                "nb_stagiaires": suivi.nb_stagiaires,
                "nb_alternants": suivi.nb_alternants,
                "nb_cdd": suivi.nb_cdd,
                "nb_cdi": suivi.nb_cdi,
                "montant_subventions_obtenues": suivi.montant_subventions_obtenues,
                "organismes_financeurs": suivi.organismes_financeurs,
                "montant_dettes_effectuees": suivi.montant_dettes_effectuees,
                "montant_dettes_encours": suivi.montant_dettes_encours,
                "montant_dettes_envisagees": suivi.montant_dettes_envisagees,
                "montant_equity_effectue": suivi.montant_equity_effectue,
                "montant_equity_encours": suivi.montant_equity_encours,
                "statut_juridique": suivi.statut_juridique,
                "adresse_entreprise": suivi.adresse_entreprise,
                "situation_socioprofessionnelle": suivi.situation_socioprofessionnelle,
                "score_objectifs": suivi.score_objectifs,
                "commentaire": suivi.commentaire
            },
            "edit_mode": True,
            "inscription_id": suivi.inscription_id
        }
    )

@router.post("/modifier/{suivi_id}", name="modifier_suivi_mensuel")
async def modifier_suivi_mensuel(
    request: Request,
    suivi_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    inscription_id: int = Form(...),
    mois: str = Form(...),  # Changé en str pour gérer le format YYYY-MM
    # Métriques business
    chiffre_affaires_actuel: str = Form(""),
    nb_stagiaires: str = Form(""),
    nb_alternants: str = Form(""),
    nb_cdd: str = Form(""),
    nb_cdi: str = Form(""),
    montant_subventions_obtenues: str = Form(""),
    organismes_financeurs: str = Form(""),
    montant_dettes_effectuees: str = Form(""),
    montant_dettes_encours: str = Form(""),
    montant_dettes_envisagees: str = Form(""),
    montant_equity_effectue: str = Form(""),
    montant_equity_encours: str = Form(""),
    statut_juridique: str = Form(""),
    adresse_entreprise: str = Form(""),
    situation_socioprofessionnelle: str = Form(""),
    # Métriques générales
    score_objectifs: str = Form(""),
    commentaire: str = Form("")
):
    """Modifier un suivi mensuel avec métriques business"""
    try:
        # Convertir le mois string en date
        from datetime import datetime
        try:
            mois_date = datetime.strptime(mois, '%Y-%m').date().replace(day=1)
            print(f"🔍 DEBUG: mois converti pour modification: {mois_date}")
        except ValueError as e:
            print(f"❌ DEBUG: Erreur conversion mois: {e}")
            raise ValueError(f"Format de mois invalide: {mois}")
        
        suivi_update = SuiviMensuelUpdate(
            inscription_id=inscription_id,
            mois=mois_date,
            chiffre_affaires_actuel=clean_numeric_data(chiffre_affaires_actuel),
            nb_stagiaires=clean_int_data(nb_stagiaires),
            nb_alternants=clean_int_data(nb_alternants),
            nb_cdd=clean_int_data(nb_cdd),
            nb_cdi=clean_int_data(nb_cdi),
            montant_subventions_obtenues=clean_numeric_data(montant_subventions_obtenues),
            organismes_financeurs=clean_form_data(organismes_financeurs),
            montant_dettes_effectuees=clean_numeric_data(montant_dettes_effectuees),
            montant_dettes_encours=clean_numeric_data(montant_dettes_encours),
            montant_dettes_envisagees=clean_numeric_data(montant_dettes_envisagees),
            montant_equity_effectue=clean_numeric_data(montant_equity_effectue),
            montant_equity_encours=clean_numeric_data(montant_equity_encours),
            statut_juridique=clean_form_data(statut_juridique),
            adresse_entreprise=clean_form_data(adresse_entreprise),
            situation_socioprofessionnelle=clean_form_data(situation_socioprofessionnelle),
            score_objectifs=clean_numeric_data(score_objectifs),
            commentaire=clean_form_data(commentaire)
        )
        suivi = suivi_mensuel_service.update_suivi_mensuel(db, suivi_id, suivi_update)
        if not suivi:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
        return RedirectResponse(
            url=request.url_for("suivis_par_inscription", inscription_id=inscription_id), status_code=status.HTTP_303_SEE_OTHER
        )
    except ValueError as e:
        suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
        inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db)
        return templates.TemplateResponse(
            "suivi_mensuel/form_business.html",
            {
                "request": request,
                "utilisateur": current_user,
                "suivi": suivi,
                "inscriptions": inscriptions,
                "initial_data": {
                    "inscription_id": inscription_id,
                    "mois": mois.strftime("%Y-%m"),
                    "chiffre_affaires_actuel": chiffre_affaires_actuel,
                    "nb_stagiaires": nb_stagiaires,
                    "nb_alternants": nb_alternants,
                    "nb_cdd": nb_cdd,
                    "nb_cdi": nb_cdi,
                    "montant_subventions_obtenues": montant_subventions_obtenues,
                    "organismes_financeurs": organismes_financeurs,
                    "montant_dettes_effectuees": montant_dettes_effectuees,
                    "montant_dettes_encours": montant_dettes_encours,
                    "montant_dettes_envisagees": montant_dettes_envisagees,
                    "montant_equity_effectue": montant_equity_effectue,
                    "montant_equity_encours": montant_equity_encours,
                    "statut_juridique": statut_juridique,
                    "adresse_entreprise": adresse_entreprise,
                    "situation_socioprofessionnelle": situation_socioprofessionnelle,
                    "score_objectifs": score_objectifs,
                    "commentaire": commentaire
                },
                "error_message": str(e),
                "edit_mode": True,
                "inscription_id": inscription_id
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/supprimer/{suivi_id}", name="supprimer_suivi_mensuel")
async def supprimer_suivi_mensuel(
    request: Request,
    suivi_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un suivi mensuel"""
    # Récupérer l'inscription_id avant suppression pour redirection
    suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
    if not suivi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
    
    inscription_id = suivi.inscription_id
    
    if not suivi_mensuel_service.delete_suivi_mensuel(db, suivi_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
    return RedirectResponse(
        url=request.url_for("suivis_par_inscription", inscription_id=inscription_id), status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/inscription/{inscription_id}", name="suivis_par_inscription", response_class=HTMLResponse)
async def suivis_par_inscription(
    request: Request,
    inscription_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Suivis mensuels d'une inscription spécifique"""
    inscription = db.get(Inscription, inscription_id)
    if not inscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inscription non trouvée")
    
    candidat = db.get(Candidat, inscription.candidat_id)
    programme = db.get(Programme, inscription.programme_id)

    filters = SuiviMensuelFilter(inscription_id=inscription_id)
    suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters)
    stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters)

    return templates.TemplateResponse(
        "suivi_mensuel/inscription.html",
        {
            "request": request,
            "utilisateur": current_user,
            "inscription": inscription,
            "candidat": candidat,
            "programme": programme,
            "suivis": suivis,
            "stats": stats
        }
    )

@router.get("/programme/{programme_id}", name="suivis_par_programme", response_class=HTMLResponse)
async def suivis_par_programme(
    request: Request,
    programme_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Suivis mensuels d'un programme spécifique"""
    programme = db.get(Programme, programme_id)
    if not programme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme non trouvé")
    
    filters = SuiviMensuelFilter(programme_id=programme_id)
    suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters)
    stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters)

    return templates.TemplateResponse(
        "suivi_mensuel/programme.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programme": programme,
            "suivis": suivis,
            "stats": stats
        }
    )