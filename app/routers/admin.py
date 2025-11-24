# app/routers/admin.py (version avec logs intégrés)
from __future__ import annotations

from datetime import datetime, timezone
import time
from sqlalchemy import func, delete
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, File, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, and_
from sqlmodel import Session, select
import os
from pathlib import Path

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.config import settings
from ..core.security import get_current_user
from ..core.program_schema_integration import (
    get_current_program_schema,
    SchemaRoutingService,
)
import logging
from ..core.path_config import path_config
from ..services.file_upload_service import FileUploadService
from ..templates import templates

from ..models.base import (
    User, TypeUtilisateur,
    Programme, EtapePipeline, Preinscription, Jury, ProgrammeUtilisateur, MembreJury, Promotion, Partenaire, Groupe, DecisionJuryCandidat
)
from ..models.enums import UserRole as UserRoleEnum
from ..models.admin import AppSetting
from ..models.archive import Archive, TypeArchive, StatutArchive, RegleNettoyage, LogNettoyage
from ..services.archive import ArchiveService
from ..services.audit import log_activity
from ..models.activity import ActivityLog



logger = logging.getLogger("app.admin")

router = APIRouter()

def configure_schema(session: Session, request: Optional[Request], programme: Optional[str] = None) -> str:
    base_programme = None
    if request is not None:
        base_programme = request.query_params.get("programme") or get_current_program_schema(request)
    programme_code = programme or base_programme or "public"
    routing_service = SchemaRoutingService(session)
    routing_service.set_schema(programme_code)
    return programme_code

# Fonction pour sauvegarder les photos de profil
async def save_profile_photo(photo: UploadFile, user_id: int, old_photo_path: str = None) -> str:
    """Sauvegarde une photo de profil et retourne le chemin relatif"""
    from ..core.config import Settings
    settings = Settings()
    
    print(f"🔍 [DEBUG] save_profile_photo appelée avec user_id={user_id}, filename={photo.filename}")
    
    # Validation du type MIME
    if photo.content_type not in settings.ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Type de fichier non autorisé")
    
    # Validation de la taille
    if photo.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Fichier trop volumineux. Max: {settings.MAX_UPLOAD_SIZE_MB}MB")
    
    # Supprimer l'ancienne photo si elle existe
    if old_photo_path:
        try:
            FileUploadService.delete_file(old_photo_path)
            print(f"🗑️ [DEBUG] Ancienne photo supprimée: {old_photo_path}")
        except Exception as e:
            print(f"❌ [DEBUG] Erreur lors de la suppression de l'ancienne photo: {e}")
    
    # Générer le nom de fichier
    ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
    filename = f"user_{user_id}_profile{ext}"
    
    # Modifier temporairement le nom du fichier pour le service
    original_filename = photo.filename
    photo.filename = filename
    
    # Utiliser FileUploadService pour sauvegarder le fichier
    try:
        file_info = await FileUploadService.save_file(
            photo,
            "image",
            "users",
            subfolder_id=None
        )
        print(f"✅ [DEBUG] Fichier sauvegardé avec succès: {file_info['relative_path']}")
        # Retourner le chemin avec le préfixe /uploads/ pour l'accès via le montage
        return f"/uploads/{file_info['relative_path']}"
        
    except Exception as e:
        print(f"❌ [DEBUG] Erreur lors de la sauvegarde: {e}")
        raise e
    finally:
        # Restaurer le nom original du fichier
        photo.filename = original_filename

# -------- RBAC --------
def admin_required(user: User):
    allowed = {UserRoleEnum.ADMINISTRATEUR.value, UserRoleEnum.DIRECTEUR_GENERAL.value}
    if user is None or user.role not in allowed:
        raise HTTPException(status_code=403, detail="Accès restreint")
    return user

# ===== DASHBOARD =====
@router.get("/", name="admin_root")
async def admin_root(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    return RedirectResponse(url=request.url_for("admin_programmes"), status_code=status.HTTP_302_FOUND)


# ===== PROGRAMMES =====
@router.get("/programmes", response_class=HTMLResponse, name="admin_programmes")
def admin_programmes(request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    request.state.admin_title = "Gestion des programmes"
    configure_schema(session, request)
    progs = session.exec(select(Programme).order_by(Programme.code)).all()
    
    # Récupérer tous les utilisateurs actifs pour les modals d'équipe
    users = session.exec(select(User).where(User.actif == True).order_by(User.nom_complet)).all()
    
    # Récupérer les utilisateurs affectés à chaque programme
    for prog in progs:
        prog.utilisateurs = session.exec(select(ProgrammeUtilisateur).where(ProgrammeUtilisateur.programme_id == prog.id).order_by(ProgrammeUtilisateur.role_programme)).all()
    
    # Créer un dictionnaire des utilisateurs disponibles par programme
    users_disponibles_par_programme = {}
    # Créer un dictionnaire des membres d'équipe par programme (pour JSON)
    membres_equipe_par_programme = {}
    # Créer un dictionnaire des étapes par programme
    etapes_par_programme = {}
    
    for prog in progs:
        # Exclure seulement le responsable (les utilisateurs peuvent avoir plusieurs rôles)
        excluded_user_ids = {prog.responsable_id} if prog.responsable_id else set()
        
        users_disponibles_par_programme[prog.id] = [user for user in users if user.id not in excluded_user_ids]
        
        # Convertir les membres d'équipe en dictionnaires pour JSON
        membres_equipe_par_programme[prog.id] = [
            {
                "utilisateur_id": pu.utilisateur_id,
                "role_programme": pu.role_programme
            }
            for pu in prog.utilisateurs
        ]
        
        # Récupérer les étapes du pipeline pour ce programme
        try:
            etapes_par_programme[prog.id] = session.exec(
                select(EtapePipeline)
                .where(EtapePipeline.programme_id == prog.id)
                .order_by(EtapePipeline.ordre)
            ).all()
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des étapes du pipeline pour le programme {prog.id}: {e}")
            etapes_par_programme[prog.id] = []
    
    timestamp = int(time.time())
    return templates.TemplateResponse("admin/programmes_list.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "progs": progs,
        "users": users,
        "users_disponibles_par_programme": users_disponibles_par_programme,
        "membres_equipe_par_programme": membres_equipe_par_programme,
        "etapes_par_programme": etapes_par_programme,
        "UserRole": UserRoleEnum,
        "timestamp": timestamp
    })

@router.get("/programmes/new",name="admin_programmes_new", response_class=HTMLResponse)
def admin_programme_new(request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    request.state.admin_title = "Gestion des programmes"
    configure_schema(session, request)
    # Récupérer tous les utilisateurs actifs pour le dropdown responsable
    users = session.exec(select(User).where(User.actif == True).order_by(User.nom_complet)).all()
    
    # Filtrer les utilisateurs déjà responsables d'autres programmes
    responsables_existants = session.exec(select(Programme.responsable_id).where(Programme.responsable_id.is_not(None))).all()
    responsables_existants = [r for r in responsables_existants if r is not None]
    
    users_disponibles = [user for user in users if user.id not in responsables_existants]
    
    return templates.TemplateResponse("admin/programme_form.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "prog": None,
        "users": users_disponibles,
        "UserRole": UserRoleEnum
    })

@router.get("/programmes/{prog_id}", name="admin_programmes_edit", response_class=HTMLResponse)
def admin_programme_edit(
    prog_id: int, 
    request: Request, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user)):

    admin_required(current_user)
    request.state.admin_title = "Gestion des programmes"
    configure_schema(session, request)
    prog = session.get(Programme, prog_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    
    # Récupérer tous les utilisateurs actifs pour le dropdown responsable
    users = session.exec(select(User).where(User.actif == True).order_by(User.nom_complet)).all()
    
    # Filtrer les utilisateurs déjà responsables d'autres programmes (sauf le responsable actuel)
    responsables_existants = session.exec(select(Programme.responsable_id).where(
        Programme.responsable_id.is_not(None),
        Programme.id != prog_id
    )).all()
    responsables_existants = [r for r in responsables_existants if r is not None]
    
    users_disponibles = [user for user in users if user.id not in responsables_existants]
    
    # Récupérer les utilisateurs affectés au programme
    programme_users = session.exec(select(ProgrammeUtilisateur).where(ProgrammeUtilisateur.programme_id == prog.id).order_by(ProgrammeUtilisateur.role_programme)).all()
    
    # Récupérer les étapes du pipeline pour ce programme (après les requêtes critiques)
    try:
        steps = session.exec(
            select(EtapePipeline)
            .where(EtapePipeline.programme_id == prog.id)
            .order_by(EtapePipeline.ordre)
        ).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des étapes du pipeline pour le programme {prog.id}: {e}")
        steps = []
    
    return templates.TemplateResponse("admin/programme_form.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "prog": prog, 
        "steps": steps,
        "users": users_disponibles,
        "programme_users": programme_users,
        "timestamp": int(time.time()),
        "UserRole": UserRoleEnum
    })

@router.post("/programmes/save", name="admin_programmes_save")
def admin_programme_save(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    prog_id: Optional[str] = Form(None),
    code: str = Form(...),
    nom: str = Form(...),
    objectif: Optional[str] = Form(None),
    date_debut: Optional[str] = Form(None),
    date_fin: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    ca_seuil_min: Optional[str] = Form(None),
    ca_seuil_max: Optional[str] = Form(None),
    anciennete_min_annees: Optional[str] = Form(None),
    responsable_id: Optional[str] = Form(None),
    objectif_total: Optional[str] = Form(None),
    cible_qpv_pct: Optional[str] = Form(None),
    cible_femmes_pct: Optional[str] = Form(None),
):
    print(f"🚀 [DEBUG] admin_programme_save appelée")
    print(f"📝 [DEBUG] prog_id: {prog_id} (type: {type(prog_id)})")
    print(f"📝 [DEBUG] code: {code}")
    print(f"📝 [DEBUG] nom: {nom}")
    print(f"📝 [DEBUG] actif: {actif}")
    
    admin_required(current_user)
    configure_schema(session, request)
    def _to_float(s: Optional[str]) -> Optional[float]:
        if not s: return None
        try: return float(s.replace(" ", "").replace(",", "."))
        except: return None

    # Convertir prog_id en int si fourni
    prog_id_int = None
    if prog_id and prog_id.strip():
        try:
            prog_id_int = int(prog_id)
            print(f"✅ [DEBUG] prog_id converti en int: {prog_id_int}")
        except ValueError:
            print(f"❌ [DEBUG] Erreur de conversion prog_id: {prog_id}")
            pass

    creating = False
    prog = session.get(Programme, prog_id_int) if prog_id_int else Programme()
    creating = not bool(prog_id_int)
    print(f"🔄 [DEBUG] Création: {creating}, Programme trouvé: {prog is not None}")
    
    prog.code = code.strip()
    prog.nom = nom.strip()
    prog.objectif = objectif
    if date_debut:  prog.date_debut  = datetime.fromisoformat(date_debut).date()
    if date_fin:    prog.date_fin    = datetime.fromisoformat(date_fin).date()
    prog.actif = (actif != "off")
    prog.ca_seuil_min = _to_float(ca_seuil_min)
    prog.ca_seuil_max = _to_float(ca_seuil_max)
    prog.anciennete_min_annees = int(anciennete_min_annees) if (anciennete_min_annees or "").isdigit() else None
    
    # Gérer les objectifs quantitatifs
    prog.objectif_total = int(objectif_total) if (objectif_total or "").isdigit() else None
    prog.cible_qpv_pct = _to_float(cible_qpv_pct)
    prog.cible_femmes_pct = _to_float(cible_femmes_pct)
    
    # Gérer le responsable
    if responsable_id and responsable_id.strip():
        try:
            prog.responsable_id = int(responsable_id)
        except ValueError:
            prog.responsable_id = None
    else:
        prog.responsable_id = None

    print(f"💾 [DEBUG] Sauvegarde du programme...")
    session.add(prog)
    session.flush()  # Pour obtenir l'ID du programme
    
    # Les membres d'équipe sont maintenant gérés via le modal séparé
    
    # log
    
    log_activity(session, user=current_user,
                 action="PROGRAMME_CREATE" if creating else "PROGRAMME_UPDATE",
                 entity="Programme", entity_id=prog.id,
                 activity_data={"code": prog.code, "nom": prog.nom}, request=request)
    session.commit()
    print(f"✅ [DEBUG] Programme sauvegardé avec succès")
    
    timestamp = int(time.time())
    action = "add" if creating else "update"
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action={action}&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/update", name="admin_programmes_update")
def admin_programme_update(
    prog_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    code: str = Form(...),
    nom: str = Form(...),
    objectif: Optional[str] = Form(None),
    date_debut: Optional[str] = Form(None),
    date_fin: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    ca_seuil_min: Optional[str] = Form(None),
    ca_seuil_max: Optional[str] = Form(None),
    anciennete_min_annees: Optional[str] = Form(None),
    objectif_total: Optional[str] = Form(None),
    cible_qpv_pct: Optional[str] = Form(None),
    cible_femmes_pct: Optional[str] = Form(None),
):
    admin_required(current_user)
    configure_schema(session, request)
    prog = session.get(Programme, prog_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    
    def _to_float(s: Optional[str]) -> Optional[float]:
        if not s: return None
        try: return float(s.replace(" ", "").replace(",", "."))
        except: return None

    prog.code = code.strip()
    prog.nom = nom.strip()
    prog.objectif = objectif
    if date_debut:  prog.date_debut  = datetime.fromisoformat(date_debut).date()
    if date_fin:    prog.date_fin    = datetime.fromisoformat(date_fin).date()
    prog.actif = (actif != "off")
    prog.ca_seuil_min = _to_float(ca_seuil_min)
    prog.ca_seuil_max = _to_float(ca_seuil_max)
    prog.anciennete_min_annees = int(anciennete_min_annees) if (anciennete_min_annees or "").isdigit() else None

    # Gérer les objectifs quantitatifs
    prog.objectif_total = int(objectif_total) if (objectif_total or "").isdigit() else None
    prog.cible_qpv_pct = _to_float(cible_qpv_pct)
    prog.cible_femmes_pct = _to_float(cible_femmes_pct)

    session.add(prog)
    log_activity(session, user=current_user,
                 action="PROGRAMME_UPDATE",
                 entity="Programme", entity_id=prog.id,
                 activity_data={"code": prog.code, "nom": prog.nom}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=update&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/delete", name="admin_programmes_delete")
def admin_programme_delete(
    prog_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    prog = session.get(Programme, prog_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    
    # NOTE: Le modèle Inscription a été supprimé. Les candidats validés sont identifiés par leur statut dans la table Candidat.
    # Vérification des inscriptions supprimée car le modèle n'existe plus.
    # inscriptions_count = session.exec(select(func.count(Inscription.id)).where(Inscription.programme_id == prog_id)).first()
    # if inscriptions_count > 0:
    #     raise HTTPException(status_code=400, detail=f"Impossible de supprimer le programme {prog.code} : {inscriptions_count} inscription(s) liée(s)")
    
    # Supprimer les étapes du pipeline
    try:
        session.exec(delete(EtapePipeline).where(EtapePipeline.programme_id == prog_id))
    except Exception as e:
        logger.warning(f"Erreur lors de la suppression des étapes du pipeline pour le programme {prog_id}: {e}")
    
    # Supprimer le programme
    session.delete(prog)
    log_activity(session, user=current_user,
                 action="PROGRAMME_DELETE",
                 entity="Programme", entity_id=prog_id,
                 activity_data={"code": prog.code, "nom": prog.nom}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=delete&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/etapes/add", name="admin_programmes_add_step")
def admin_programmes_add_step(
    prog_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    code: str = Form(...),
    libelle: str = Form(...),
    ordre: int = Form(...),
    type_etape: Optional[str] = Form(None),
    active: Optional[str] = Form(None)
):
    admin_required(current_user)
    configure_schema(session, request)
    prog = session.get(Programme, prog_id)
    if not prog: raise HTTPException(status_code=404, detail="Programme introuvable")
    st = EtapePipeline(programme_id=prog.id, libelle=libelle, code=code, ordre=int(ordre), type_etape=type_etape, active=(active != "off"))
    session.add(st)
    log_activity(session, user=current_user, action="STEP_ADD", entity="EtapePipeline", entity_id=None,
                 activity_data={"programme_id": prog.id, "libelle": libelle, "code": code, "ordre": int(ordre)}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=add_step&prog_id={prog_id}&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/etapes/{etape_id}/update", name="admin_etapes_update")
def admin_etapes_update(
    prog_id: int,
    etape_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    libelle: str = Form(...),
    ordre: int = Form(...),
    type_etape: Optional[str] = Form(None),
    active: Optional[str] = Form(None)
):
    admin_required(current_user)
    configure_schema(session, request)
    st = session.get(EtapePipeline, etape_id)
    if not st: raise HTTPException(status_code=404, detail="Étape introuvable")
    st.libelle = libelle; st.code = code; st.ordre = int(ordre); st.type_etape = type_etape; st.active = (active != "off")
    log_activity(session, user=current_user, action="STEP_UPDATE", entity="EtapePipeline", entity_id=st.id,
                activity_data={"programme_id": st.programme_id, "libelle": libelle, "code": code, "ordre": int(ordre)}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=update_step&prog_id={st.programme_id}&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/etapes/{etape_id}/delete", name="admin_etapes_delete")
def admin_etapes_delete(
    prog_id: int,
    etape_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    st = session.get(EtapePipeline, etape_id)
    if not st: raise HTTPException(status_code=404, detail="Étape introuvable")
    prog_id = st.programme_id
    session.delete(st)
    log_activity(session, user=current_user, action="STEP_DELETE", entity="EtapePipeline", entity_id=etape_id,
                 activity_data={"programme_id": prog_id}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=remove_step&prog_id={prog_id}&t={timestamp}", status_code=303)

# ===== UTILISATEURS DU PROGRAMME =====
@router.post("/programmes/{prog_id}/utilisateurs/add", name="admin_programme_add_user")
def admin_programme_add_user(
    prog_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    configure_schema(session, request)
    prog = session.get(Programme, prog_id)
    if not prog: raise HTTPException(status_code=404, detail="Programme introuvable")
    
    # Vérifier si l'utilisateur est déjà affecté à ce programme avec ce rôle
    existing = session.exec(select(ProgrammeUtilisateur).where(
        ProgrammeUtilisateur.programme_id == prog_id,
        ProgrammeUtilisateur.utilisateur_id == utilisateur_id,
        ProgrammeUtilisateur.role_programme == role_programme
    )).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Cet utilisateur est déjà affecté à ce programme avec ce rôle")
    
    pu = ProgrammeUtilisateur(
        programme_id=prog_id,
        utilisateur_id=utilisateur_id,
        role_programme=role_programme
    )
    session.add(pu)
    log_activity(session, user=current_user, action="PROGRAMME_USER_ADD", entity="ProgrammeUtilisateur", entity_id=None,
                 activity_data={"programme_id": prog_id, "utilisateur_id": utilisateur_id, "role": role_programme}, request=request)
    session.commit()
    
    # Rediriger vers la même page avec un paramètre pour indiquer le succès
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=add_member&prog_id={prog_id}&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/utilisateurs/{user_id}/delete", name="admin_programme_remove_user")
def admin_programme_remove_user(
    prog_id: int,
    user_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    configure_schema(session, request)
    pu = session.exec(select(ProgrammeUtilisateur).where(
        ProgrammeUtilisateur.programme_id == prog_id,
        ProgrammeUtilisateur.utilisateur_id == user_id
    )).first()
    
    if not pu: raise HTTPException(status_code=404, detail="Affectation introuvable")
    
    session.delete(pu)
    log_activity(session, user=current_user, action="PROGRAMME_USER_REMOVE", entity="ProgrammeUtilisateur", entity_id=pu.id,
                 activity_data={"programme_id": prog_id, "utilisateur_id": user_id, "role": pu.role_programme}, request=request)
    session.commit()
    
    # Rediriger vers la même page avec un paramètre pour indiquer le succès
    timestamp = int(time.time())
    return RedirectResponse(url=f"{request.url_for('admin_programmes')}?success=1&action=remove_member&prog_id={prog_id}&t={timestamp}", status_code=303)

# ===== UTILISATEURS =====
@router.get("/users", response_class=HTMLResponse, name="admin_users")
def admin_users(request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user), q: Optional[str] = Query(None)):
    admin_required(current_user)
    request.state.admin_title = "Gestion des utilisateurs"
    configure_schema(session, request)
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.email.ilike(like)) | (User.nom_complet.ilike(like)))
    users = session.exec(stmt.order_by(User.cree_le.desc())).all()
    
    # Ajouter un timestamp pour le cache-busting des images
    timestamp = int(datetime.now(timezone.utc).timestamp())
    
    return templates.TemplateResponse("admin/users.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "users": users, 
        "UserRole": UserRoleEnum,
        "q": q or "",
        "timestamp": timestamp
    })

@router.post("/users/add", name="admin_users_add")
async def admin_users_add(
    email: str = Form(...), 
    nom_complet: str = Form(...), 
    telephone: Optional[str] = Form(None),
    role: str = Form(...),
    type_utilisateur: str = Form("INTERNE"),
    mot_de_passe: Optional[str] = Form(None),
    photo_profil: UploadFile | None = File(None),
    request: Request = None, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    from ..core.security import get_password_hash
    if session.exec(select(User).where(User.email==email)).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    try: 
        # Chercher le rôle par sa valeur au lieu de son nom
        r = None
        for enum_role in UserRoleEnum:
            if enum_role.value == role:
                r = enum_role
                break
        
        if not r:
            r = UserRoleEnum.CONSEILLER.value  # Valeur par défaut
        
        # Assigner la valeur string au lieu de l'objet enum
        role_value = r.value
    except Exception: 
        role_value = UserRoleEnum.CONSEILLER.value  # Valeur par défaut
    
    try: t = getattr(TypeUtilisateur, type_utilisateur)
    except Exception: t = TypeUtilisateur.INTERNE
    
    # Utiliser le mot de passe fourni ou le défaut
    password = mot_de_passe if mot_de_passe else "ChangeMe123!"
    
    u = User(
        email=email, 
        nom_complet=nom_complet, 
        telephone=telephone,
        role=role_value, 
        type_utilisateur=t,
        mot_de_passe_hash=get_password_hash(password)
    )
    session.add(u)
    session.flush()  # Pour obtenir l'ID de l'utilisateur
    
    # Sauvegarder la photo de profil si fournie
    if photo_profil and photo_profil.filename:
        try:
            photo_path = await save_profile_photo(photo_profil, u.id, None)  # Pas d'ancienne photo lors de la création
            u.photo_profil = photo_path
        except Exception as e:
            # En cas d'erreur, continuer sans photo
            pass
    
    log_activity(session, user=current_user, action="USER_CREATE", entity="User", entity_id=u.id,
                 activity_data={"email": u.email, "nom_complet": u.nom_complet, "role": u.role}, request=request)
    session.commit()
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_users')}?success=1&action=add&t={timestamp}", status_code=303)

@router.post("/users/{uid}/toggle", name="admin_users_toggle")
def admin_users_toggle(uid: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    configure_schema(session, request)
    u = session.get(User, uid)
    if not u: raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    u.actif = not bool(u.actif)
    log_activity(session, user=current_user, action="USER_TOGGLE", entity="User", entity_id=u.id,
                activity_data={"active": u.actif}, request=request)
    session.commit()
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_users')}?success=1&action=toggle&t={timestamp}", status_code=303)

@router.post("/users/{uid}/update", name="admin_users_update")
def admin_users_update(
    uid: int,
    nom_complet: str = Form(...),
    email: str = Form(...),
    telephone: Optional[str] = Form(None),
    role: str = Form(...),
    type_utilisateur: str = Form(...),
    mot_de_passe: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    u = session.get(User, uid)
    if not u: raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    # Vérifier si l'email est déjà utilisé par un autre utilisateur
    existing_user = session.exec(select(User).where(User.email == email, User.id != uid)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email déjà utilisé par un autre utilisateur")
    
    # Sauvegarder les anciennes valeurs pour le log
    old_values = {
        "nom_complet": u.nom_complet,
        "email": u.email,
        "telephone": u.telephone,
        "role": u.role,
        "type_utilisateur": u.type_utilisateur.name
    }
    
    # Mettre à jour les champs
    u.nom_complet = nom_complet
    u.email = email
    u.telephone = telephone if telephone.strip() else None
    
    print(f"🔍 [DEBUG] Rôle reçu du formulaire: '{role}'")
    print(f"🔍 [DEBUG] Type du rôle reçu: {type(role)}")
    print(f"🔍 [DEBUG] Rôle actuel de l'utilisateur: {u.role}")
    print(f"🔍 [DEBUG] Valeur du rôle actuel: {u.role.value if hasattr(u.role, 'value') else u.role}")
    
    try: 
        # Chercher le rôle par sa valeur au lieu de son nom
        new_role = None
        for enum_role in UserRoleEnum:
            if enum_role.value == role:
                new_role = enum_role
                break
        
        if new_role:
            print(f"✅ [DEBUG] Nouveau rôle trouvé: {new_role}")
            print(f"✅ [DEBUG] Valeur du nouveau rôle: {new_role.value}")
            u.role = new_role.value  # Assigner la valeur string au lieu de l'objet enum
            print(f"✅ [DEBUG] Rôle assigné à l'utilisateur: {u.role}")
        else:
            print(f"❌ [DEBUG] Rôle '{role}' non trouvé dans l'enum")
    except Exception as e: 
        print(f"❌ [DEBUG] Erreur lors de l'assignation du rôle: {e}")
        pass
    
    try: u.type_utilisateur = getattr(TypeUtilisateur, type_utilisateur)
    except Exception: pass
    
    # Mettre à jour le mot de passe si fourni
    if mot_de_passe and mot_de_passe.strip():
        from ..core.security import get_password_hash
        u.mot_de_passe_hash = get_password_hash(mot_de_passe)
        old_values["password_changed"] = True
    
    # Log des modifications
    log_activity(session, user=current_user, action="USER_UPDATE", entity="User", entity_id=u.id,
                 activity_data={"old": old_values, "new": {
                     "nom_complet": u.nom_complet,
                     "email": u.email,
                     "telephone": u.telephone,
                     "role": u.role,  # u.role est maintenant une string
                     "type_utilisateur": u.type_utilisateur.name,
                     "password_changed": mot_de_passe and mot_de_passe.strip() != ""
                                }}, request=request)
    
    print(f"💾 [DEBUG] Avant commit - Rôle de l'utilisateur: {u.role}")
    session.commit()
    print(f"✅ [DEBUG] Après commit - Rôle de l'utilisateur: {u.role}")
    
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_users')}?success=1&action=update&t={timestamp}", status_code=303)

# ===== JURYS =====
@router.get("/jurys", response_class=HTMLResponse, name="admin_jurys")
def admin_jurys(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme: Optional[str] = Query(None),
):
    admin_required(current_user)
    request.state.admin_title = "Gestion des jurys"

    # Déterminer le schéma courant (middleware ou paramètre ?programme=...)
    programme_code = configure_schema(session, request, programme)
    logger.info("🏛️ [ADMIN/JURYS] Schéma actif: %s", programme_code)

    # Charger les jurys avec leurs relations - Version sécurisée
    from sqlalchemy.orm import joinedload
    jurys = []
    logger.info("🧾 [ADMIN/JURYS] Chargement des données jurys")
    try:
        jurys = session.exec(
            select(Jury)
            .options(
                joinedload(Jury.programme),
                joinedload(Jury.promotion)
            )
            .order_by(Jury.session_le.desc())
        ).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des jurys: {e}")
        jurys = []
    logger.info("🧑‍⚖️ [ADMIN/JURYS] Jurys chargés: %d", len(jurys))
    
    progs = []
    try:
        progs = session.exec(select(Programme).order_by(Programme.code)).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des programmes: {e}")
        progs = []
    logger.info("📚 [ADMIN/JURYS] Programmes chargés: %d", len(progs))
    
    promotions = []
    try:
        promotions = session.exec(select(Promotion).order_by(Promotion.libelle)).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des promotions: {e}")
        promotions = []
    logger.info("🎓 [ADMIN/JURYS] Promotions chargées: %d", len(promotions))
    
    groupes = []
    try:
        groupes = session.exec(select(Groupe).where(Groupe.actif == True).order_by(Groupe.nom)).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des groupes: {e}")
        groupes = []
    logger.info("👥 [ADMIN/JURYS] Groupes actifs: %d", len(groupes))
    
    users = []
    try:
        users = session.exec(select(User).where(User.actif == True)).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des utilisateurs: {e}")
        users = []
    logger.info("👤 [ADMIN/JURYS] Utilisateurs actifs: %d", len(users))
    logger.info("🏷️ [ADMIN/JURYS] Premier programme: %s", progs[0].code if progs else "<aucun>")
    if jurys:
        premier_prog = getattr(jurys[0].programme, "code", "-")
        logger.info("🔎 [ADMIN/JURYS] Premier jury: id=%s, programme=%s", jurys[0].id, premier_prog)
    else:
        logger.info("🔎 [ADMIN/JURYS] Premier jury: <aucun>")
    
    return templates.TemplateResponse("admin/jurys.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "jurys": jurys, 
        "progs": progs,
        "promotions": promotions,
        "groupes": groupes,
        "users": users
    })

@router.post("/jurys/add")
def admin_jurys_add(programme_id: int = Form(...), session_date: str = Form(...), session_time: str = Form(...), 
                     lieu: Optional[str] = Form(None), statut: str = Form("planifie"), promotion_id: Optional[str] = Form(None),
                     request: Request = None, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
     admin_required(current_user)
     configure_schema(session, request)
     prog = session.get(Programme, programme_id)
     if not prog: raise HTTPException(status_code=404, detail="Programme introuvable")
     
     # Combiner la date et l'heure
     dt = datetime.fromisoformat(f"{session_date}T{session_time}")
     j = Jury(programme_id=prog.id, session_le=dt, lieu=lieu or None, statut=statut, 
              promotion_id=int(promotion_id) if promotion_id else None)
     session.add(j)
     log_activity(session, user=current_user, action="JURY_ADD", entity="Jury", entity_id=None,
                  activity_data={"programme_id": prog.id, "session_le": dt.isoformat(), "lieu": lieu, "statut": statut}, request=request)
     session.commit()
     return RedirectResponse(url=request.url_for("admin_jurys"), status_code=303)

@router.post("/jurys/{jury_id}/update")
def admin_jury_update(jury_id: int, 
                      programme_id: int = Form(...), 
                      session_date: str = Form(...), 
                      session_time: str = Form(...), 
                      lieu: Optional[str] = Form(None),
                      statut: str = Form("planifie"),
                      promotion_id: Optional[str] = Form(None),
                      request: Request = None, 
                      session: Session = Depends(get_shared_session), 
                      current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    configure_schema(session, request)
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(status_code=404, detail="Jury introuvable")
    
    # Combiner la date et l'heure
    dt = datetime.fromisoformat(f"{session_date}T{session_time}")
    
    # Mise à jour des champs
    jury.programme_id = programme_id
    jury.session_le = dt
    jury.lieu = lieu or None
    jury.statut = statut
    jury.promotion_id = int(promotion_id) if promotion_id else None
    
    session.add(jury)
    session.commit()
    
    log_activity(session, user=current_user, action="JURY_UPDATE", entity="Jury", entity_id=jury_id,
                 activity_data={"programme_id": programme_id, "session_le": dt.isoformat(), "statut": statut}, request=request)
    
    return RedirectResponse(url=f"{request.url_for('admin_jurys')}?success=jury_updated&jury_id={jury_id}", status_code=303)

@router.post("/jurys/{jury_id}/delete")
def admin_jury_delete(jury_id: int, request: Request = None, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    configure_schema(session, request)
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(status_code=404, detail="Jury introuvable")
    
    # Supprimer d'abord les membres du jury
    session.exec(delete(MembreJury).where(MembreJury.jury_id == jury_id))
    
    # Puis supprimer le jury
    session.delete(jury)
    session.commit()
    
    log_activity(session, user=current_user, action="JURY_DELETE", entity="Jury", entity_id=jury_id,
                 activity_data={"programme_id": jury.programme_id}, request=request)
    
    return RedirectResponse(url=request.url_for("admin_jurys"), status_code=303)

@router.post("/jurys/{jury_id}/membres/add")
def admin_jury_add_member(jury_id: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user),
                           membre_id: int = Form(...), role: str = Form(...)):
    admin_required(current_user)
    configure_schema(session, request)
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(status_code=404, detail="Jury introuvable")
    
    user = session.get(User, membre_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    # Vérifier si l'utilisateur n'est pas déjà membre
    existing = session.exec(select(MembreJury).where(MembreJury.jury_id == jury_id, MembreJury.utilisateur_id == membre_id)).first()
    if existing:
        return RedirectResponse(url=f"{request.url_for('admin_jurys')}?error=already_member&jury_id={jury_id}&action=add_member", status_code=303)
    
    # Ajouter le membre
    membre = MembreJury(jury_id=jury_id, utilisateur_id=membre_id, role=role)
    session.add(membre)
    session.commit()
    
    log_activity(session, user=current_user, action="JURY_MEMBER_ADD", entity="Jury", entity_id=jury_id,
                 activity_data={"utilisateur_id": membre_id, "role": role}, request=request)
    
    return RedirectResponse(url=f"{request.url_for('admin_jurys')}?success=member_added&jury_id={jury_id}&action=add_member", status_code=303)

@router.post("/jurys/{jury_id}/membres/{membre_id}/delete")
def admin_jury_remove_member(jury_id: int, membre_id: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    configure_schema(session, request)
    membre = session.get(MembreJury, membre_id)
    if not membre or membre.jury_id != jury_id:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    
    session.delete(membre)
    session.commit()
    
    log_activity(session, user=current_user, action="JURY_MEMBER_DELETE", entity="Jury", entity_id=jury_id,
                 activity_data={"utilisateur_id": membre.utilisateur_id}, request=request)
    
    return RedirectResponse(url=f"{request.url_for('admin_jurys')}?success=member_deleted&jury_id={jury_id}&action=remove_member", status_code=303)

@router.post("/jurys/{jury_id}/send-invitations")
def admin_jury_send_invitations(jury_id: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    configure_schema(session, request)
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(status_code=404, detail="Jury introuvable")
    
    # Récupérer les membres du jury
    membres = session.exec(select(MembreJury).where(MembreJury.jury_id == jury_id)).all()
    
    if not membres:
        return RedirectResponse(url=f"{request.url_for('admin_jurys')}?error=no_members&jury_id={jury_id}&action=invitations", status_code=303)
    
    # Envoyer les invitations par email
    sent_count = 0
    for membre in membres:
        try:
            # Ici vous pouvez ajouter la logique d'envoi d'email
            # Pour l'instant, on simule l'envoi
            print(f"📧 [DEBUG] Envoi invitation jury à {membre.utilisateur.email}")
            sent_count += 1
        except Exception as e:
            print(f"❌ [ERROR] Erreur envoi email à {membre.utilisateur.email}: {e}")
    
    log_activity(session, user=current_user, action="JURY_INVITATIONS_SENT", entity="Jury", entity_id=jury_id,
                 activity_data={"sent_count": sent_count, "total_members": len(membres)}, request=request)
    
    return RedirectResponse(url=f"{request.url_for('admin_jurys')}?success=invitations_sent&count={sent_count}&jury_id={jury_id}", status_code=303)

@router.get("/settings", response_class=HTMLResponse, name="admin_settings")
def admin_settings(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    request.state.admin_title = "Paramètres de l'administration"
    configure_schema(session, request)

    def get_value(key: str, default: str = "") -> str:
        try:
            # S'assurer que le schéma public est utilisé pour app_setting
            from sqlalchemy import text
            # Rollback d'abord pour s'assurer que la transaction est propre
            try:
                session.rollback()
            except:
                pass
            
            # Configurer le search_path pour le schéma public
            session.exec(text("SET search_path TO public, public"))
            
            setting = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
            return setting.value if setting else default
        except Exception as exc:
            logger.warning("Erreur lors de la récupération du paramètre %s: %s", key, exc)
            # Rollback en cas d'erreur pour éviter que la transaction reste en état d'échec
            try:
                session.rollback()
            except:
                pass
            return default

    context = {
        "THEME_PRIMARY": get_value("THEME_PRIMARY", getattr(settings, "THEME_PRIMARY", "#ffd300")),
        "THEME_SECONDARY": get_value("THEME_SECONDARY", getattr(settings, "THEME_SECONDARY", "#111827")),
        "MAX_UPLOAD_SIZE_MB": get_value("MAX_UPLOAD_SIZE_MB", str(getattr(settings, "MAX_UPLOAD_SIZE_MB", 5))),
        "SMTP_HOST": get_value("SMTP_HOST", getattr(settings, "SMTP_HOST", "")),
        "SMTP_PORT": get_value("SMTP_PORT", str(getattr(settings, "SMTP_PORT", ""))),
        "SMTP_USER": get_value("SMTP_USER", getattr(settings, "SMTP_USER", "")),
        "SMTP_PASSWORD": get_value("SMTP_PASSWORD", getattr(settings, "SMTP_PASSWORD", "")),
        "MAIL_FROM": get_value("MAIL_FROM", getattr(settings, "MAIL_FROM", "")),
        "SMTP_TLS": get_value("SMTP_TLS", str(getattr(settings, "SMTP_TLS", True))),
    }

    return templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "cfg": context,
        },
    )


@router.post("/settings/save", name="admin_settings_save")
def admin_settings_save(
    THEME_PRIMARY: Optional[str] = Form(None),
    THEME_SECONDARY: Optional[str] = Form(None),
    MAX_UPLOAD_SIZE_MB: Optional[str] = Form(None),
    SMTP_HOST: Optional[str] = Form(None),
    SMTP_PORT: Optional[str] = Form(None),
    SMTP_USER: Optional[str] = Form(None),
    SMTP_PASSWORD: Optional[str] = Form(None),
    MAIL_FROM: Optional[str] = Form(None),
    SMTP_TLS: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    configure_schema(session, request)

    def upsert(key: str, value: Optional[str]) -> None:
        if value is None:
            return
        try:
            # S'assurer que le schéma public est utilisé pour app_setting
            from sqlalchemy import text
            # Rollback d'abord pour s'assurer que la transaction est propre
            try:
                session.rollback()
            except:
                pass
            
            # Configurer le search_path pour le schéma public
            session.exec(text("SET search_path TO public, public"))
            
            setting = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
            if setting is None:
                session.add(AppSetting(key=key, value=value))
            else:
                setting.value = value
                setting.updated_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning("Erreur lors de la mise à jour du paramètre %s: %s", key, exc)
            # Rollback en cas d'erreur pour éviter que la transaction reste en état d'échec
            try:
                session.rollback()
            except:
                pass

    upsert("THEME_PRIMARY", THEME_PRIMARY)
    upsert("THEME_SECONDARY", THEME_SECONDARY)
    upsert("MAX_UPLOAD_SIZE_MB", MAX_UPLOAD_SIZE_MB)
    upsert("SMTP_HOST", SMTP_HOST)
    upsert("SMTP_PORT", SMTP_PORT)
    upsert("SMTP_USER", SMTP_USER)
    # Ne mettre à jour le mot de passe que s'il est fourni (pour éviter de le vider si le champ est vide)
    if SMTP_PASSWORD is not None and SMTP_PASSWORD.strip():
        upsert("SMTP_PASSWORD", SMTP_PASSWORD)
    upsert("MAIL_FROM", MAIL_FROM)
    upsert("SMTP_TLS", SMTP_TLS)

    log_activity(
        session,
        user=current_user,
        action="SETTINGS_SAVE",
        entity="AppSetting",
        entity_id=None,
        activity_data={
            "keys": [
                "THEME_PRIMARY",
                "THEME_SECONDARY",
                "MAX_UPLOAD_SIZE_MB",
                "SMTP_HOST",
                "SMTP_PORT",
                "SMTP_USER",
                "SMTP_PASSWORD",
                "MAIL_FROM",
                "SMTP_TLS",
            ]
        },
        request=request,
    )
    session.commit()
    return RedirectResponse(url=request.url_for("admin_settings"), status_code=303)


@router.get("/logs", response_class=HTMLResponse)
def admin_logs(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),   # "YYYY-MM-DD"
    date_to: Optional[str] = Query(None),     # "YYYY-MM-DD"
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
):
    admin_required(current_user)
    request.state.admin_title = "Traçabilité des actions"
    configure_schema(session, request)
    stmt = select(ActivityLog)
    conds = []
    if q:
        like = f"%{q}%"
        # recherche libre sur action, entity, user_email
        conds.append(
            (ActivityLog.action.ilike(like)) | (ActivityLog.entity.ilike(like)) | (ActivityLog.user_email.ilike(like))
        )
    if action:
        conds.append(ActivityLog.action == action)
    if user_email:
        conds.append(ActivityLog.user_email == user_email)
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
            conds.append(ActivityLog.created_at >= from_dt)
        except: pass
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)  # fin de journée pas imposée
            conds.append(ActivityLog.created_at <= to_dt)
        except: pass

    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.order_by(ActivityLog.created_at.desc())
    # pagination basique
    offset = (page - 1) * page_size
    rows = session.exec(stmt.offset(offset).limit(page_size)).all()

    # pour les filtres action / user_email
    actions_distinct = session.exec(select(ActivityLog.action).distinct().order_by(ActivityLog.action)).all()
    users_distinct = session.exec(select(ActivityLog.user_email).where(ActivityLog.user_email.is_not(None)).distinct().order_by(ActivityLog.user_email)).all()

    return templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "logs": rows,
            "rows": rows,
            "q": q or "",
            "action": action or "",
            "user_email": user_email or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
            "actions_distinct": [a[0] if isinstance(a, tuple) else a for a in actions_distinct],
            "users_distinct": [u[0] if isinstance(u, tuple) else u for u in users_distinct],
            "page": page,
            "page_size": page_size,
        }
    )

@router.get("/logs/export")
def admin_logs_export_csv(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    admin_required(current_user)
    import csv, io, json
    stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    # (optionnel) re-appliquer les mêmes filtres que ci-dessus si tu veux
    rows = session.exec(stmt.limit(10000)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at","user_email","action","entity","entity_id","ip","user_agent","activity_data"])
    for r in rows:
        writer.writerow([
            r.created_at.isoformat(), r.user_email or "", r.action, r.entity or "", r.entity_id or "",
            r.ip or "", (r.user_agent or "")[:200],  # UA tronqué
            ("" if r.activity_data is None else json.dumps(r.activity_data, ensure_ascii=False)),
        ])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=activity_logs.csv"})

@router.post("/users/{uid}/photo", name="admin_users_photo")
async def admin_users_photo(
    uid: int, 
    photo_profil: UploadFile = File(...),
    request: Request = None, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user)
):
    print(f"🚀 [DEBUG] admin_users_photo appelée avec uid={uid}")
    admin_required(current_user)
    configure_schema(session, request)
    
    print(f"🔍 [DEBUG] Recherche de l'utilisateur avec id={uid}")
    u = session.get(User, uid)
    if not u: 
        print(f"❌ [DEBUG] Utilisateur introuvable avec id={uid}")
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    print(f"✅ [DEBUG] Utilisateur trouvé: {u.email}")
    
    # Sauvegarder la nouvelle photo
    try:
        print(f"📸 [DEBUG] Début de la sauvegarde de la photo...")
        photo_path = await save_profile_photo(photo_profil, u.id, u.photo_profil)
        print(f"📸 [DEBUG] Photo sauvegardée: {photo_path}")
        
        u.photo_profil = photo_path
        print(f"💾 [DEBUG] Mise à jour du champ photo_profil dans la base")
        session.commit()
        print(f"✅ [DEBUG] Commit réussi")
        
        log_activity(session, user=current_user, action="USER_PHOTO_UPDATE", entity="User", entity_id=u.id,
                     activity_data={"user_email": u.email}, request=request)
        print(f"📝 [DEBUG] Activité loggée")
        
    except Exception as e:
        print(f"❌ [DEBUG] Erreur dans admin_users_photo: {e}")
        print(f"❌ [DEBUG] Type d'erreur: {type(e)}")
        import traceback
        print(f"❌ [DEBUG] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde de la photo")
    
    print(f"🔄 [DEBUG] Redirection vers /admin/users")
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_users')}?success=1&action=photo&t={timestamp}", status_code=303)

@router.post("/users/{uid}/delete", name="admin_users_delete")
def admin_users_delete(
    uid: int,
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    print(f"🚀 [DEBUG] admin_users_delete appelée avec uid={uid}")
    admin_required(current_user)
    configure_schema(session, request)
    
    print(f"🔍 [DEBUG] Recherche de l'utilisateur avec id={uid}")
    u = session.get(User, uid)
    if not u:
        print(f"❌ [DEBUG] Utilisateur introuvable avec id={uid}")
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    print(f"✅ [DEBUG] Utilisateur trouvé: {u.email}")
    
    # Empêcher la suppression de l'utilisateur connecté
    if u.id == current_user.id:
        print(f"❌ [DEBUG] Tentative de suppression de l'utilisateur connecté")
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    
    # Vérifier si l'utilisateur est responsable d'un programme
    programmes_responsable = session.exec(select(Programme).where(Programme.responsable_id == u.id)).all()
    if programmes_responsable:
        programmes_noms = [f"{p.code} - {p.nom}" for p in programmes_responsable]
        print(f"❌ [DEBUG] Utilisateur responsable de programmes: {programmes_noms}")
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return RedirectResponse(
            url=f"/admin/users?error=1&message=Impossible de supprimer cet utilisateur car il est responsable des programmes suivants : {', '.join(programmes_noms)}. Veuillez d'abord réassigner ces programmes à un autre responsable.&t={timestamp}", 
            status_code=303
        )
    
    # Vérifier si l'utilisateur est membre d'équipe d'un programme
    from ..models.base import ProgrammeUtilisateur
    membres_equipe = session.exec(select(ProgrammeUtilisateur).where(ProgrammeUtilisateur.utilisateur_id == u.id)).all()
    if membres_equipe:
        programmes_membre = []
        for membre in membres_equipe:
            prog = session.get(Programme, membre.programme_id)
            if prog:
                programmes_membre.append(f"{prog.code} - {prog.nom}")
        print(f"❌ [DEBUG] Utilisateur membre d'équipe de programmes: {programmes_membre}")
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return RedirectResponse(
            url=f"/admin/users?error=1&message=Impossible de supprimer cet utilisateur car il est membre d'équipe des programmes suivants : {', '.join(programmes_membre)}. Veuillez d'abord le retirer de ces équipes.&t={timestamp}", 
            status_code=303
        )
    
    
    
    # Vérifier si l'utilisateur a déposé des documents
    from ..models.base import Document
    documents_deposes = session.exec(select(Document).where(Document.depose_par_id == u.id)).all()
    if documents_deposes:
        print(f"❌ [DEBUG] Utilisateur a déposé des documents")
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return RedirectResponse(
            url=f"/admin/users?error=1&message=Impossible de supprimer cet utilisateur car il a déposé des documents. Veuillez d'abord réassigner ces documents.&t={timestamp}", 
            status_code=303
        )
    
    # Sauvegarder les informations pour le log avant suppression
    user_email = u.email
    user_name = u.nom_complet
    photo_profil_path = u.photo_profil  # Sauvegarder le chemin de la photo
    
    try:
        print(f"🗑️ [DEBUG] Suppression de l'utilisateur de la base de données")
        session.delete(u)
        session.commit()
        print(f"✅ [DEBUG] Utilisateur supprimé avec succès")
        
        # Supprimer la photo de profil seulement après confirmation de la suppression en base
        if photo_profil_path:
            try:
                photo_path = Path("." + photo_profil_path)
                if photo_path.exists():
                    print(f"🗑️ [DEBUG] Suppression de la photo de profil: {photo_path}")
                    photo_path.unlink()
                    print(f"✅ [DEBUG] Photo de profil supprimée")
            except Exception as e:
                print(f"⚠️ [DEBUG] Erreur lors de la suppression de la photo: {e}")
        
        log_activity(session, user=current_user, action="USER_DELETE", entity="User", entity_id=uid,
                     activity_data={"deleted_user_email": user_email, "deleted_user_name": user_name}, request=request)
        print(f"📝 [DEBUG] Activité loggée")
        
    except Exception as e:
        print(f"❌ [DEBUG] Erreur lors de la suppression: {e}")
        session.rollback()
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression de l'utilisateur")
    
    print(f"🔄 [DEBUG] Redirection vers /admin/users")
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_users')}?success=1&action=delete&t={timestamp}", status_code=303)

# ===== PARTENAIRES =====
@router.get("/partenaires", response_class=HTMLResponse, name="admin_partenaires")
def admin_partenaires(request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user), q: Optional[str] = Query(None)):
    admin_required(current_user)
    request.state.admin_title = "Gestion des partenaires"
    configure_schema(session, request)
    stmt = select(Partenaire)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Partenaire.nom.ilike(like)) | (Partenaire.email.ilike(like)) | (Partenaire.description.ilike(like)))
    partenaires = session.exec(stmt.order_by(Partenaire.nom)).all()
    
    return templates.TemplateResponse("admin/partenaires.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "partenaires": partenaires, 
        "q": q or ""
    })

@router.post("/partenaires/add")
def admin_partenaires_add(
    nom: str = Form(...), 
    description: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    telephone: Optional[str] = Form(None),
    adresse: Optional[str] = Form(None),
    site_web: Optional[str] = Form(None),
    specialites: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    request: Request = None, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    
    # Vérifier si un partenaire avec ce nom existe déjà
    existing = session.exec(select(Partenaire).where(Partenaire.nom == nom.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un partenaire avec ce nom existe déjà")
    
    partenaire = Partenaire(
        nom=nom.strip(),
        description=description.strip() if description else None,
        email=email.strip() if email else None,
        telephone=telephone.strip() if telephone else None,
        adresse=adresse.strip() if adresse else None,
        site_web=site_web.strip() if site_web else None,
        specialites=specialites.strip() if specialites else None,
        actif=(actif != "off")
    )
    session.add(partenaire)
    log_activity(session, user=current_user, action="PARTENAIRE_CREATE", entity="Partenaire", entity_id=partenaire.id,
                 activity_data={"nom": partenaire.nom, "email": partenaire.email}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_partenaires')}?success=1&action=add&t={timestamp}", status_code=303)

@router.post("/partenaires/{partenaire_id}/update")
def admin_partenaires_update(
    partenaire_id: int,
    nom: str = Form(...),
    description: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    telephone: Optional[str] = Form(None),
    adresse: Optional[str] = Form(None),
    site_web: Optional[str] = Form(None),
    specialites: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    partenaire = session.get(Partenaire, partenaire_id)
    if not partenaire:
        raise HTTPException(status_code=404, detail="Partenaire introuvable")
    
    # Vérifier si un autre partenaire avec ce nom existe déjà
    existing = session.exec(select(Partenaire).where(Partenaire.nom == nom.strip(), Partenaire.id != partenaire_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un autre partenaire avec ce nom existe déjà")
    
    # Sauvegarder les anciennes valeurs pour le log
    old_values = {
        "nom": partenaire.nom,
        "description": partenaire.description,
        "email": partenaire.email,
        "telephone": partenaire.telephone,
        "adresse": partenaire.adresse,
        "site_web": partenaire.site_web,
        "specialites": partenaire.specialites,
        "actif": partenaire.actif
    }
    
    # Mettre à jour les champs
    partenaire.nom = nom.strip()
    partenaire.description = description.strip() if description else None
    partenaire.email = email.strip() if email else None
    partenaire.telephone = telephone.strip() if telephone else None
    partenaire.adresse = adresse.strip() if adresse else None
    partenaire.site_web = site_web.strip() if site_web else None
    partenaire.specialites = specialites.strip() if specialites else None
    partenaire.actif = (actif != "off")
    
    session.add(partenaire)
    log_activity(session, user=current_user, action="PARTENAIRE_UPDATE", entity="Partenaire", entity_id=partenaire.id,
                 activity_data={"old": old_values, "new": {
                     "nom": partenaire.nom,
                     "description": partenaire.description,
                     "email": partenaire.email,
                     "telephone": partenaire.telephone,
                     "adresse": partenaire.adresse,
                     "site_web": partenaire.site_web,
                     "specialites": partenaire.specialites,
                     "actif": partenaire.actif
                 }}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_partenaires')}?success=1&action=update&t={timestamp}", status_code=303)

@router.post("/partenaires/{partenaire_id}/toggle")
def admin_partenaires_toggle(partenaire_id: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    configure_schema(session, request)
    partenaire = session.get(Partenaire, partenaire_id)
    if not partenaire:
        raise HTTPException(status_code=404, detail="Partenaire introuvable")
    
    partenaire.actif = not bool(partenaire.actif)
    log_activity(session, user=current_user, action="PARTENAIRE_TOGGLE", entity="Partenaire", entity_id=partenaire.id,
                activity_data={"nom": partenaire.nom, "actif": partenaire.actif}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_partenaires')}?success=1&action=toggle&t={timestamp}", status_code=303)

@router.post("/partenaires/{partenaire_id}/delete")
def admin_partenaires_delete(
    partenaire_id: int,
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    partenaire = session.get(Partenaire, partenaire_id)
    if not partenaire:
        raise HTTPException(status_code=404, detail="Partenaire introuvable")
    
    # Vérifier si le partenaire est utilisé dans des réorientations
    from ..models.jury import DecisionJuryCandidat
    try:
        reorientations_count = session.exec(
            select(func.count(DecisionJuryCandidat.id)).where(DecisionJuryCandidat.partenaire_id == partenaire_id)
        ).first()
    except Exception as e:
        logger.warning(f"Erreur lors de la vérification des réorientations: {e}")
        reorientations_count = 0
    
    if reorientations_count > 0:
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return RedirectResponse(
            url=f"/admin/partenaires?error=1&message=Impossible de supprimer le partenaire '{partenaire.nom}' car il est utilisé dans {reorientations_count} réorientation(s). Veuillez d'abord réassigner ces réorientations.&t={timestamp}", 
            status_code=303
        )
    
    # Sauvegarder les informations pour le log avant suppression
    partenaire_nom = partenaire.nom
    partenaire_email = partenaire.email
    
    try:
        session.delete(partenaire)
        session.commit()
        
        log_activity(session, user=current_user, action="PARTENAIRE_DELETE", entity="Partenaire", entity_id=partenaire_id,
                     activity_data={"deleted_partenaire_nom": partenaire_nom, "deleted_partenaire_email": partenaire_email}, request=request)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression du partenaire")
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_partenaires')}?success=1&action=delete&t={timestamp}", status_code=303)


# ===== GROUPES =====
@router.get("/groupes", response_class=HTMLResponse, name="admin_groupes")
def admin_groupes(request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user), q: Optional[str] = Query(None)):
    admin_required(current_user)
    request.state.admin_title = "Gestion des groupes"
    configure_schema(session, request)
    stmt = select(Groupe)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Groupe.nom.ilike(like)) | (Groupe.description.ilike(like)))
    groupes = session.exec(stmt.order_by(Groupe.nom)).all()
    
    return templates.TemplateResponse("admin/groupes.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "groupes": groupes, 
        "q": q or ""
    })

@router.post("/groupes/add")
def admin_groupes_add(
    nom: str = Form(...), 
    description: Optional[str] = Form(None),
    capacite_max: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    request: Request = None, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    
    # Vérifier si un groupe avec ce nom existe déjà
    existing = session.exec(select(Groupe).where(Groupe.nom == nom.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un groupe avec ce nom existe déjà")
    
    groupe = Groupe(
        nom=nom.strip(),
        description=description.strip() if description else None,
        capacite_max=int(capacite_max) if capacite_max and capacite_max.strip().isdigit() else None,
        actif=(actif != "off")
    )
    session.add(groupe)
    log_activity(session, user=current_user, action="GROUPE_CREATE", entity="Groupe", entity_id=groupe.id,
                 activity_data={"nom": groupe.nom, "capacite_max": groupe.capacite_max}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_groupes')}?success=1&action=add&t={timestamp}", status_code=303)

@router.post("/groupes/{groupe_id}/update")
def admin_groupes_update(
    groupe_id: int,
    nom: str = Form(...),
    description: Optional[str] = Form(None),
    capacite_max: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    groupe = session.get(Groupe, groupe_id)
    if not groupe:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    
    # Vérifier si un autre groupe avec ce nom existe déjà
    existing = session.exec(select(Groupe).where(
        Groupe.nom == nom.strip(),
        Groupe.id != groupe_id
    )).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un autre groupe avec ce nom existe déjà")
    
    # Sauvegarder les anciennes valeurs pour le log
    old_values = {
        "nom": groupe.nom,
        "description": groupe.description,
        "capacite_max": groupe.capacite_max,
        "actif": groupe.actif
    }
    
    # Mettre à jour les champs
    groupe.nom = nom.strip()
    groupe.description = description.strip() if description else None
    groupe.capacite_max = int(capacite_max) if capacite_max and capacite_max.strip().isdigit() else None
    groupe.actif = (actif != "off")
    groupe.date_modification = datetime.now(timezone.utc)
    
    session.add(groupe)
    log_activity(session, user=current_user, action="GROUPE_UPDATE", entity="Groupe", entity_id=groupe.id,
                 activity_data={"old": old_values, "new": {
                     "nom": groupe.nom,
                     "description": groupe.description,
                     "capacite_max": groupe.capacite_max,
                     "actif": groupe.actif
                 }}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_groupes')}?success=1&action=update&t={timestamp}", status_code=303)

@router.post("/groupes/{groupe_id}/toggle")
def admin_groupes_toggle(groupe_id: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    groupe = session.get(Groupe, groupe_id)
    if not groupe:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    
    groupe.actif = not bool(groupe.actif)
    groupe.date_modification = datetime.now(timezone.utc)
    log_activity(session, user=current_user, action="GROUPE_TOGGLE", entity="Groupe", entity_id=groupe.id,
                activity_data={"nom": groupe.nom, "actif": groupe.actif}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_groupes')}?success=1&action=toggle&t={timestamp}", status_code=303)

@router.post("/groupes/{groupe_id}/delete")
def admin_groupes_delete(
    groupe_id: int,
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    groupe = session.get(Groupe, groupe_id)
    if not groupe:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    
    # Vérifier si le groupe est utilisé dans des décisions de jury - Version sécurisée
    try:
        decisions_count = session.exec(
            select(func.count(DecisionJuryCandidat.id)).where(DecisionJuryCandidat.groupe_id == groupe_id)
        ).first()
    except Exception as e:
        logger.warning(f"Erreur lors de la vérification des décisions de jury: {e}")
        decisions_count = 0
    if decisions_count > 0:
        timestamp = int(datetime.now(timezone.utc).timestamp())
        return RedirectResponse(
            url=f"/admin/groupes?error=1&message=Impossible de supprimer le groupe '{groupe.nom}' car il est utilisé dans {decisions_count} décision(s) de jury. Veuillez d'abord réassigner ces décisions.&t={timestamp}", 
            status_code=303
        )
    
    # Sauvegarder les informations pour le log avant suppression
    groupe_nom = groupe.nom
    
    try:
        session.delete(groupe)
        session.commit()
        
        log_activity(session, user=current_user, action="GROUPE_DELETE", entity="Groupe", entity_id=groupe_id,
                     activity_data={"deleted_groupe_nom": groupe_nom}, request=request)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression du groupe")
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"{request.url_for('admin_groupes')}?success=1&action=delete&t={timestamp}", status_code=303)

# ===== ARCHIVES =====
@router.get("/archives/iframe", response_class=HTMLResponse, name="admin_archives_iframe")
def admin_archives_iframe(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    """Version iframe de la page archives (sans layout complet)."""
    admin_required(current_user)
    configure_schema(session, request)

    archive_service = ArchiveService(session)
    archives = []
    try:
        archives = archive_service.get_archive_list()
    except Exception as exc:
        logger.warning("Erreur lors de la récupération des archives (iframe): %s", exc)

    return templates.TemplateResponse(
        "admin/archives_iframe.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "archives": archives,
        },
    )


@router.get("/archives", response_class=HTMLResponse, name="admin_archives")
def admin_archives(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    request.state.admin_title = "Gestion des archives"
    configure_schema(session, request)

    archive_service = ArchiveService(session)
    archives = []
    try:
        archives = archive_service.get_archive_list()
    except Exception as exc:
        logger.warning("Erreur lors de la récupération des archives: %s", exc)

    return templates.TemplateResponse(
        "admin/archives.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "archives": archives,
            "archive_types": list(TypeArchive),
            "archive_statuses": list(StatutArchive),
        },
    )


# ===== ARCHIVES - NETTOYAGE, EXPORT, IMPORT =====
@router.post("/archives/cleanup")
def admin_archives_cleanup(
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    
    archive_service = ArchiveService(session)
    try:
        cleanup_stats = archive_service.cleanup_old_data(current_user)
        log_activity(session, user=current_user, action="ARCHIVE_CLEANUP", entity="Archive", entity_id=None,
                     activity_data={"cleanup_stats": cleanup_stats}, request=request)
        return RedirectResponse(url=request.url_for("admin_archives") + "?success=cleanup_completed", status_code=303)
    except Exception as e:
        log_activity(session, user=current_user, action="ARCHIVE_CLEANUP_FAILED", entity="Archive", entity_id=None,
                     activity_data={"error": str(e)}, request=request)
        return RedirectResponse(url=request.url_for("admin_archives") + "?error=cleanup_failed", status_code=303)

@router.get("/archives/{archive_id}/download")
def admin_archives_download(
    archive_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, None)
    
    archive_service = ArchiveService(session)
    archive = session.get(Archive, archive_id)
    
    if not archive:
        raise HTTPException(status_code=404, detail="Archive introuvable")
    
    if archive.statut != StatutArchive.TERMINE:
        raise HTTPException(status_code=400, detail="L'archive n'est pas terminée")
    
    if not archive.chemin_fichier or not os.path.exists(archive.chemin_fichier):
        raise HTTPException(status_code=404, detail="Fichier d'archive introuvable")
    
    # Log de téléchargement
    log_activity(session, user=current_user, action="ARCHIVE_DOWNLOAD", entity="Archive", entity_id=archive_id,
                 activity_data={"archive_nom": archive.nom, "archive_type": archive.type_archive.value})
    
    return FileResponse(
        path=archive.chemin_fichier,
        filename=f"{archive.nom}.zip",
        media_type="application/zip"
    )

@router.post("/archives/export")
def admin_archives_export(
    export_type: str = Form(...),
    description: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    
    archive_service = ArchiveService(session)
    
    try:
        print(f"🔄 [EXPORT] Début de l'export - Type: {export_type}, Description: {description}")
        print(f"🔄 [EXPORT] Utilisateur: {current_user.email}")
        
        # Vérifier que le dossier archives existe
        from pathlib import Path
        archive_dir = Path("archives")
        if not archive_dir.exists():
            print(f"📁 [EXPORT] Création du dossier archives...")
            archive_dir.mkdir(exist_ok=True)
        
        print(f"📁 [EXPORT] Dossier archives: {archive_dir.absolute()}")
        
        if export_type == "data_only":
            print(f"🔄 [EXPORT] Création export données...")
            archive = archive_service.create_data_export(current_user, description)
        elif export_type == "files_only":
            print(f"🔄 [EXPORT] Création export fichiers...")
            archive = archive_service.create_files_export(current_user, description)
        elif export_type == "full_backup":
            print(f"🔄 [EXPORT] Création sauvegarde complète...")
            archive = archive_service.create_full_backup(current_user, description)
        else:
            raise HTTPException(status_code=400, detail="Type d'export invalide")
        
        print(f"📦 [EXPORT] Archive créée: {archive}")
        
        if archive:
            print(f"📊 [EXPORT] Détails archive:")
            print(f"   - ID: {archive.id}")
            print(f"   - Nom: {archive.nom}")
            print(f"   - Statut: {archive.statut}")
            print(f"   - Chemin: {archive.chemin_fichier}")
            print(f"   - Taille: {archive.taille_fichier}")
            print(f"   - Message erreur: {archive.message_erreur}")
        
        if archive and archive.statut == StatutArchive.TERMINE and archive.chemin_fichier:
            print(f"✅ [EXPORT] Export réussi - Fichier: {archive.chemin_fichier}")
            
            # Vérifier que le fichier existe
            file_path = Path(archive.chemin_fichier)
            if not file_path.exists():
                print(f"❌ [EXPORT] Fichier non trouvé: {archive.chemin_fichier}")
                return RedirectResponse(url=request.url_for("admin_archives") + "?error=file_not_found", status_code=303)
            
            print(f"✅ [EXPORT] Fichier trouvé, taille: {file_path.stat().st_size} bytes")
            
            # Log de l'export
            log_activity(session, user=current_user, action="ARCHIVE_EXPORT", entity="Archive", entity_id=archive.id,
                         activity_data={"export_type": export_type, "description": description}, request=request)
            
            # Télécharger directement le fichier
            return FileResponse(
                path=archive.chemin_fichier,
                filename=f"{archive.nom}.zip",
                media_type="application/zip"
            )
        else:
            print(f"❌ [EXPORT] Échec de l'export - Archive: {archive}")
            if archive:
                print(f"   Statut: {archive.statut}")
                print(f"   Chemin: {archive.chemin_fichier}")
                print(f"   Message erreur: {archive.message_erreur}")
            return RedirectResponse(url=request.url_for("admin_archives") + "?error=export_failed", status_code=303)
            
    except Exception as e:
        print(f"💥 [EXPORT] Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        
        log_activity(session, user=current_user, action="ARCHIVE_EXPORT_FAILED", entity="Archive", entity_id=None,
                     activity_data={"export_type": export_type, "error": str(e)}, request=request)
        return RedirectResponse(url=request.url_for("admin_archives") + "?error=export_failed", status_code=303)

@router.post("/archives/import")
def admin_archives_import(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    description: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    
    # Vérifier le type de fichier
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers ZIP sont acceptés")
    
    # Vérifier la taille du fichier (max 100MB)
    if file.size and file.size > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 100MB)")
    
    archive_service = ArchiveService(session)
    
    try:
        # Sauvegarder le fichier temporairement
        import tempfile
        import shutil
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        # Créer l'enregistrement d'archive
        archive = Archive(
            nom=f"Import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type_archive=TypeArchive(import_type),
            statut=StatutArchive.EN_COURS,
            description=description or f"Import {import_type}",
            cree_par=current_user.id,
            chemin_fichier=tmp_path,
            metadonnees={"import_source": file.filename, "import_type": import_type}
        )
        
        session.add(archive)
        session.commit()
        
        # Traiter l'import en arrière-plan
        try:
            if import_type == "data_only":
                result = archive_service.import_data_from_archive(archive, current_user)
            elif import_type == "files_only":
                result = archive_service.import_files_from_archive(archive, current_user)
            elif import_type == "full_backup":
                result = archive_service.import_full_backup(archive, current_user)
            else:
                raise ValueError(f"Type d'import invalide: {import_type}")
            
            if result:
                archive.statut = StatutArchive.TERMINE
                archive.termine_le = datetime.now(timezone.utc)
                log_activity(session, user=current_user, action="ARCHIVE_IMPORT_SUCCESS", entity="Archive", entity_id=archive.id,
                             activity_data={"import_type": import_type, "source_file": file.filename}, request=request)
            else:
                archive.statut = StatutArchive.ECHEC
                archive.message_erreur = "Échec de l'import"
                log_activity(session, user=current_user, action="ARCHIVE_IMPORT_FAILED", entity="Archive", entity_id=archive.id,
                             activity_data={"import_type": import_type, "error": "Import failed"}, request=request)
            
        except Exception as e:
            archive.statut = StatutArchive.ECHEC
            archive.message_erreur = str(e)
            log_activity(session, user=current_user, action="ARCHIVE_IMPORT_FAILED", entity="Archive", entity_id=archive.id,
                         activity_data={"import_type": import_type, "error": str(e)}, request=request)
        
        session.commit()
        
        # Nettoyer le fichier temporaire
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        return RedirectResponse(url=request.url_for("admin_archives") + "?success=import_completed", status_code=303)
        
    except Exception as e:
        # Nettoyer le fichier temporaire en cas d'erreur
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        
        log_activity(session, user=current_user, action="ARCHIVE_IMPORT_ERROR", entity="Archive", entity_id=None,
                     activity_data={"import_type": import_type, "error": str(e)}, request=request)
        return RedirectResponse(url=request.url_for("admin_archives") + "?error=import_failed", status_code=303)

@router.post("/archives/bulk-delete")
def admin_archives_bulk_delete(
    archive_ids: str = Form(...),  # Liste d'IDs séparés par des virgules
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    configure_schema(session, request)
    
    try:
        ids = [int(id.strip()) for id in archive_ids.split(',') if id.strip()]
        if not ids:
            raise HTTPException(status_code=400, detail="Aucun ID d'archive fourni")
        
        archive_service = ArchiveService(session)
        deleted_count = 0
        
        for archive_id in ids:
            archive = session.get(Archive, archive_id)
            if archive:
                try:
                    # Supprimer le fichier physique
                    if archive.chemin_fichier and os.path.exists(archive.chemin_fichier):
                        os.unlink(archive.chemin_fichier)
                    
                    # Supprimer l'enregistrement
                    session.delete(archive)
                    deleted_count += 1
                    
                    log_activity(session, user=current_user, action="ARCHIVE_BULK_DELETE", entity="Archive", entity_id=archive_id,
                                 activity_data={"archive_nom": archive.nom}, request=request)
                    
                except Exception as e:
                    print(f"Erreur lors de la suppression de l'archive {archive_id}: {e}")
        
        session.commit()
        
        return RedirectResponse(url=f"{request.url_for('admin_archives')}?success=bulk_delete_completed&count={deleted_count}", status_code=303)
        
    except Exception as e:
        log_activity(session, user=current_user, action="ARCHIVE_BULK_DELETE_FAILED", entity="Archive", entity_id=None,
                     activity_data={"error": str(e)}, request=request)
        return RedirectResponse(url=request.url_for("admin_archives") + "?error=bulk_delete_failed", status_code=303)
