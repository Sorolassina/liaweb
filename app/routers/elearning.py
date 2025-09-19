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
from app_lia_web.app.templates import templates

router = APIRouter()

# === ROUTES WEB ===

@router.get("/", response_class=HTMLResponse)
async def elearning_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    programme_id: Optional[int] = None
):
    """Dashboard e-learning"""
    # Récupérer les statistiques générales
    programmes = session.exec(
        select(Programme).where(Programme.actif == True)
    ).all()
    
    print(f"🔍 DEBUG DASHBOARD: {len(programmes)} programmes actifs trouvés")
    for p in programmes:
        print(f"  - Programme {p.id}: {p.nom}")
    
    # Si un programme_id est spécifié, ne calculer les stats que pour ce programme
    if programme_id:
        programmes_to_process = [p for p in programmes if p.id == programme_id]
        print(f"🔍 DEBUG: Filtrage par programme_id {programme_id}")
    else:
        programmes_to_process = programmes
        print(f"🔍 DEBUG: Affichage de tous les programmes")
    
    stats_programmes = []
    for programme in programmes_to_process:
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
            "stats_programmes": stats_programmes,
            "programmes": programmes,
            "programme_id": programme_id
        }
    )

@router.get("/modules", response_class=HTMLResponse)
async def elearning_modules(
    request: Request,
    programme_id: Optional[int] = None,
    statut: Optional[str] = None,
    difficulte: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Liste des modules e-learning"""
    print(f"🔍 DEBUG MODULES: programme_id={programme_id}, statut={statut}, difficulte={difficulte}")
    
    # Si statut est "tous", on ne filtre pas par statut
    if statut == "tous":
        statut = None
        actif_only = False  # Voir tous les modules (actifs ET inactifs)
        print("🔍 DEBUG: Mode 'tous' activé - actif_only=False")
    else:
        actif_only = True   # Par défaut, voir seulement les modules actifs
        print(f"🔍 DEBUG: Mode normal - actif_only=True, statut={statut}")
    
    # Si difficulte est "tous", on ne filtre pas par difficulté
    if difficulte == "tous":
        difficulte = None
        print("🔍 DEBUG: Mode 'tous' difficultés activé")
    
    # Debug: Vérifier tous les modules dans la base
    all_modules = session.exec(select(ModuleElearning)).all()
    print(f"🔍 DEBUG: Total modules en base: {len(all_modules)}")
    for m in all_modules:
        print(f"  - Module {m.id}: {m.titre} (statut: {m.statut}, actif: {m.actif}, difficulte: {m.difficulte})")
    
    modules = ElearningService.get_modules(session, programme_id, statut, actif_only, difficulte)
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    
    print(f"🔍 DEBUG MODULES: {len(modules)} modules trouvés après filtrage")
    for m in modules:
        print(f"  - Module {m.id}: {m.titre} (statut: {m.statut}, actif: {m.actif}, difficulte: {m.difficulte})")
    
    return templates.TemplateResponse(
        "elearning/modules.html",
        {
            "request": request,
            "utilisateur": current_user,
            "modules": modules,
            "programmes": programmes,
            "programme_id": programme_id,
            "statut_selected": statut,
            "difficulte_selected": difficulte
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
            # Nouveaux champs spécifiques
            'url_contenu_video': ressource.url_contenu_video,
            'url_contenu_document': ressource.url_contenu_document,
            'url_contenu_audio': ressource.url_contenu_audio,
            'url_contenu_lien': ressource.url_contenu_lien,
            'fichier_video_path': ressource.fichier_video_path,
            'fichier_video_nom_original': ressource.fichier_video_nom_original,
            'fichier_document_path': ressource.fichier_document_path,
            'fichier_document_nom_original': ressource.fichier_document_nom_original,
            'fichier_audio_path': ressource.fichier_audio_path,
            'fichier_audio_nom_original': ressource.fichier_audio_nom_original,
            # Anciens champs (compatibilité)
            'url_contenu': ressource.url_contenu,
            'fichier_path': ressource.fichier_path,
            'nom_fichier_original': ressource.nom_fichier_original,
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
        print(f"🔍 DEBUG: Ressource {ressources}")
    
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
    session: Session = Depends(get_session),
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
    
    print("✅ Autorisation OK")

    # --- Form data
    print("📝 Récupération des données du formulaire...")
    form_data = await request.form()

    try:
        dbg = settings.DEBUG
    except Exception:
        dbg = False
    if dbg:
        print(f"🔍 Form keys: {list(form_data.keys())}")
    
    print(f"🔍 Clés du formulaire: {list(form_data.keys())}")

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
        # Rien à créer
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
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
                    module_id,  # ID du module
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
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
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
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "error": f"Erreur de validation: {str(e)}",
            },
        )

    try:
        print(f"💾 Sauvegarde en base de données...")
        res = ElearningService.create_ressource(session, ressource_data, current_user.id)
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
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
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
        # Rien n'a pu être créé : on retourne au formulaire avec erreurs
        return templates.TemplateResponse(
            "elearning/ressource_form.html",
            {
                "request": request,
                "utilisateur": current_user,
                "ressource": None,
                "module_id": module_id,
                "return_url": return_url,
                "error": "Aucune ressource n'a été créée. " + (" | ".join(errors) if errors else ""),
            },
        )

    # On redirige ; on peut reporter un petit résumé via querystring (facultatif)
    # ex: /elearning/modules?created=3&errors=1
    created_count = 1 if created_id else 0
    error_count = len(errors)
    print(f"🔄 Redirection avec {created_count} créations et {error_count} erreurs")
    suffix = f"?created={created_count}&errors={error_count}" if (created_count or error_count) else ""
    target = (return_url or "/elearning/modules") + suffix
    return RedirectResponse(url=target, status_code=303)

@router.get("/modules/{module_id}/ressources/{ressource_id}/remove")
async def remove_ressource_from_module(
    module_id: int,
    ressource_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Supprimer une ressource d'un module"""
    if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    try:
        ElearningService.remove_ressource_from_module(session, module_id, ressource_id)
        return RedirectResponse(url=f"/elearning/modules/{module_id}", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")

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
                    print(f"🔍 DEBUG: Fichier {file_type} trouvé: {candidate.filename}")
                    
                    file_info = await FileUploadService.save_file(
                        candidate,
                        file_type,
                        int(module_id) if module_id else None
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
                        "elearning/ressource_form.html",
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
    
    # Mettre à jour la ressource
    ressource_data = RessourceElearningUpdate(
        titre=form_data.get("titre"),
        description=form_data.get("description"),
        type_ressource=type_ressource,
        
        # URLs pour chaque type
        url_contenu_video=form_data.get("url_contenu_video"),
        url_contenu_document=form_data.get("url_contenu_document"),
        url_contenu_audio=form_data.get("url_contenu_audio"),
        url_contenu_lien=form_data.get("url_contenu_lien"),
        
        # Fichiers pour chaque type
        fichier_video_path=fichier_video_path,
        fichier_video_nom_original=fichier_video_nom_original,
        fichier_document_path=fichier_document_path,
        fichier_document_nom_original=fichier_document_nom_original,
        fichier_audio_path=fichier_audio_path,
        fichier_audio_nom_original=fichier_audio_nom_original,
        
        # Champs généraux
        url_contenu=url_contenu_selected,
        fichier_path=None,
        
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
        # En cas d'erreur, faire un rollback de la session
        session.rollback()
        # Retourner au formulaire avec un message d'erreur
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

