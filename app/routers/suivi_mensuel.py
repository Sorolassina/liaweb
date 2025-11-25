from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from sqlalchemy import text
from typing import List, Optional
from datetime import date, datetime, timezone

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.program_schema_integration import table_exists_anywhere, get_schema_from_request, get_schema_routing_service, SchemaRoutingService
from ..models.base import User, Programme, Candidat, SuiviMensuel
from ..models.preinscription import Preinscription
from ..schemas.suivi_mensuel_schemas import (
    SuiviMensuelCreate, SuiviMensuelUpdate, SuiviMensuelFilter
)
from ..services.suivi_mensuel_service import SuiviMensuelService
from ..templates import templates
from ..services.file_upload_service import FileUploadService

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

def _normalize_situation_socio(data: Optional[str]) -> str:
    """Normalise la situation socio-professionnelle : convertit None, '' ou 'nc' en 'Non communiqué'"""
    if not data or data.strip() == "" or data.strip().lower() == 'nc':
        return 'Non communiqué'
    return data.strip()

# === ROUTES WEB ===

@router.get("/", name="liste_candidats_valides", response_class=HTMLResponse)
async def liste_candidats_valides(
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme: Optional[str] = None,
    programme_id: Optional[int] = None,
    search_candidat: Optional[str] = None,
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
):
    """Liste des candidats validés pour créer des suivis mensuels"""
    print(f"🔍 DEBUG: Affichage des candidats validés - programme: {programme}, programme_id: {programme_id}")
    print(f"🔍 DEBUG: search_candidat: {search_candidat}")
    
    try:
        # Récupérer et configurer le schéma (comme dans les routes seminaire)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        print(f"🔍 DEBUG: Schéma configuré: {schema_name}")
        
        # Si programme (code) est fourni, récupérer l'ID correspondant
        if programme and not programme_id:
            programme_obj = db.exec(
                select(Programme).where(Programme.code.ilike(programme))
            ).first()
            if programme_obj:
                programme_id = programme_obj.id
        
        # D'abord, vérifier tous les statuts disponibles
        print(f"🔍 DEBUG: Vérification des statuts disponibles...")
        # NOTE: Le modèle Inscription a été supprimé. Utiliser directement les candidats validés.
        from ..models.enums import DecisionJury
        
        # Construire la requête SQL directe avec le schéma du programme pour candidat/preinscription
        # et public pour programme
        base_query = f"""
            SELECT 
                c.id,
                c.id AS cree_le,
                c.statut,
                c.prenom,
                c.nom,
                c.email,
                c.photo_profil,
                p.nom AS programme_nom,
                p.code AS programme_code
            FROM {schema_name}.candidat c
            INNER JOIN {schema_name}.preinscription pr ON pr.candidat_id = c.id
            INNER JOIN public.programme p ON p.id = pr.programme_id
        """
        
        where_conditions = []
        params = {}
        
        # Filtrer uniquement les candidats validés
        where_conditions.append("c.statut = :statut_valide")
        params["statut_valide"] = DecisionJury.VALIDE.value
        print(f"🔍 DEBUG: Filtre statut VALIDE ajouté")
        
        # Filtrer par programme si fourni
        if programme_id:
            where_conditions.append("pr.programme_id = :programme_id")
            params["programme_id"] = programme_id
            print(f"🔍 DEBUG: Filtre programme_id ajouté: {programme_id}")
        
        # Filtrer par recherche de candidat
        if search_candidat:
            where_conditions.append("(LOWER(c.prenom) LIKE :search_pattern OR LOWER(c.nom) LIKE :search_pattern)")
            params["search_pattern"] = f"%{search_candidat.lower()}%"
            print(f"🔍 DEBUG: Filtre recherche ajouté: {search_candidat}")
        
        # Ajouter le filtre partenaire_bpi si nécessaire
        from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
        add_partenaire_bpi_filter(current_user, where_conditions, params, "c.")
        
        # Ajouter les conditions WHERE si nécessaire
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        # Ajouter le tri
        base_query += " ORDER BY p.nom, c.nom, c.prenom"
        
        print(f"🔍 DEBUG: Requête SQL: {base_query}")
        print(f"🔍 DEBUG: Paramètres: {params}")
        
        # Exécuter la requête
        query = text(base_query)
        if params:
            query = query.bindparams(**params)
        
        print(f"🔍 DEBUG: Exécution de la requête...")
        results = db.exec(query).all()
        
        # Convertir les résultats en objets avec attributs
        candidats_valides = []
        for row in results:
            # Les résultats de text() retournent des Row objects accessibles par nom
            # Créer un objet simple avec les attributs nécessaires
            candidat_obj = type('CandidatRow', (), {
                'id': row.id,
                'cree_le': row.cree_le,
                'statut': row.statut,
                'prenom': row.prenom,
                'nom': row.nom,
                'email': row.email,
                'photo_profil': row.photo_profil,
                'programme_nom': row.programme_nom,
                'programme_code': row.programme_code
            })()
            candidats_valides.append(candidat_obj)
        print(f"🔍 DEBUG: {len(candidats_valides)} candidats validés trouvés")
        
        # Si aucun candidat validé, essayer avec d'autres statuts pour debug
        if len(candidats_valides) == 0:
            print(f"🔍 DEBUG: Aucun candidat validé trouvé, vérification des autres statuts...")
            # NOTE: Le modèle Inscription a été supprimé
            # for statut in unique_statuts:
            #     count = db.exec(
            #         select(Inscription.id)
            #         .where(Inscription.statut == statut)
            #     ).all()
            #     print(f"🔍 DEBUG: Statut '{statut}': {len(count)} inscriptions")
        
        # Récupérer les programmes pour le filtre
        programmes = db.exec(select(Programme)).all()
        print(f"🔍 DEBUG: {len(programmes)} programmes trouvés")
        
        # Statistiques
        total_candidats = len(candidats_valides)
        programmes_count = len(set(candidat.programme_nom for candidat in candidats_valides)) if candidats_valides else 0
        
        print(f"🔍 DEBUG: Statistiques - total_candidats: {total_candidats}, programmes_count: {programmes_count}")
        
        # Déterminer le code du programme pour les URLs
        programme_code = programme.upper() if programme else schema_name.upper()
        
        return templates.TemplateResponse(
            "pages/suivi_mensuel/liste_candidat.html",
            {
                "request": request,
                "utilisateur": current_user,
                "candidats_valides": candidats_valides,
                "programmes": programmes,
                "programme": programme,
                "programme_code": programme_code,
                "programme_id": programme_id,
                "search_candidat": search_candidat,
                "total_candidats": total_candidats,
                "programmes_count": programmes_count,
                "current_date": date.today(),
                "schema_name": schema_name
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
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme_id: Optional[int] = None,
    mois_debut: Optional[str] = None,
    mois_fin: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    has_commentaire: Optional[bool] = None,
    search_candidat: Optional[str] = None,
):
    """Liste des suivis mensuels avec filtres"""
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
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
    suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters, schema_name=schema_name)
    stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters, schema_name=schema_name)
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
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    inscription_id: Optional[int] = None,
    mois: Optional[date] = None,
    programme: Optional[str] = None
):
    """Formulaire de création d'un suivi mensuel"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request, programme=programme) or 'acd'
    if schema_name == 'public':
        schema_name = 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
    programme_code = programme.upper() if programme else schema_name.upper()
    
    inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db, schema_name=schema_name)
    
    initial_data = {
        "inscription_id": inscription_id,
        "mois": mois.strftime("%Y-%m") if mois else date.today().strftime("%Y-%m")
    }

    return templates.TemplateResponse(
        "pages/suivi_mensuel/form_business.html",
        {
            "request": request,
            "utilisateur": current_user,
            "inscriptions": inscriptions,
            "initial_data": initial_data,
            "edit_mode": False,
            "inscription_id": inscription_id,
            "programme_code": programme_code,
            "schema_name": schema_name
        }
    )

@router.post("/creer", name="creer_suivi_mensuel")
async def creer_suivi_mensuel(
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    inscription_id: int = Form(...),
    mois: str = Form(...),  # Changé en str pour debug
    programme: Optional[str] = None,
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
    # Statut dans le programme
    statut_programme: str = Form(""),
    raison_abandon: str = Form(""),
    # Métriques générales
    score_objectifs: str = Form(""),
    commentaire: str = Form("")
):
    """Créer un nouveau suivi mensuel avec métriques business"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request, programme=programme) or 'acd'
    if schema_name == 'public':
        schema_name = 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
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
            situation_socioprofessionnelle=_normalize_situation_socio(clean_form_data(situation_socioprofessionnelle)),
            statut_programme=clean_form_data(statut_programme) if clean_form_data(statut_programme) else None,
            raison_abandon=clean_form_data(raison_abandon) if clean_form_data(raison_abandon) else None,
            score_objectifs=clean_numeric_data(score_objectifs),
            commentaire=clean_form_data(commentaire)
        )
        suivi_mensuel_service.create_suivi_mensuel(db, suivi_create)
        # Préserver le paramètre programme dans la redirection
        programme = request.query_params.get("programme", "")
        redirect_url = str(request.url_for("suivis_par_inscription", inscription_id=inscription_id))
        if programme:
            redirect_url += f"?programme={programme}"
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db, schema_name=schema_name)
        return templates.TemplateResponse(
            "pages/suivi_mensuel/form_business.html",
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
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme: Optional[str] = None
):
    """Formulaire de modification d'un suivi mensuel"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request, programme=programme) or 'acd'
    if schema_name == 'public':
        schema_name = 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
    programme_code = programme.upper() if programme else schema_name.upper()
    
    suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
    if not suivi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
    
    inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db, schema_name=schema_name)

    return templates.TemplateResponse(
        "pages/suivi_mensuel/form_business.html",
        {
            "request": request,
            "utilisateur": current_user,
            "suivi": suivi,
            "inscriptions": inscriptions,
            "initial_data": {
                "inscription_id": suivi.candidat_id,
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
                "statut_programme": suivi.statut_programme,
                "raison_abandon": suivi.raison_abandon,
                "score_objectifs": suivi.score_objectifs,
                "commentaire": suivi.commentaire
            },
            "edit_mode": True,
            "inscription_id": suivi.candidat_id,
            "programme_code": programme_code,
            "schema_name": schema_name
        }
    )

@router.post("/modifier/{suivi_id}", name="modifier_suivi_mensuel")
async def modifier_suivi_mensuel(
    request: Request,
    suivi_id: int,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    inscription_id: int = Form(...),
    mois: str = Form(...),  # Changé en str pour gérer le format YYYY-MM
    programme: Optional[str] = None,
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
    # Statut dans le programme
    statut_programme: str = Form(""),
    raison_abandon: str = Form(""),
    # Métriques générales
    score_objectifs: str = Form(""),
    commentaire: str = Form("")
):
    """Modifier un suivi mensuel avec métriques business"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request, programme=programme) or 'acd'
    if schema_name == 'public':
        schema_name = 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
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
            situation_socioprofessionnelle=_normalize_situation_socio(clean_form_data(situation_socioprofessionnelle)),
            statut_programme=clean_form_data(statut_programme) if clean_form_data(statut_programme) else None,
            raison_abandon=clean_form_data(raison_abandon) if clean_form_data(raison_abandon) else None,
            score_objectifs=clean_numeric_data(score_objectifs),
            commentaire=clean_form_data(commentaire)
        )
        suivi = suivi_mensuel_service.update_suivi_mensuel(db, suivi_id, suivi_update)
        if not suivi:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
        # Préserver le paramètre programme dans la redirection
        programme = request.query_params.get("programme", "")
        redirect_url = str(request.url_for("suivis_par_inscription", inscription_id=inscription_id))
        if programme:
            redirect_url += f"?programme={programme}"
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
        inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db, schema_name=schema_name)
        return templates.TemplateResponse(
            "pages/suivi_mensuel/form_business.html",
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
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un suivi mensuel"""
    # Récupérer le candidat_id avant suppression pour redirection
    suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
    if not suivi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
    
    inscription_id = suivi.candidat_id  # candidat_id est utilisé comme inscription_id pour la compatibilité avec les URLs
    
    if not suivi_mensuel_service.delete_suivi_mensuel(db, suivi_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suivi mensuel non trouvé")
    # Préserver le paramètre programme dans la redirection
    programme = request.query_params.get("programme", "")
    redirect_url = str(request.url_for("suivis_par_inscription", inscription_id=inscription_id))
    if programme:
        redirect_url += f"?programme={programme}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

@router.get("/inscription/{inscription_id}", name="suivis_par_inscription", response_class=HTMLResponse)
async def suivis_par_inscription(
    request: Request,
    inscription_id: int,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
):
    """Suivis mensuels d'un candidat spécifique (inscription_id est maintenant candidat_id)"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
    # inscription_id est maintenant interprété comme candidat_id
    candidat_id = inscription_id
    
    # Récupérer le candidat via requête SQL directe
    candidat_query = text(f"SELECT * FROM {schema_name}.candidat WHERE id = :candidat_id")
    candidat_result = db.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
    
    if not candidat_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidat non trouvé")
    
    candidat = type('Candidat', (), dict(candidat_result._mapping))()
    
    # Récupérer la preinscription pour obtenir le programme
    preinscription_query = text(f"""
        SELECT pr.*, p.nom as programme_nom, p.code as programme_code
        FROM {schema_name}.preinscription pr
        INNER JOIN public.programme p ON p.id = pr.programme_id
        WHERE pr.candidat_id = :candidat_id
        LIMIT 1
    """)
    preinscription_result = db.exec(preinscription_query.bindparams(candidat_id=candidat_id)).first()
    
    if not preinscription_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Préinscription non trouvée pour ce candidat")
    
    programme = type('Programme', (), {
        'id': preinscription_result.programme_id,
        'nom': preinscription_result.programme_nom,
        'code': preinscription_result.programme_code
    })()
    
    # Créer un objet inscription factice pour la compatibilité avec le template
    # Récupérer cree_le depuis le résultat (peut être dans _mapping ou directement)
    preinscription_dict = dict(preinscription_result._mapping) if hasattr(preinscription_result, '_mapping') else dict(preinscription_result)
    cree_le_value = preinscription_dict.get('cree_le', datetime.now(timezone.utc))
    
    inscription = type('Inscription', (), {
        'id': candidat_id,
        'candidat_id': candidat_id,
        'programme_id': preinscription_result.programme_id,
        'cree_le': cree_le_value
    })()

    filters = SuiviMensuelFilter(candidat_id=candidat_id)
    suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters, schema_name=schema_name)
    stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters, schema_name=schema_name)

    # Déterminer le code du programme pour les URLs
    programme_code = programme.code if hasattr(programme, 'code') else schema_name.upper()
    
    return templates.TemplateResponse(
        "pages/suivi_mensuel/inscription.html",
        {
            "request": request,
            "utilisateur": current_user,
            "inscription": inscription,
            "candidat": candidat,
            "programme": programme,
            "programme_code": programme_code,
            "suivis": suivis,
            "stats": stats,
            "schema_name": schema_name
        }
    )

@router.get("/programme/{programme_id}", name="suivis_par_programme", response_class=HTMLResponse)
async def suivis_par_programme(
    request: Request,
    programme_id: int,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Suivis mensuels d'un programme spécifique"""
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    db.exec(text(f"SET search_path TO {schema_name}, public"))
    
    programme = db.get(Programme, programme_id)
    if not programme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme non trouvé")
    
    filters = SuiviMensuelFilter(programme_id=programme_id)
    suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters, schema_name=schema_name)
    stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters, schema_name=schema_name)

    return templates.TemplateResponse(
        "pages/suivi_mensuel/programme.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programme": programme,
            "suivis": suivis,
            "stats": stats
        }
    )