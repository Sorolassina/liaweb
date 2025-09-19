# app/routers/elearning.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi import UploadFile, File, Form
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user
from app_lia_web.app.models.base import User, Programme, Inscription
from app_lia_web.app.models.elearning import (
    RessourceElearning, ModuleElearning, ProgressionElearning,
    ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning,
    ModuleRessource
)
from app_lia_web.app.services.elearning_service import ElearningService
from app_lia_web.app.services.file_upload_service import FileUploadService
from app_lia_web.app.schemas.elearning import (
    RessourceElearningCreate, RessourceElearningUpdate, RessourceElearningResponse,
    ModuleElearningCreate, ModuleElearningUpdate, ModuleElearningResponse,
    ProgressionElearningCreate, ProgressionElearningUpdate, ProgressionElearningResponse,
    ObjectifElearningCreate, ObjectifElearningUpdate, ObjectifElearningResponse,
    QuizElearningCreate, QuizElearningUpdate, QuizElearningResponse,
    ReponseQuizCreate, ReponseQuizResponse,
    CertificatElearningCreate, CertificatElearningResponse,
    StatistiquesElearningCandidat, StatistiquesElearningProgramme,
    RapportProgressionElearning, FileUploadInfo
)
from app_lia_web.app.templates import templates

router = APIRouter()

# === ROUTES WEB ===

@router.get("/", response_class=HTMLResponse)
async def elearning_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Dashboard e-learning"""
    # Récupérer les statistiques générales
    programmes = session.exec(
        select(Programme).where(Programme.actif == True)
    ).all()
    
    print(f"🔍 DEBUG DASHBOARD: {len(programmes)} programmes actifs trouvés")
    for p in programmes:
        print(f"  - Programme {p.id}: {p.nom}")
    
    stats_programmes = []
    for programme in programmes:
        try:
            print(f"🔍 DEBUG: Calcul des stats pour programme {programme.id} ({programme.nom})")
            stats = ElearningService.get_statistiques_programme(session, programme.id)
            print(f"✅ DEBUG: Stats calculées - inscrits: {stats.candidats_inscrits}, actifs: {stats.candidats_actifs}, completion: {stats.taux_completion}%")
            stats_programmes.append(stats)
        except Exception as e:
            print(f"❌ DEBUG: Erreur pour programme {programme.id}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"🔍 DEBUG: {len(stats_programmes)} programmes avec stats valides")
    
    return templates.TemplateResponse(
        "elearning/dashboard.html",
        {
            "request": request,
            "utilisateur": current_user,
            "stats_programmes": stats_programmes
        }
    )

@router.get("/modules", response_class=HTMLResponse)
async def elearning_modules(
    request: Request,
    programme_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Liste des modules e-learning"""
    modules = ElearningService.get_modules(session, programme_id)
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    
    return templates.TemplateResponse(
        "elearning/modules.html",
        {
            "request": request,
            "utilisateur": current_user,
            "modules": modules,
            "programmes": programmes,
            "programme_id": programme_id
        }
    )

@router.get("/modules/creer", response_class=HTMLResponse)
async def elearning_module_creer_form(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Formulaire de création d'un module e-learning"""
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    
    return templates.TemplateResponse(
        "elearning/module_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programmes": programmes,
            "module": None  # Pas de module existant
        }
    )

@router.get("/modules/{module_id}/edit", response_class=HTMLResponse, name="elearning_module_edit_form")
async def elearning_module_edit_form(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Formulaire d'édition d'un module e-learning"""
    module = session.get(ModuleElearning, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module non trouvé")
    
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    
    return templates.TemplateResponse(
        "elearning/module_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programmes": programmes,
            "module": module  # Module existant à modifier
        }
        )

@router.post("/modules/{module_id}/edit", response_class=HTMLResponse, name="elearning_module_edit")
async def elearning_module_edit(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Traiter la modification d'un module e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Vérifier que le module existe
    module = session.get(ModuleElearning, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module non trouvé")
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Mettre à jour le module
    module_data = ModuleElearningUpdate(
        titre=form_data.get("titre"),
        description=form_data.get("description"),
        programme_id=int(form_data.get("programme_id")),
        objectifs=form_data.get("objectifs"),
        prerequis=form_data.get("prerequis"),
        duree_totale_minutes=int(form_data.get("duree_totale_minutes")) if form_data.get("duree_totale_minutes") else None,
        difficulte=form_data.get("difficulte", "facile"),
        statut=form_data.get("statut", "brouillon"),
        ordre=int(form_data.get("ordre", 0)),
        actif=form_data.get("actif") == "true"
    )
    
    try:
        updated_module = ElearningService.update_module(session, module_id, module_data)
        # Rediriger vers la liste des modules
        return RedirectResponse(url="/elearning/modules", status_code=303)
    except Exception as e:
        # En cas d'erreur, retourner au formulaire avec un message d'erreur
        programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
        return templates.TemplateResponse(
            "elearning/module_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "programmes": programmes,
                "module": module,
                "error": f"Erreur lors de la modification du module: {str(e)}"
            }
        )

@router.post("/modules/creer", response_class=HTMLResponse)
async def elearning_module_creer(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Traiter la création d'un module e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Créer le module
    module_data = ModuleElearningCreate(
        titre=form_data.get("titre"),
        description=form_data.get("description"),
        programme_id=int(form_data.get("programme_id")),
        objectifs=form_data.get("objectifs"),
        prerequis=form_data.get("prerequis"),
        duree_totale_minutes=int(form_data.get("duree_totale_minutes")) if form_data.get("duree_totale_minutes") else None,
        difficulte=form_data.get("difficulte", "facile"),
        statut=form_data.get("statut", "brouillon"),
        ordre=int(form_data.get("ordre", 0)),
        actif=form_data.get("actif") == "true"
    )
    
    try:
        module = ElearningService.create_module(session, module_data, current_user.id)
        # Rediriger vers la liste des modules
        return RedirectResponse(url="/elearning/modules", status_code=303)
    except Exception as e:
        # En cas d'erreur, retourner au formulaire avec un message d'erreur
        programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
        return templates.TemplateResponse(
            "elearning/module_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "programmes": programmes,
                "module": None,
                "error": f"Erreur lors de la création du module: {str(e)}"
            }
        )

@router.get("/modules/{module_id}", response_class=HTMLResponse)
async def elearning_module_detail(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Détail d'un module e-learning"""
    module = session.get(ModuleElearning, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module non trouvé")
    
    # Récupérer les ressources du module avec leurs informations de liaison
    ressources_query = session.exec(
        select(RessourceElearning, ModuleRessource)
        .join(ModuleRessource, RessourceElearning.id == ModuleRessource.ressource_id)
        .where(ModuleRessource.module_id == module_id)
        .order_by(ModuleRessource.ordre)
    ).all()
    
    # Transformer les résultats pour inclure les informations de liaison
    ressources = []
    for ressource, module_ressource in ressources_query:
        # Créer un dictionnaire avec les propriétés de la ressource et de la liaison
        ressource_data = {
            'id': ressource.id,
            'titre': ressource.titre,
            'description': ressource.description,
            'type_ressource': ressource.type_ressource,
            'url_contenu': ressource.url_contenu,
            'fichier_path': ressource.fichier_path,
            'duree_minutes': ressource.duree_minutes,
            'difficulte': ressource.difficulte,
            'tags': ressource.tags,
            'actif': ressource.actif,
            'ordre': ressource.ordre,
            'cree_le': ressource.cree_le,
            'cree_par_id': ressource.cree_par_id,
            # Propriétés de liaison
            'module_ordre': module_ressource.ordre,
            'obligatoire': module_ressource.obligatoire
        }
        ressources.append(ressource_data)
    
    return templates.TemplateResponse(
        "elearning/module_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "module": module,
            "ressources": ressources
        }
    )

@router.get("/ressources/{ressource_id}/start", response_class=HTMLResponse)
async def start_ressource(
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Démarrer une ressource e-learning"""
    ressource = session.get(RessourceElearning, ressource_id)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    # Récupérer l'inscription de l'utilisateur (si c'est un candidat)
    inscription = None
    if current_user.type_utilisateur == "candidat":
        inscription = session.exec(
            select(Inscription).where(Inscription.candidat_id == current_user.id)
        ).first()
    
    return templates.TemplateResponse(
        "elearning/ressource_player.html",
        {
            "request": request,
            "utilisateur": current_user,
            "ressource": ressource,
            "inscription": inscription
        }
    )

# Route pour servir les fichiers uploadés
@router.get("/media/{file_path:path}")
async def serve_uploaded_file(file_path: str):
    """Servir les fichiers uploadés"""
    full_path = Path("media") / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    # Vérifier que le fichier est dans le dossier elearning
    if not str(full_path).startswith("media/elearning/"):
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return FileResponse(full_path)

# Routes pour la gestion des ressources
@router.get("/ressources/creer", response_class=HTMLResponse)
async def elearning_ressource_creer_form(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Formulaire de création d'une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Récupérer le module_id depuis les paramètres de requête
    module_id = request.query_params.get("module_id")
    return_url = request.query_params.get("return_url")
    
    return templates.TemplateResponse(
        "elearning/ressource_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "ressource": None,  # Pas de ressource existante
            "module_id": module_id,
            "return_url": return_url
        }
    )

@router.post("/ressources/creer", response_class=HTMLResponse)
async def elearning_ressource_creer(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Traiter la création d'une ressource e-learning avec upload de fichier"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Récupérer le fichier uploadé si présent
    uploaded_file = None
    file_info = None
    fichier_path = None
    
    # Vérifier s'il y a un fichier uploadé
    print(f"🔍 DEBUG: Form data keys: {list(form_data.keys())}")
    
    if "fichier" in form_data:
        uploaded_file = form_data["fichier"]
        print(f"🔍 DEBUG: Fichier trouvé: {uploaded_file.filename if uploaded_file else 'None'}")
        
        if uploaded_file and uploaded_file.filename:
            try:
                # Sauvegarder le fichier
                resource_type = form_data.get("type_ressource")
                module_id = form_data.get("module_id")
                
                print(f"🔍 DEBUG: Type ressource: {resource_type}, Module ID: {module_id}")
                
                file_info = await FileUploadService.save_file(
                    uploaded_file, 
                    resource_type, 
                    int(module_id) if module_id else None
                )
                fichier_path = file_info["relative_path"]
                print(f"✅ DEBUG: Fichier sauvegardé: {fichier_path}")
                
            except HTTPException as e:
                print(f"❌ DEBUG: Erreur fichier: {e.detail}")
                # Retourner au formulaire avec l'erreur de fichier
                return templates.TemplateResponse(
                    "elearning/ressource_form.html",
                    {
                        "request": request,
                        "utilisateur": current_user,
                        "ressource": None,
                        "module_id": form_data.get("module_id"),
                        "return_url": form_data.get("return_url"),
                        "error": f"Erreur de fichier: {e.detail}"
                    }
                )
        else:
            print("🔍 DEBUG: Aucun fichier valide trouvé")
    else:
        print("🔍 DEBUG: Aucun fichier dans la requête")
    
    # Créer la ressource
    ressource_data = RessourceElearningCreate(
        titre=form_data.get("titre"),
        description=form_data.get("description"),
        type_ressource=form_data.get("type_ressource"),
        url_contenu=form_data.get("url_contenu") if not fichier_path else None,
        fichier_path=fichier_path,
        duree_minutes=int(form_data.get("duree_minutes")) if form_data.get("duree_minutes") else None,
        difficulte=form_data.get("difficulte", "facile"),
        tags=form_data.get("tags"),
        ordre=int(form_data.get("ordre", 0)),
        actif=form_data.get("actif") == "on"
    )
    
    try:
        ressource = ElearningService.create_ressource(session, ressource_data, current_user.id)
        
        # Si un module_id est fourni, associer automatiquement la ressource au module
        module_id = form_data.get("module_id")
        if module_id:
            try:
                ElearningService.add_ressource_to_module(
                    session, 
                    int(module_id), 
                    ressource.id, 
                    ordre=int(form_data.get("ordre", 0)),
                    obligatoire=form_data.get("obligatoire") == "on"
                )
            except Exception as e:
                # Si l'association échoue, on continue quand même
                pass
        
        # Rediriger vers l'URL de retour ou la liste des modules
        return_url = form_data.get("return_url")
        if return_url:
            return RedirectResponse(url=return_url, status_code=303)
        else:
            return RedirectResponse(url="/elearning/modules", status_code=303)
            
    except Exception as e:
        # En cas d'erreur, supprimer le fichier uploadé s'il existe
        if file_info:
            FileUploadService.delete_file(file_info["relative_path"])
        
        # Retourner au formulaire avec un message d'erreur
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": form_data.get("module_id"),
                "return_url": form_data.get("return_url"),
                "error": f"Erreur lors de la création de la ressource: {str(e)}"
            }
        )

@router.get("/ressources/{ressource_id}/edit", response_class=HTMLResponse)
async def elearning_ressource_edit_form(
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Formulaire d'édition d'une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    ressource = session.get(RessourceElearning, ressource_id)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    return templates.TemplateResponse(
        "elearning/ressource_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "ressource": ressource
        }
    )

@router.post("/ressources/{ressource_id}/edit", response_class=HTMLResponse)
async def elearning_ressource_edit(
    ressource_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Traiter la modification d'une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    ressource = session.get(RessourceElearning, ressource_id)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    # Mettre à jour la ressource
    ressource_data = RessourceElearningUpdate(
        titre=form_data.get("titre"),
        description=form_data.get("description"),
        type_ressource=form_data.get("type_ressource"),
        url_contenu=form_data.get("url_contenu"),
        duree_minutes=int(form_data.get("duree_minutes")) if form_data.get("duree_minutes") else None,
        difficulte=form_data.get("difficulte", "facile"),
        tags=form_data.get("tags"),
        ordre=int(form_data.get("ordre", 0)),
        actif=form_data.get("actif") == "on"
    )
    
    try:
        updated_ressource = ElearningService.update_ressource(session, ressource_id, ressource_data)
        # Rediriger vers la liste des modules
        return RedirectResponse(url="/elearning/modules", status_code=303)
    except Exception as e:
        # En cas d'erreur, retourner au formulaire avec un message d'erreur
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": ressource,
                "error": f"Erreur lors de la modification de la ressource: {str(e)}"
            }
        )

# Route pour les statistiques e-learning
@router.get("/statistiques", response_class=HTMLResponse)
async def elearning_statistiques(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
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
        "elearning/statistiques.html",
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

@router.get("/candidat/{inscription_id}", response_class=HTMLResponse)
async def elearning_candidat_progression(
    inscription_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Progression e-learning d'un candidat"""
    inscription = session.get(Inscription, inscription_id)
    if not inscription:
        raise HTTPException(status_code=404, detail="Inscription non trouvée")
    
    # Récupérer les statistiques du candidat
    try:
        stats = ElearningService.get_statistiques_candidat(session, inscription_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Récupérer la progression détaillée
    progressions = ElearningService.get_progression_candidat(session, inscription_id)
    
    return templates.TemplateResponse(
        "elearning/candidat_progression.html",
        {
            "request": request,
            "utilisateur": current_user,
            "inscription": inscription,
            "stats": stats,
            "progressions": progressions
        }
    )

# === ROUTES API ===

# Ressources
@router.post("/api/ressources", response_model=RessourceElearningResponse)
async def create_ressource(
    ressource_data: RessourceElearningCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Créer une ressource e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return ElearningService.create_ressource(session, ressource_data, current_user.id)

@router.get("/api/ressources", response_model=List[RessourceElearningResponse])
async def get_ressources(
    programme_id: Optional[int] = None,
    actif_only: bool = True,
    session: Session = Depends(get_session)
):
    """Récupérer les ressources e-learning"""
    return ElearningService.get_ressources(session, programme_id, actif_only)

@router.put("/api/ressources/{ressource_id}", response_model=RessourceElearningResponse)
async def update_ressource(
    ressource_id: int,
    ressource_data: RessourceElearningUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Mettre à jour une ressource"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    ressource = ElearningService.update_ressource(session, ressource_id, ressource_data)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource non trouvée")
    
    return ressource

# Modules
@router.post("/api/modules", response_model=ModuleElearningResponse)
async def create_module(
    module_data: ModuleElearningCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Créer un module e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return ElearningService.create_module(session, module_data, current_user.id)

@router.get("/api/modules", response_model=List[ModuleElearningResponse])
async def get_modules(
    programme_id: Optional[int] = None,
    statut: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Récupérer les modules e-learning"""
    return ElearningService.get_modules(session, programme_id, statut)

@router.post("/api/modules/{module_id}/ressources/{ressource_id}")
async def add_ressource_to_module(
    module_id: int,
    ressource_id: int,
    ordre: int = 0,
    obligatoire: bool = True,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Ajouter une ressource à un module"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    success = ElearningService.add_ressource_to_module(session, module_id, ressource_id, ordre, obligatoire)
    if not success:
        raise HTTPException(status_code=400, detail="Impossible d'ajouter la ressource")
    
    return {"message": "Ressource ajoutée au module"}

@router.delete("/api/modules/{module_id}/ressources/{ressource_id}")
async def remove_ressource_from_module(
    module_id: int,
    ressource_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Retirer une ressource d'un module"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    success = ElearningService.remove_ressource_from_module(session, module_id, ressource_id)
    if not success:
        raise HTTPException(status_code=400, detail="Impossible de retirer la ressource")
    
    return {"message": "Ressource retirée du module"}

# Progression
@router.post("/api/progression/start")
async def start_ressource(
    inscription_id: int,
    ressource_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Commencer une ressource"""
    progression = ElearningService.start_ressource(session, inscription_id, ressource_id)
    if not progression:
        raise HTTPException(status_code=400, detail="Impossible de commencer la ressource")
    
    return progression

@router.put("/api/progression/{progression_id}")
async def update_progression(
    progression_id: int,
    temps_ajoute: int,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Mettre à jour la progression"""
    progression = ElearningService.update_progression(session, progression_id, temps_ajoute, notes)
    if not progression:
        raise HTTPException(status_code=404, detail="Progression non trouvée")
    
    return progression

@router.post("/api/progression/{progression_id}/complete")
async def complete_ressource(
    progression_id: int,
    score: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Marquer une ressource comme terminée"""
    progression = ElearningService.complete_ressource(session, progression_id, score)
    if not progression:
        raise HTTPException(status_code=404, detail="Progression non trouvée")
    
    return progression

@router.get("/api/progression/candidat/{inscription_id}", response_model=List[ProgressionElearningResponse])
async def get_candidat_progression(
    inscription_id: int,
    session: Session = Depends(get_session)
):
    """Récupérer la progression d'un candidat"""
    return ElearningService.get_progression_candidat(session, inscription_id)

# Quiz
@router.post("/api/quiz", response_model=QuizElearningResponse)
async def create_quiz(
    quiz_data: QuizElearningCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Créer un quiz"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return ElearningService.create_quiz(session, quiz_data)

@router.post("/api/quiz/reponse", response_model=ReponseQuizResponse)
async def submit_quiz_response(
    reponse_data: ReponseQuizCreate,
    session: Session = Depends(get_session)
):
    """Soumettre une réponse à un quiz"""
    try:
        return ElearningService.submit_quiz_response(session, reponse_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Objectifs
@router.post("/api/objectifs", response_model=ObjectifElearningResponse)
async def create_objectif(
    objectif_data: ObjectifElearningCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Créer un objectif e-learning"""
    if current_user.role not in ["administrateur", "responsable_programme"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return ElearningService.create_objectif(session, objectif_data)

@router.get("/api/objectifs/check/{inscription_id}/{objectif_id}")
async def check_objectif_atteint(
    inscription_id: int,
    objectif_id: int,
    session: Session = Depends(get_session)
):
    """Vérifier si un objectif est atteint"""
    atteint = ElearningService.check_objectif_atteint(session, inscription_id, objectif_id)
    return {"objectif_atteint": atteint}

# Statistiques
@router.get("/api/statistiques/candidat/{inscription_id}", response_model=StatistiquesElearningCandidat)
async def get_statistiques_candidat(
    inscription_id: int,
    session: Session = Depends(get_session)
):
    """Obtenir les statistiques d'un candidat"""
    try:
        return ElearningService.get_statistiques_candidat(session, inscription_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/api/statistiques/programme/{programme_id}", response_model=StatistiquesElearningProgramme)
async def get_statistiques_programme(
    programme_id: int,
    session: Session = Depends(get_session)
):
    """Obtenir les statistiques d'un programme"""
    try:
        return ElearningService.get_statistiques_programme(session, programme_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Certificats
@router.post("/api/certificats", response_model=CertificatElearningResponse)
async def generate_certificat(
    inscription_id: int,
    module_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Générer un certificat de completion"""
    if current_user.role not in ["administrateur", "responsable_programme"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    try:
        return ElearningService.generate_certificat(session, inscription_id, module_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
