# app/routers/elearning.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi import UploadFile, File, Form
from sqlmodel import Session, select, text
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.program_schema_integration import (
    table_exists_anywhere, 
    get_schema_from_request, 
    get_schema_routing_service,
    SchemaRoutingService
)
import logging
from ..models.base import User, Programme, Candidat
from ..core.config import settings
from ..models.elearning import (
    RessourceElearning, ModuleElearning, ProgressionElearning,
    ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning,
    ModuleRessource
)
from ..services.elearning_service import ElearningService
from ..services.file_upload_service import FileUploadService
from ..schemas.elearning import (
    RessourceElearningCreate, RessourceElearningUpdate,
    ModuleElearningCreate, ModuleElearningUpdate,
    ProgressionElearningCreate, ProgressionElearningUpdate,
    ObjectifElearningCreate, ObjectifElearningUpdate,
    QuizElearningCreate, QuizElearningUpdate,
    ReponseQuizCreate,
    CertificatElearningCreate,
    StatistiquesElearningCandidat, StatistiquesElearningProgramme,
    RapportProgressionElearning, FileUploadInfo
)
from ..templates import templates

router = APIRouter()

# === ROUTES WEB ===

@router.get("/", response_class=HTMLResponse, name="elearning_dashboard")
async def elearning_dashboard(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = None,
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Dashboard e-learning"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Forcer l'expiration de tous les objets de la session pour éviter le cache
    session.expire_all()
    
    # Récupérer le paramètre programme de l'URL
    programme_param = request.query_params.get('programme', '').upper()
    
    # Récupérer le programme en cours - SQL direct
    programme_courant = None
    if programme_param:
        try:
            programme_query = text("SELECT * FROM public.programme WHERE code = :code AND actif = true")
            programme_result = session.exec(programme_query.bindparams(code=programme_param)).first()
            if programme_result:
                if hasattr(programme_result, '_mapping'):
                    programme_courant = type('Programme', (), dict(programme_result._mapping))()
                else:
                    programme_courant = type('Programme', (), dict(programme_result))()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du programme {programme_param}: {e}")
    
    # Si programme_id est spécifié, utiliser celui-ci
    if programme_id and not programme_courant:
        try:
            programme_query = text("SELECT * FROM public.programme WHERE id = :id AND actif = true")
            programme_result = session.exec(programme_query.bindparams(id=programme_id)).first()
            if programme_result:
                if hasattr(programme_result, '_mapping'):
                    programme_courant = type('Programme', (), dict(programme_result._mapping))()
                else:
                    programme_courant = type('Programme', (), dict(programme_result))()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du programme {programme_id}: {e}")
    
    # Calculer les stats uniquement pour le programme en cours
    stats_programme = None
    if programme_courant:
        try:
            stats_programme = ElearningService.get_statistiques_programme(session, programme_courant.id, schema_name)
        except Exception as e:
            logging.warning(f"Erreur calcul stats pour programme {programme_courant.id}: {e}")
    
    return templates.TemplateResponse(
        "pages/elearning/dashboard.html",
        {
            "request": request,
            "utilisateur": current_user,
            "stats_programme": stats_programme,
            "programme_courant": programme_courant,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/modules", response_class=HTMLResponse, name="elearning_modules")
async def elearning_modules(
    request: Request,
    programme_id: Optional[int] = Query(None),
    statut: Optional[str] = Query(None),
    difficulte: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Liste des modules e-learning"""
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Forcer l'expiration de tous les objets de la session pour éviter le cache
    session.expire_all()
    
    # Si statut est "tous", on ne filtre pas par statut
    if statut == "tous":
        statut = None
        actif_only = False
    else:
        actif_only = True
    
    # Si difficulte est "tous", on ne filtre pas par difficulté
    if difficulte == "tous":
        difficulte = None
    
    # Récupérer les modules - SQL direct
    modules = []
    try:
        modules = ElearningService.get_modules(session, programme_id, statut, actif_only, difficulte, schema_name)
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des modules e-learning: {e}")
        modules = []
    
    # Récupérer les programmes - SQL direct
    programmes = []
    try:
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY nom")
        programmes_results = session.exec(programmes_query).all()
        for row in programmes_results:
            if hasattr(row, '_mapping'):
                programme = type('Programme', (), dict(row._mapping))()
            else:
                programme = type('Programme', (), dict(row))()
            programmes.append(programme)
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des programmes e-learning: {e}")
        programmes = []
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/elearning/modules.html",
        {
            "request": request,
            "utilisateur": current_user,
            "modules": modules,
            "programmes": programmes,
            "programme_id": programme_id,
            "statut_selected": statut,
            "difficulte_selected": difficulte,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/modules/creer", response_class=HTMLResponse, name="elearning_module_create_form")
async def elearning_module_creer_form(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'un module e-learning"""
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les programmes - SQL direct
    programmes = []
    try:
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY nom")
        programmes_results = session.exec(programmes_query).all()
        for row in programmes_results:
            if hasattr(row, '_mapping'):
                programme = type('Programme', (), dict(row._mapping))()
            else:
                programme = type('Programme', (), dict(row))()
            programmes.append(programme)
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des programmes: {e}")
        programmes = []
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/elearning/module_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programmes": programmes,
            "module": None,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/modules/{module_id}/edit", response_class=HTMLResponse, name="elearning_module_edit_form")
async def elearning_module_edit_form(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire d'édition d'un module e-learning"""
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer le module - SQL direct
    module_query = text(f"SELECT * FROM {schema_name}.module_elearning WHERE id = :module_id")
    module_result = session.exec(module_query.bindparams(module_id=module_id)).first()
    
    if not module_result:
        raise HTTPException(status_code=404, detail="Module non trouvé")
    
    module = type('ModuleElearning', (), dict(module_result._mapping))()
    
    # Récupérer les programmes - SQL direct
    programmes = []
    try:
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY nom")
        programmes_results = session.exec(programmes_query).all()
        for row in programmes_results:
            if hasattr(row, '_mapping'):
                programme = type('Programme', (), dict(row._mapping))()
            else:
                programme = type('Programme', (), dict(row))()
            programmes.append(programme)
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des programmes: {e}")
        programmes = []
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/elearning/module_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programmes": programmes,
            "module": module,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/modules/{module_id}/edit", response_class=HTMLResponse, name="elearning_module_edit")
async def elearning_module_edit(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Traiter la modification d'un module e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Vérifier que le module existe - SQL direct
    module_query = text(f"SELECT * FROM {schema_name}.module_elearning WHERE id = :module_id")
    module_result = session.exec(module_query.bindparams(module_id=module_id)).first()
    
    if not module_result:
        raise HTTPException(status_code=404, detail="Module non trouvé")
    
    module = type('ModuleElearning', (), dict(module_result._mapping))()
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Mettre à jour le module - SQL direct
    try:
        update_query = text(f"""
            UPDATE {schema_name}.module_elearning
            SET titre = :titre,
                description = :description,
                programme_id = :programme_id,
                objectifs = :objectifs,
                prerequis = :prerequis,
                duree_totale_minutes = :duree_totale_minutes,
                difficulte = :difficulte,
                statut = :statut,
                ordre = :ordre,
                actif = :actif
            WHERE id = :module_id
        """)
        
        session.exec(update_query.bindparams(
            module_id=module_id,
            titre=form_data.get("titre"),
            description=form_data.get("description") or None,
            programme_id=int(form_data.get("programme_id")),
            objectifs=form_data.get("objectifs") or None,
            prerequis=form_data.get("prerequis") or None,
            duree_totale_minutes=int(form_data.get("duree_totale_minutes")) if form_data.get("duree_totale_minutes") else None,
            difficulte=form_data.get("difficulte", "facile"),
            statut=form_data.get("statut", "brouillon"),
            ordre=int(form_data.get("ordre", 0)),
            actif=form_data.get("actif") == "true"
        ))
        session.commit()
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = request.url_for("elearning_modules")
        if programme_param:
            redirect_url = str(redirect_url) + f"?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        session.rollback()
        # En cas d'erreur, retourner au formulaire avec un message d'erreur
        programmes = []
        try:
            programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY nom")
            programmes_results = session.exec(programmes_query).all()
            for row in programmes_results:
                if hasattr(row, '_mapping'):
                    programme = type('Programme', (), dict(row._mapping))()
                else:
                    programme = type('Programme', (), dict(row))()
                programmes.append(programme)
        except:
            programmes = []
        
        programme_param = request.query_params.get('programme', '').upper()
        
        return templates.TemplateResponse(
            "pages/elearning/module_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "programmes": programmes,
                "module": module,
                "error": f"Erreur lors de la modification du module: {str(e)}",
                "programme_param": programme_param,
                "schema_name": schema_name
            }
        )

@router.post("/modules/creer", response_class=HTMLResponse, name="elearning_module_create")
async def elearning_module_creer(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Traiter la création d'un module e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Créer le module - SQL direct
    try:
        insert_query = text(f"""
            INSERT INTO {schema_name}.module_elearning
            (titre, description, programme_id, objectifs, prerequis, duree_totale_minutes,
             difficulte, statut, ordre, actif, cree_par_id, cree_le)
            VALUES (:titre, :description, :programme_id, :objectifs, :prerequis, :duree_totale_minutes,
                    :difficulte, :statut, :ordre, :actif, :cree_par_id, CURRENT_TIMESTAMP)
            RETURNING *
        """)
        
        module_result = session.exec(insert_query.bindparams(
            titre=form_data.get("titre"),
            description=form_data.get("description") or None,
            programme_id=int(form_data.get("programme_id")),
            objectifs=form_data.get("objectifs") or None,
            prerequis=form_data.get("prerequis") or None,
            duree_totale_minutes=int(form_data.get("duree_totale_minutes")) if form_data.get("duree_totale_minutes") else None,
            difficulte=form_data.get("difficulte", "facile"),
            statut=form_data.get("statut", "brouillon"),
            ordre=int(form_data.get("ordre", 0)),
            actif=form_data.get("actif") == "true",
            cree_par_id=current_user.id
        )).first()
        
        session.commit()
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = request.url_for("elearning_modules")
        if programme_param:
            redirect_url = str(redirect_url) + f"?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        session.rollback()
        # En cas d'erreur, retourner au formulaire avec un message d'erreur
        programmes = []
        try:
            programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY nom")
            programmes_results = session.exec(programmes_query).all()
            for row in programmes_results:
                if hasattr(row, '_mapping'):
                    programme = type('Programme', (), dict(row._mapping))()
                else:
                    programme = type('Programme', (), dict(row))()
                programmes.append(programme)
        except:
            programmes = []
        
        programme_param = request.query_params.get('programme', '').upper()
        
        return templates.TemplateResponse(
            "pages/elearning/module_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "programmes": programmes,
                "module": None,
                "error": f"Erreur lors de la création du module: {str(e)}",
                "programme_param": programme_param,
                "schema_name": schema_name
            }
        )

@router.get("/modules/{module_id}", response_class=HTMLResponse, name="elearning_module_detail")
async def elearning_module_detail(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Détail d'un module e-learning"""
    schema_name = get_schema_from_request(request) or 'acd'
    logging.info(f"🔍 [elearning_module_detail] schema_name = {schema_name}, module_id = {module_id}, URL = {request.url}")
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Forcer l'expiration de tous les objets de la session pour éviter le cache
    session.expire_all()
    
    # Récupérer le module - SQL direct avec préfixe explicite du schéma
    # Utiliser une variable pour s'assurer que schema_name est bien utilisé
    query_str = f"SELECT * FROM {schema_name}.module_elearning WHERE id = :module_id"
    logging.info(f"🔍 [elearning_module_detail] query_str = {query_str}")
    module_query = text(query_str)
    module_result = session.exec(module_query.bindparams(module_id=module_id)).first()
    
    if not module_result:
        raise HTTPException(status_code=404, detail="Module non trouvé")
    
    module = type('ModuleElearning', (), dict(module_result._mapping))()
    
    # Vérifier d'abord si des associations existent dans module_ressource
    check_associations_query = text(f"SELECT COUNT(*) as count FROM {schema_name}.module_ressource WHERE module_id = :module_id")
    associations_count = session.exec(check_associations_query.bindparams(module_id=module_id)).first()
    if associations_count:
        count = dict(associations_count._mapping).get('count', 0) if hasattr(associations_count, '_mapping') else associations_count.count if hasattr(associations_count, 'count') else 0
        logging.info(f"🔍 [elearning_module_detail] Nombre d'associations trouvées dans module_ressource: {count}")
    
    # Récupérer les ressources du module avec leurs informations de liaison - SQL direct avec préfixe explicite du schéma
    ressources_table = f"{schema_name}.ressource_elearning"
    module_ressource_table = f"{schema_name}.module_ressource"
    ressources_query = text(f"""
        SELECT r.*, mr.ordre as module_ordre, mr.obligatoire
        FROM {ressources_table} r
        INNER JOIN {module_ressource_table} mr ON r.id = mr.ressource_id
        WHERE mr.module_id = :module_id
        ORDER BY mr.ordre
    """)
    
    logging.info(f"🔍 [elearning_module_detail] Requête ressources: {ressources_query}")
    logging.info(f"🔍 [elearning_module_detail] module_id: {module_id}, schema_name: {schema_name}")
    
    try:
        ressources_results = session.exec(ressources_query.bindparams(module_id=module_id)).all()
        logging.info(f"🔍 [elearning_module_detail] Nombre de ressources trouvées: {len(ressources_results)}")
    except Exception as e:
        logging.error(f"❌ [elearning_module_detail] Erreur lors de la récupération des ressources: {e}", exc_info=True)
        ressources_results = []
    
    # Transformer les résultats pour inclure les informations de liaison
    ressources = []
    for row in ressources_results:
        if hasattr(row, '_mapping'):
            ressource_dict = dict(row._mapping)
        else:
            ressource_dict = dict(row)
        
        ressource_data = type('RessourceElearning', (), ressource_dict)()
        # Ajouter les propriétés de liaison
        ressource_data.module_ordre = ressource_dict.get('module_ordre', 0)
        ressource_data.obligatoire = ressource_dict.get('obligatoire', False)
        ressources.append(ressource_data)
        logging.info(f"🔍 [elearning_module_detail] Ressource ajoutée: ID={ressource_data.id}, titre={ressource_data.titre}")
    
    logging.info(f"🔍 [elearning_module_detail] Total ressources dans la liste: {len(ressources)}")
    
    programme_param = request.query_params.get('programme', '').upper()
    
    # Récupérer les programmes pour afficher le nom du programme
    programmes = []
    try:
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY nom")
        programmes_results = session.exec(programmes_query).all()
        for row in programmes_results:
            if hasattr(row, '_mapping'):
                programme = type('Programme', (), dict(row._mapping))()
            else:
                programme = type('Programme', (), dict(row))()
            programmes.append(programme)
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des programmes: {e}")
        programmes = []
    
    return templates.TemplateResponse(
        "pages/elearning/module_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "module": module,
            "ressources": ressources,
            "programmes": programmes,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/ressources/{ressource_id}/start", response_class=HTMLResponse, name="elearning_start_ressource")
async def start_ressource(
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session)
):
    """Démarrer une ressource e-learning"""
    ressource = session.get(RessourceElearning, ressource_id)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    # Récupérer l'inscription de l'utilisateur (si c'est un candidat)
    inscription = None
    # NOTE: Le modèle Inscription a été supprimé. Utiliser directement le candidat.
    if current_user.type_utilisateur == "candidat":
        # inscription = session.exec(
        #     select(Inscription).where(Inscription.candidat_id == current_user.id)
        # ).first()
        candidat = session.exec(
            select(Candidat).where(Candidat.email == current_user.email)
        ).first()
    
    return templates.TemplateResponse(
        "pages/elearning/ressource_player.html",
        {
            "request": request,
            "utilisateur": current_user,
            "ressource": ressource,
            "inscription": inscription
        }
    )

# Routes pour la gestion des ressources
@router.get("/ressources/creer", response_class=HTMLResponse, name="elearning_ressource_creer_form")
async def elearning_ressource_creer_form(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session)
):
    """Formulaire de création d'une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Récupérer le module_id depuis les paramètres de requête
    module_id = request.query_params.get("module_id")
    return_url = request.query_params.get("return_url")
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/elearning/ressource_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "ressource": None,  # Pas de ressource existante
            "module_id": module_id,
            "return_url": return_url,
            "programme_param": programme_param
        }
    )

@router.post("/ressources/creer", response_class=HTMLResponse, name="elearning_ressource_create")
async def elearning_ressource_creer(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    print("🔥 ROUTE APPELÉE: elearning_ressource_creer")
    """
    Traiter la création de ressources e-learning :
    - Crée une ressource PAR type présent dans le formulaire (video/document/audio/lien)
    - Pour chaque type : prend soit un fichier uploadé, soit une URL, soit les deux.
    """
    print("🚀 === DÉBUT elearning_ressource_creer ===")
    print(f"👤 Utilisateur: {current_user.nom_complet} ({current_user.role})")
    
    # --- Sécurité
    if current_user.role not in {"administrateur", "responsable_programme", "formateur"}:
        print("❌ Accès refusé - rôle insuffisant")
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    print("✅ Autorisation OK")

    # --- Form data
    print("📝 Récupération des données du formulaire...")
    form_data = await request.form()

    try:
        dbg = settings.DEBUG
    except Exception:
        dbg = False
    
    # Logging détaillé de tous les champs du formulaire
    print(f"🔍 Clés du formulaire: {list(form_data.keys())}")
    print(f"🔍 Nombre total de champs: {len(form_data)}")
    
    # Afficher tous les champs et leurs valeurs (sauf les fichiers)
    for key, value in form_data.items():
        if hasattr(value, 'filename'):
            print(f"  📁 {key}: fichier = {value.filename if value.filename else 'vide'}")
        else:
            print(f"  📝 {key}: {str(value)[:100] if value else 'vide'}")
    
    # Récupérer le programme depuis le formulaire si présent, sinon depuis la requête
    programme_from_form = form_data.get("programme")
    programme_param = None
    if programme_from_form:
        programme_param = str(programme_from_form).upper()
        schema_name = programme_from_form.lower()
        schema_routing_service.set_schema(schema_name)
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        print(f"✅ Schéma mis à jour depuis le formulaire: {schema_name}")
    else:
        # Récupérer depuis la requête si pas dans le formulaire
        programme_param = request.query_params.get('programme', '').upper() or None

    # Helpers
    def to_int(val, default=None):
        try:
            return int(val) if val not in (None, "", "None") else default
        except Exception:
            return default

    def to_bool_on(val):
        # checkboxes renvoient "on" si cochés
        return str(val).lower() == "on"

    # Champs transverses
    module_id = to_int(form_data.get("module_id"))
    return_url = form_data.get("return_url")
    titre_base = (form_data.get("titre") or "").strip() or None
    description = (form_data.get("description") or "").strip() or None
    duree_minutes = to_int(form_data.get("duree_minutes"))
    difficulte = (form_data.get("difficulte") or "facile").strip()
    tags = (form_data.get("tags") or None)
    ordre = to_int(form_data.get("ordre"), 0)
    actif = to_bool_on(form_data.get("actif"))
    obligatoire = to_bool_on(form_data.get("obligatoire"))

    # Définition des types gérés
    TYPES = ("video", "document", "audio", "lien")
    print(f"🎯 Types gérés: {TYPES}")

    # Collecte de ce qui est réellement présent
    # Pour chaque type, on regarde :
    #  - un fichier présent ? champ 'fichier_{type}'
    #  - une URL présente ? champ 'url_contenu_{type}'
    print("🔍 Analyse des champs présents...")
    presence = {}
    uploaded_files = {}
    urls_candidates = {}

    for t in TYPES:
        f_key = f"fichier_{t}"
        u_key = f"url_contenu_{t}"

        upload = form_data.get(f_key)
        has_file = bool(getattr(upload, "filename", None))
        url_val = (form_data.get(u_key) or "").strip()
        has_url = bool(url_val)
        
        print(f"  📁 {t}: fichier={has_file}, URL={has_url}")
        print(f"    🔍 Champ fichier '{f_key}': {upload}")
        print(f"    🔍 Champ URL '{u_key}': '{url_val}'")
        if has_file:
            print(f"    📄 Fichier: {getattr(upload, 'filename', 'N/A')}")
        if has_url:
            print(f"    🔗 URL: {url_val}")

        if has_file or has_url:
            presence[t] = True
            if has_file:
                uploaded_files[t] = upload
            if has_url:
                urls_candidates[t] = url_val

    print(f"📊 Présence détectée: {list(presence.keys())}")
    print(f"📁 Fichiers à uploader: {list(uploaded_files.keys())}")
    print(f"🔗 URLs fournies: {list(urls_candidates.keys())}")

    if not presence:
        print("❌ Aucun contenu détecté - rien à créer")
        programme_param = request.query_params.get('programme', '').upper()
        # Rien à créer
        return templates.TemplateResponse(
            "pages/elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "programme_param": programme_param,
                "error": "Aucun contenu détecté (ni fichier ni URL) dans le formulaire.",
            },
        )

    print(f"🔄 Création d'UNE SEULE ressource avec {len(presence)} type(s) de contenu...")

    # Déterminer le type principal de la ressource
    # Priorité : video > document > audio > lien
    type_principal = None
    if "video" in presence:
        type_principal = "video"
    elif "document" in presence:
        type_principal = "document"
    elif "audio" in presence:
        type_principal = "audio"
    elif "lien" in presence:
        type_principal = "lien"

    print(f"🎯 Type principal de la ressource: {type_principal}")

    # Uploader tous les fichiers détectés
    fichiers_info = {}
    errors: list[str] = []

    for t in TYPES:
        if t not in presence:
            continue
        
        print(f"\n📝 === Upload du type: {t} ===")

        # Upload du fichier si présent
        if t in uploaded_files:
            uploaded_file = uploaded_files[t]
            try:
                print(f"📤 Upload du fichier {t}: {uploaded_file.filename}")
                file_info = await FileUploadService.save_file(
                    uploaded_file,
                    t,  # type logique (video, document, audio)
                    "elearning",  # dossier principal
                    programme_param.lower() if programme_param else None,  # Code du programme
                    module_id,  # ID du module (subfolder_id)
                )
                fichiers_info[t] = {
                    "path": file_info["relative_path"],
                    "nom_original": uploaded_file.filename
                }
                print(f"✅ Fichier {t} uploadé: {file_info['relative_path']}")
            except HTTPException as e:
                print(f"❌ Erreur upload {t}: {e.detail}")
                errors.append(f"Fichier {t}: {e.detail}")
            except Exception as e:
                print(f"❌ Erreur upload {t}: {str(e)}")
                errors.append(f"Fichier {t}: {str(e)}")

    # Si aucun fichier n'a pu être uploadé, on arrête
    if not fichiers_info and not urls_candidates:
        print("❌ Aucun contenu valide - retour au formulaire")
        programme_param = request.query_params.get('programme', '').upper()
        return templates.TemplateResponse(
            "pages/elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "programme_param": programme_param,
                "error": "Aucun contenu valide détecté.",
            },
        )

    # Construire le payload pour UNE SEULE ressource avec tous les contenus
    print(f"📋 Construction du payload pour la ressource unique...")
    kwargs = {
        "titre": titre_base or "Ressource e-learning",
        "description": description,
        "type_ressource": type_principal,
        "duree_minutes": duree_minutes,
        "difficulte": difficulte,
        "tags": tags,
        "ordre": ordre,
        "actif": actif,
    }

    # Remplir tous les champs spécifiques selon les contenus disponibles
    for t in TYPES:
        if t in fichiers_info:
            kwargs[f"fichier_{t}_path"] = fichiers_info[t]["path"]
            kwargs[f"fichier_{t}_nom_original"] = fichiers_info[t]["nom_original"]
        
        if t in urls_candidates:
            kwargs[f"url_contenu_{t}"] = urls_candidates[t]

    # Champs de compatibilité (legacy) - utiliser le contenu principal
    if type_principal in fichiers_info:
        kwargs["fichier_path"] = fichiers_info[type_principal]["path"]
        kwargs["nom_fichier_original"] = fichiers_info[type_principal]["nom_original"]
    elif type_principal in urls_candidates:
        kwargs["url_contenu"] = urls_candidates[type_principal]

    print(f"📝 Données de la ressource: titre={kwargs['titre']}, type={kwargs['type_ressource']}")

    # Création de la ressource unique
    try:
        print(f"💾 Création de la ressource unique...")
        ressource_data = RessourceElearningCreate(**kwargs)
        print(f"✅ Données de ressource validées")
    except Exception as e:
        print(f"❌ Erreur validation ressource: {str(e)}")
        # Nettoyer tous les fichiers uploadés
        for t, info in fichiers_info.items():
            try:
                print(f"🧹 Nettoyage fichier {t}: {info['path']}")
                FileUploadService.delete_file(info["path"])
            except Exception:
                pass
        errors.append(f"Préparation ressource: {str(e)}")
        programme_param = request.query_params.get('programme', '').upper()
        return templates.TemplateResponse(
            "pages/elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "programme_param": programme_param,
                "error": f"Erreur de validation: {str(e)}",
            },
        )

    try:
        print(f"💾 Sauvegarde en base de données...")
        res = ElearningService.create_ressource(session, ressource_data, current_user.id, schema_name)
        created_id = res.id
        print(f"✅ Ressource créée avec l'ID: {created_id}")

        # Association au module si demandé
        if module_id is not None:
            try:
                print(f"🔗 Association au module {module_id}...")
                ElearningService.add_ressource_to_module(
                    session,
                    module_id,
                    res.id,
                    ordre=ordre,
                    obligatoire=obligatoire,
                    schema_name=schema_name
                )
                print(f"✅ Ressource {res.id} associée au module {module_id}")
            except Exception as e:
                print(f"⚠️ Erreur association module: {e}")
                errors.append(f"Association module: {str(e)}")

    except Exception as e:
        print(f"❌ Erreur création ressource: {str(e)}")
        # Nettoyer tous les fichiers uploadés
        for t, info in fichiers_info.items():
            try:
                print(f"🧹 Nettoyage fichier échoué {t}: {info['path']}")
                FileUploadService.delete_file(info["path"])
            except Exception:
                pass
        errors.append(f"Création ressource: {str(e)}")
        programme_param = request.query_params.get('programme', '').upper()
        return templates.TemplateResponse(
            "pages/elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "programme_param": programme_param,
                "error": f"Erreur de création: {str(e)}",
            },
        )

    # --- Bilan & redirection
    print(f"\n📊 === BILAN FINAL ===")
    print(f"✅ Ressource créée: {created_id}")
    print(f"❌ Erreurs: {len(errors)}")
    print(f"📋 ID créé: {created_id}")
    if errors:
        print(f"🚨 Erreurs détaillées: {errors}")
    
    if not created_id:
        print("❌ Aucune ressource créée - retour au formulaire")
        programme_param = request.query_params.get('programme', '').upper()
        # Rien n'a pu être créé : on retourne au formulaire avec erreurs
        return templates.TemplateResponse(
            "pages/elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "programme_param": programme_param,
                "error": "Aucune ressource n'a été créée. " + (" | ".join(errors) if errors else ""),
            },
        )

    # On redirige ; on peut reporter un petit résumé via querystring (facultatif)
    # ex: /elearning/modules?created=3&errors=1
    created_count = 1 if created_id else 0
    error_count = len(errors)
    print(f"🔄 Redirection avec {created_count} créations et {error_count} erreurs")
    
    # Construire l'URL de redirection avec le paramètre programme si disponible
    programme_param = request.query_params.get('programme', '').upper()
    base_url = return_url or "/elearning/modules"
    
    # Ajouter le paramètre programme si présent
    if programme_param:
        separator = "&" if "?" in base_url else "?"
        base_url = f"{base_url}{separator}programme={programme_param}"
    
    # Ajouter les paramètres de résultat
    separator = "&" if "?" in base_url else "?"
    suffix = f"{separator}created={created_count}&errors={error_count}" if (created_count or error_count) else ""
    target = base_url + suffix
    
    print(f"🔄 Redirection vers: {target}")
    return RedirectResponse(url=target, status_code=303)

@router.get("/modules/{module_id}/ressources/{ressource_id}/remove", name="elearning_remove_ressource_from_module")
async def remove_ressource_from_module(
    module_id: int,
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer une ressource d'un module"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        ElearningService.remove_ressource_from_module(session, module_id, ressource_id, schema_name)
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = request.url_for("elearning_module_detail", module_id=module_id)
        if programme_param:
            redirect_url = str(redirect_url) + f"?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")

@router.get("/ressources/{ressource_id}/edit", response_class=HTMLResponse, name="elearning_ressource_edit_form")
async def elearning_ressource_edit_form(
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire d'édition d'une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la ressource - SQL direct
    ressource_query = text(f"SELECT * FROM {schema_name}.ressource_elearning WHERE id = :ressource_id")
    ressource_result = session.exec(ressource_query.bindparams(ressource_id=ressource_id)).first()
    
    if not ressource_result:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    ressource = type('RessourceElearning', (), dict(ressource_result._mapping))()
    
    # Récupérer le module_id depuis les paramètres de requête ou depuis la table de liaison
    module_id = request.query_params.get("module_id")
    return_url = request.query_params.get("return_url")
    
    # Si module_id n'est pas dans les paramètres, le récupérer depuis la table de liaison
    if not module_id:
        module_ressource_query = text(f"SELECT module_id FROM {schema_name}.module_ressource WHERE ressource_id = :ressource_id LIMIT 1")
        module_ressource_result = session.exec(module_ressource_query.bindparams(ressource_id=ressource_id)).first()
        if module_ressource_result:
            if hasattr(module_ressource_result, '_mapping'):
                module_id = dict(module_ressource_result._mapping).get('module_id')
            else:
                module_id = dict(module_ressource_result).get('module_id')
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/elearning/ressource_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "ressource": ressource,
            "module_id": module_id,
            "return_url": return_url,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/ressources/{ressource_id}/edit", response_class=HTMLResponse, name="elearning_ressource_edit")
async def elearning_ressource_edit(
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Traiter la modification d'une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la ressource - SQL direct
    ressource_query = text(f"SELECT * FROM {schema_name}.ressource_elearning WHERE id = :ressource_id")
    ressource_result = session.exec(ressource_query.bindparams(ressource_id=ressource_id)).first()
    
    if not ressource_result:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    ressource = type('RessourceElearning', (), dict(ressource_result._mapping))()
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Déterminer le type de ressource basé sur les champs remplis
    # Priorité : fichiers > URLs > lien
    type_ressource = ressource.type_ressource  # Garder le type existant par défaut
    
    # Vérifier les fichiers uploadés en priorité
    fichiers_presents = []
    if "fichier_video" in form_data and getattr(form_data.get("fichier_video"), "filename", None):
        fichiers_presents.append("video")
    if "fichier_document" in form_data and getattr(form_data.get("fichier_document"), "filename", None):
        fichiers_presents.append("document")
    if "fichier_audio" in form_data and getattr(form_data.get("fichier_audio"), "filename", None):
        fichiers_presents.append("audio")
    
    # Si plusieurs fichiers, utiliser le premier trouvé
    if fichiers_presents:
        type_ressource = fichiers_presents[0]
    # Sinon vérifier les URLs
    elif form_data.get("url_contenu_video"):
        type_ressource = "video"
    elif form_data.get("url_contenu_document"):
        type_ressource = "document"
    elif form_data.get("url_contenu_audio"):
        type_ressource = "audio"
    elif form_data.get("url_contenu_lien"):
        type_ressource = "lien"
    
    # Traiter tous les fichiers uploadés s'ils existent
    fichiers_info = []
    
    # Traiter chaque type de fichier s'il existe
    file_types = ["video", "document", "audio"]
    for file_type in file_types:
        field_name = f"fichier_{file_type}"
        if field_name in form_data:
            candidate = form_data.get(field_name)
            
            if getattr(candidate, "filename", None):
                try:
                    module_id = form_data.get("module_id")
                    programme_param = request.query_params.get('programme', '').upper()
                    print(f"🔍 DEBUG: Fichier {file_type} trouvé: {candidate.filename}")
                    
                    # Supprimer l'ancien fichier s'il existe
                    ancien_fichier_path = None
                    if file_type == "video" and ressource.fichier_video_path:
                        ancien_fichier_path = ressource.fichier_video_path
                    elif file_type == "document" and ressource.fichier_document_path:
                        ancien_fichier_path = ressource.fichier_document_path
                    elif file_type == "audio" and ressource.fichier_audio_path:
                        ancien_fichier_path = ressource.fichier_audio_path
                    
                    if ancien_fichier_path:
                        try:
                            FileUploadService.delete_file(ancien_fichier_path)
                            print(f"🗑️ DEBUG: Ancien fichier {file_type} supprimé: {ancien_fichier_path}")
                        except Exception as e:
                            print(f"⚠️ DEBUG: Erreur lors de la suppression de l'ancien fichier {file_type}: {e}")
                    
                    file_info = await FileUploadService.save_file(
                        candidate,
                        file_type,
                        "elearning",  # dossier principal
                        programme_param.lower() if programme_param else None,  # Code du programme
                        int(module_id) if module_id else None  # ID du module (subfolder_id)
                    )
                    
                    fichiers_info.append({
                        "type": file_type,
                        "filename": candidate.filename,
                        "path": file_info["relative_path"]
                    })
                    
                    print(f"✅ DEBUG: Fichier {file_type} sauvegardé: {file_info['relative_path']}")
                    
                except HTTPException as e:
                    print(f"❌ Erreur de fichier {file_type}: {e.detail}")
                    return templates.TemplateResponse(
                        "pages/elearning/ressource_form.html",
                        {
                            "request": request,
                            "utilisateur": current_user,
                            "ressource": ressource,
                            "module_id": form_data.get("module_id"),
                            "return_url": form_data.get("return_url"),
                            "error": f"Erreur de fichier {file_type}: {e.detail}"
                        }
                    )
    
    # Sélectionner l'URL pertinente selon le type détecté
    url_contenu_selected = None
    if type_ressource == "video":
        url_contenu_selected = form_data.get("url_contenu_video")
    elif type_ressource == "document":
        url_contenu_selected = form_data.get("url_contenu_document")
    elif type_ressource == "audio":
        url_contenu_selected = form_data.get("url_contenu_audio")
    elif type_ressource == "lien":
        url_contenu_selected = form_data.get("url_contenu_lien")
    
    # Préparer les données des fichiers par type pour l'édition
    fichier_video_path = ressource.fichier_video_path
    fichier_video_nom_original = ressource.fichier_video_nom_original
    fichier_document_path = ressource.fichier_document_path
    fichier_document_nom_original = ressource.fichier_document_nom_original
    fichier_audio_path = ressource.fichier_audio_path
    fichier_audio_nom_original = ressource.fichier_audio_nom_original
    
    # Mettre à jour avec les nouveaux fichiers s'ils existent
    for file_info in fichiers_info:
        if file_info["type"] == "video":
            fichier_video_path = file_info["path"]
            fichier_video_nom_original = file_info["filename"]
        elif file_info["type"] == "document":
            fichier_document_path = file_info["path"]
            fichier_document_nom_original = file_info["filename"]
        elif file_info["type"] == "audio":
            fichier_audio_path = file_info["path"]
            fichier_audio_nom_original = file_info["filename"]
    
    # Fonction helper pour convertir les chaînes vides en None
    def get_value_or_none(value):
        """Convertit les chaînes vides en None, garde les autres valeurs"""
        if value is None or value == "":
            return None
        return value
    
    # Mettre à jour la ressource
    ressource_data = RessourceElearningUpdate(
        titre=form_data.get("titre") or None,
        description=get_value_or_none(form_data.get("description")),
        type_ressource=type_ressource,
        
        # URLs pour chaque type
        url_contenu_video=get_value_or_none(form_data.get("url_contenu_video")),
        url_contenu_document=get_value_or_none(form_data.get("url_contenu_document")),
        url_contenu_audio=get_value_or_none(form_data.get("url_contenu_audio")),
        url_contenu_lien=get_value_or_none(form_data.get("url_contenu_lien")),
        
        # Fichiers pour chaque type
        fichier_video_path=fichier_video_path,
        fichier_video_nom_original=fichier_video_nom_original,
        fichier_document_path=fichier_document_path,
        fichier_document_nom_original=fichier_document_nom_original,
        fichier_audio_path=fichier_audio_path,
        fichier_audio_nom_original=fichier_audio_nom_original,
        
        # Champs généraux
        url_contenu=get_value_or_none(url_contenu_selected),
        fichier_path=None,
        
        duree_minutes=int(form_data.get("duree_minutes")) if form_data.get("duree_minutes") else None,
        difficulte=form_data.get("difficulte", "facile"),
        tags=get_value_or_none(form_data.get("tags")),
        ordre=int(form_data.get("ordre", 0)),
        actif=form_data.get("actif") == "on"
    )
    
    try:
        updated_ressource = ElearningService.update_ressource(session, ressource_id, ressource_data, schema_name)
        
        # Récupérer le module_id depuis le formulaire ou depuis la table de liaison
        module_id = form_data.get("module_id")
        if not module_id:
            # Si module_id n'est pas dans le formulaire, le récupérer depuis la table de liaison
            module_ressource_query = text(f"SELECT module_id FROM {schema_name}.module_ressource WHERE ressource_id = :ressource_id LIMIT 1")
            module_ressource_result = session.exec(module_ressource_query.bindparams(ressource_id=ressource_id)).first()
            if module_ressource_result:
                if hasattr(module_ressource_result, '_mapping'):
                    module_id = dict(module_ressource_result._mapping).get('module_id')
                else:
                    module_id = dict(module_ressource_result).get('module_id')
        
        programme_param = request.query_params.get('programme', '').upper()
        
        # Rediriger vers la page de détail du module avec l'ancre #ressources si module_id existe
        if module_id:
            redirect_url = request.url_for("elearning_module_detail", module_id=int(module_id))
            if programme_param:
                redirect_url = str(redirect_url) + f"?programme={programme_param}"
            redirect_url = str(redirect_url) + "#ressources"
        else:
            # Sinon, rediriger vers la liste des modules
            redirect_url = request.url_for("elearning_modules")
            if programme_param:
                redirect_url = str(redirect_url) + f"?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        # En cas d'erreur, faire un rollback de la session
        session.rollback()
        programme_param = request.query_params.get('programme', '').upper()
        # Retourner au formulaire avec un message d'erreur
        return templates.TemplateResponse(
            "pages/elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": ressource,
                "error": f"Erreur lors de la modification de la ressource: {str(e)}",
                "programme_param": programme_param,
                "schema_name": schema_name
            }
        )

# Route pour les statistiques e-learning
@router.get("/statistiques", response_class=HTMLResponse, name="elearning_statistiques")
async def elearning_statistiques(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session)
):
    """Page des statistiques e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Récupérer les statistiques globales
    stats_globales = ElearningService.get_statistiques_globales(session)
    
    # Récupérer les statistiques par programme
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    stats_par_programme = []
    for programme in programmes:
        stats_prog = ElearningService.get_statistiques_programme(session, programme.id)
        stats_par_programme.append({
            "programme": programme,
            "nb_modules": stats_prog.nb_modules,
            "nb_ressources": stats_prog.nb_ressources,
            "nb_candidats": stats_prog.nb_candidats,
            "temps_moyen": stats_prog.temps_moyen_minutes,
            "taux_completion": stats_prog.taux_completion,
            "score_moyen": stats_prog.score_moyen
        })
    
    # Top modules et candidats
    top_modules = ElearningService.get_top_modules(session, limit=5)
    top_candidats = ElearningService.get_top_candidats(session, limit=5)
    
    # Statistiques par type de ressource
    stats_ressources = ElearningService.get_stats_ressources_par_type(session)
    
    return templates.TemplateResponse(
        "pages/elearning/statistiques.html",
        {
            "request": request,
            "utilisateur": current_user,
            "stats_globales": stats_globales,
            "stats_par_programme": stats_par_programme,
            "programmes": programmes,
            "top_modules": top_modules,
            "top_candidats": top_candidats,
            "stats_ressources": stats_ressources
        }
    )

@router.get("/candidat/{candidat_id}", response_class=HTMLResponse, name="elearning_candidat_progression")
async def elearning_candidat_progression(
    candidat_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Progression e-learning d'un candidat"""
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer le candidat - SQL direct
    candidat_query = text(f"SELECT * FROM {schema_name}.candidat WHERE id = :candidat_id")
    candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
    
    if not candidat_result:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")
    
    candidat = type('Candidat', (), dict(candidat_result._mapping))()
    
    # Récupérer les statistiques du candidat
    try:
        stats = ElearningService.get_statistiques_candidat(session, candidat_id, schema_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Récupérer la progression détaillée
    progressions = ElearningService.get_progression_candidat(session, candidat_id, schema_name)
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/elearning/candidat_progression.html",
        {
            "request": request,
            "utilisateur": current_user,
            "candidat": candidat,
            "stats": stats,
            "progressions": progressions,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

