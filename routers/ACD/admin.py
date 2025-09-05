# app/routers/admin.py (version avec logs intégrés)
from __future__ import annotations

from datetime import datetime, timezone
import time
from sqlalchemy import func, delete
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, and_
from sqlmodel import Session, select
import os
from pathlib import Path

from ...core.database import get_session
from ...core.config import settings
from ...core.security import get_current_user
from ...templates import templates

from ...models.base import (
    User, UserRole, TypeUtilisateur,
    Programme, EtapePipeline, Preinscription, Inscription, Jury, ProgrammeUtilisateur
)
from ...models.ACD.admin import AppSetting
from ...models.ACD.activity import ActivityLog
from ...services.ACD.audit import log_activity
from ...models.enums import UserRole as UserRoleEnum

router = APIRouter()

# Fonction pour sauvegarder les photos de profil
def save_profile_photo(photo: UploadFile, user_id: int, old_photo_path: str = None) -> str:
    """Sauvegarde une photo de profil et retourne le chemin relatif"""
    print(f"🔍 [DEBUG] save_profile_photo appelée avec user_id={user_id}, filename={photo.filename}")
    
    # Créer le dossier media/users s'il n'existe pas
    media_dir = Path("media/users")
    print(f"📁 [DEBUG] Création du dossier: {media_dir}")
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Supprimer l'ancienne photo si elle existe
    if old_photo_path:
        try:
            old_file_path = Path("." + old_photo_path)  # Ajouter le point pour le chemin relatif
            if old_file_path.exists():
                print(f"🗑️ [DEBUG] Suppression de l'ancienne photo: {old_file_path}")
                old_file_path.unlink()
                print(f"✅ [DEBUG] Ancienne photo supprimée avec succès")
            else:
                print(f"⚠️ [DEBUG] Ancienne photo introuvable: {old_file_path}")
        except Exception as e:
            print(f"❌ [DEBUG] Erreur lors de la suppression de l'ancienne photo: {e}")
    
    # Générer le nom de fichier
    ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
    filename = f"user_{user_id}_profile{ext}"
    file_path = media_dir / filename
    print(f"📄 [DEBUG] Nom de fichier généré: {filename}")
    print(f"📄 [DEBUG] Chemin complet: {file_path}")
    
    # Sauvegarder le fichier
    try:
        print(f"💾 [DEBUG] Lecture du contenu du fichier...")
        content = photo.file.read()
        print(f"💾 [DEBUG] Taille du contenu: {len(content)} bytes")
        
        print(f"💾 [DEBUG] Écriture du fichier...")
        with open(file_path, "wb") as f:
            f.write(content)
        print(f"✅ [DEBUG] Fichier sauvegardé avec succès")
        
    except Exception as e:
        print(f"❌ [DEBUG] Erreur lors de la sauvegarde: {e}")
        raise e
    
    # Retourner le chemin relatif pour l'affichage
    relative_path = f"/media/users/{filename}"
    print(f"🔗 [DEBUG] Chemin relatif retourné: {relative_path}")
    return relative_path

# -------- RBAC --------
def admin_required(user: User):
    allowed = {getattr(UserRole, "ADMINISTRATEUR", None), getattr(UserRole, "GENERAL_MANAGER", None)}
    if user is None or user.role not in allowed:
        raise HTTPException(status_code=403, detail="Accès restreint")
    return user

# ===== DASHBOARD =====
@router.get("/", response_class=HTMLResponse)
def admin_home(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)

    total_prog = session.exec(select(func.count(Programme.id))).one() or 0
    total_pre = session.exec(select(func.count(Preinscription.id))).one() or 0
    total_insc = session.exec(select(func.count(Inscription.id))).one() or 0
    total_users = session.exec(select(func.count(User.id))).one() or 0

    jurys_next = session.exec(select(Jury).where(Jury.session_le >= datetime.now(timezone.utc)).order_by(Jury.session_le)).all()

    insc_by_prog = session.exec(
        select(Programme.code, func.count(Inscription.id))
        .join(Inscription, isouter=True)
        .group_by(Programme.code)
        .order_by(Programme.code)
    ).all()

    return templates.TemplateResponse(
        "ACD/admin/dashboard.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "kpi": {
                "programmes": int(total_prog),
                "preinscriptions": int(total_pre),
                "inscriptions": int(total_insc),
                "utilisateurs": int(total_users),
            },
            "jurys_next": jurys_next,
            "insc_by_prog": insc_by_prog,
        },
    )

# ===== PROGRAMMES =====
@router.get("/programmes", response_class=HTMLResponse)
def admin_programmes(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
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
        # Exclure le responsable et les utilisateurs déjà affectés
        excluded_user_ids = {prog.responsable_id} if prog.responsable_id else set()
        excluded_user_ids.update(pu.utilisateur_id for pu in prog.utilisateurs)
        
        users_disponibles_par_programme[prog.id] = [user for user in users if user.id not in excluded_user_ids]
        
        # Convertir les membres d'équipe en dictionnaires pour JSON
        membres_equipe_par_programme[prog.id] = [
            {
                "utilisateur_id": pu.utilisateur_id,
                "role_programme": pu.role_programme.value if hasattr(pu.role_programme, 'value') else str(pu.role_programme)
            }
            for pu in prog.utilisateurs
        ]
        
        # Récupérer les étapes du pipeline pour ce programme
        etapes_par_programme[prog.id] = session.exec(select(EtapePipeline).where(EtapePipeline.programme_id == prog.id).order_by(EtapePipeline.ordre)).all()
    
    timestamp = int(time.time())
    return templates.TemplateResponse("ACD/admin/programmes_list.html", {
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

@router.get("/programmes/new", response_class=HTMLResponse)
def admin_programme_new(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    # Récupérer tous les utilisateurs actifs pour le dropdown responsable
    users = session.exec(select(User).where(User.actif == True).order_by(User.nom_complet)).all()
    
    # Filtrer les utilisateurs déjà responsables d'autres programmes
    responsables_existants = session.exec(select(Programme.responsable_id).where(Programme.responsable_id.is_not(None))).all()
    responsables_existants = [r for r in responsables_existants if r is not None]
    
    users_disponibles = [user for user in users if user.id not in responsables_existants]
    
    return templates.TemplateResponse("ACD/admin/programme_form.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "prog": None,
        "users": users_disponibles,
        "UserRole": UserRoleEnum
    })

@router.get("/programmes/{prog_id}", response_class=HTMLResponse)
def admin_programme_edit(prog_id: int, request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    prog = session.get(Programme, prog_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    steps = session.exec(select(EtapePipeline).where(EtapePipeline.programme_id == prog.id).order_by(EtapePipeline.ordre)).all()
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
    return templates.TemplateResponse("ACD/admin/programme_form.html", {
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

@router.post("/programmes/save")
def admin_programme_save(
    request: Request,
    session: Session = Depends(get_session),
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
    
    # Traiter les membres d'équipe pour les nouveaux programmes
    if creating:
        print(f"👥 [DEBUG] Traitement des membres d'équipe pour le nouveau programme...")
        # Récupérer tous les paramètres de formulaire
        form_data = dict(request.form())
        
        # Chercher les membres d'équipe dans les données du formulaire
        team_members = []
        index = 0
        while f"team_member_{index}_user_id" in form_data:
            user_id = form_data.get(f"team_member_{index}_user_id")
            role = form_data.get(f"team_member_{index}_role")
            if user_id and role:
                team_members.append({
                    "user_id": int(user_id),
                    "role": role
                })
            index += 1
        
        print(f"👥 [DEBUG] {len(team_members)} membres d'équipe trouvés")
        
        # Créer les entrées ProgrammeUtilisateur
        for member in team_members:
            try:
                pu = ProgrammeUtilisateur(
                    programme_id=prog.id,
                    utilisateur_id=member["user_id"],
                    role_programme=member["role"]
                )
                session.add(pu)
                print(f"✅ [DEBUG] Membre d'équipe ajouté: utilisateur_id={member['user_id']}, rôle={member['role']}")
            except Exception as e:
                print(f"❌ [DEBUG] Erreur lors de l'ajout du membre d'équipe: {e}")
    
    # log
    log_activity(session, user=current_user,
                 action="PROGRAMME_CREATE" if creating else "PROGRAMME_UPDATE",
                 entity="Programme", entity_id=prog.id,
                 activity_data={"code": prog.code, "nom": prog.nom}, request=request)
    session.commit()
    print(f"✅ [DEBUG] Programme sauvegardé avec succès")
    
    timestamp = int(time.time())
    action = "add" if creating else "update"
    return RedirectResponse(url=f"/admin/programmes?success=1&action={action}&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/update")
def admin_programme_update(
    prog_id: int,
    request: Request,
    session: Session = Depends(get_session),
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
    return RedirectResponse(url=f"/admin/programmes?success=1&action=update&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/delete")
def admin_programme_delete(
    prog_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    prog = session.get(Programme, prog_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    
    # Vérifier s'il y a des inscriptions liées
    inscriptions_count = session.exec(select(func.count(Inscription.id)).where(Inscription.programme_id == prog_id)).first()
    if inscriptions_count > 0:
        raise HTTPException(status_code=400, detail=f"Impossible de supprimer le programme {prog.code} : {inscriptions_count} inscription(s) liée(s)")
    
    # Supprimer les étapes du pipeline
    session.exec(delete(EtapePipeline).where(EtapePipeline.programme_id == prog_id))
    
    # Supprimer le programme
    session.delete(prog)
    log_activity(session, user=current_user,
                 action="PROGRAMME_DELETE",
                 entity="Programme", entity_id=prog_id,
                 activity_data={"code": prog.code, "nom": prog.nom}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"/admin/programmes?success=1&action=delete&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/etapes/add")
def admin_programme_add_step(
    prog_id: int,
    request: Request,
    libelle: str = Form(...),
    code: str = Form(...),
    ordre: int = Form(...),
    type_etape: Optional[str] = Form(None),
    active: Literal["on", "off", ""] = Form("on"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    prog = session.get(Programme, prog_id)
    if not prog: raise HTTPException(status_code=404, detail="Programme introuvable")
    st = EtapePipeline(programme_id=prog.id, libelle=libelle, code=code, ordre=int(ordre), type_etape=type_etape, active=(active != "off"))
    session.add(st)
    log_activity(session, user=current_user, action="STEP_ADD", entity="EtapePipeline", entity_id=None,
                 activity_data={"programme_id": prog.id, "libelle": libelle, "code": code, "ordre": int(ordre)}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"/admin/programmes?success=1&action=add_step&prog_id={prog_id}&t={timestamp}", status_code=303)

@router.post("/etapes/{step_id}/update")
def admin_step_update(
    step_id: int,
    request: Request,
    libelle: str = Form(...),
    code: str = Form(...),
    ordre: int = Form(...),
    type_etape: Optional[str] = Form(None),
    active: Literal["on", "off", ""] = Form("on"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    st = session.get(EtapePipeline, step_id)
    if not st: raise HTTPException(status_code=404, detail="Étape introuvable")
    st.libelle = libelle; st.code = code; st.ordre = int(ordre); st.type_etape = type_etape; st.active = (active != "off")
    log_activity(session, user=current_user, action="STEP_UPDATE", entity="EtapePipeline", entity_id=st.id,
                activity_data={"programme_id": st.programme_id, "libelle": libelle, "code": code, "ordre": int(ordre)}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"/admin/programmes?success=1&action=update_step&prog_id={st.programme_id}&t={timestamp}", status_code=303)

@router.post("/etapes/{step_id}/delete")
def admin_step_delete(step_id: int, request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    st = session.get(EtapePipeline, step_id)
    if not st: raise HTTPException(status_code=404, detail="Étape introuvable")
    prog_id = st.programme_id
    session.delete(st)
    log_activity(session, user=current_user, action="STEP_DELETE", entity="EtapePipeline", entity_id=step_id,
                 activity_data={"programme_id": prog_id}, request=request)
    session.commit()
    timestamp = int(time.time())
    return RedirectResponse(url=f"/admin/programmes?success=1&action=remove_step&prog_id={prog_id}&t={timestamp}", status_code=303)

# ===== UTILISATEURS DU PROGRAMME =====
@router.post("/programmes/{prog_id}/utilisateurs/add")
def admin_programme_add_user(
    prog_id: int,
    request: Request,
    utilisateur_id: int = Form(...),
    role_programme: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
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
    return RedirectResponse(url=f"/admin/programmes?success=1&action=add_member&prog_id={prog_id}&t={timestamp}", status_code=303)

@router.post("/programmes/{prog_id}/utilisateurs/{user_id}/delete")
def admin_programme_remove_user(
    prog_id: int,
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
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
    return RedirectResponse(url=f"/admin/programmes?success=1&action=remove_member&prog_id={prog_id}&t={timestamp}", status_code=303)

# ===== UTILISATEURS =====
@router.get("/users", response_class=HTMLResponse)
def admin_users(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user), q: Optional[str] = Query(None)):
    admin_required(current_user)
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.email.ilike(like)) | (User.nom_complet.ilike(like)))
    users = session.exec(stmt.order_by(User.cree_le.desc())).all()
    
    # Ajouter un timestamp pour le cache-busting des images
    timestamp = int(datetime.now(timezone.utc).timestamp())
    
    return templates.TemplateResponse("ACD/admin/users.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "users": users, 
        "q": q or "",
        "timestamp": timestamp
    })

@router.post("/users/add")
def admin_users_add(
    email: str = Form(...), 
    nom_complet: str = Form(...), 
    telephone: Optional[str] = Form(None),
    role: str = Form(...),
    type_utilisateur: str = Form("INTERNE"),
    mot_de_passe: Optional[str] = Form(None),
    photo_profil: UploadFile | None = File(None),
    request: Request = None, 
    session: Session = Depends(get_session), 
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    from ...core.security import get_password_hash
    if session.exec(select(User).where(User.email==email)).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    try: r = getattr(UserRole, role)
    except Exception: r = getattr(UserRole, "CONSEILLER", list(UserRole)[0])
    
    try: t = getattr(TypeUtilisateur, type_utilisateur)
    except Exception: t = TypeUtilisateur.INTERNE
    
    # Utiliser le mot de passe fourni ou le défaut
    password = mot_de_passe if mot_de_passe else "ChangeMe123!"
    
    u = User(
        email=email, 
        nom_complet=nom_complet, 
        telephone=telephone,
        role=r, 
        type_utilisateur=t,
        mot_de_passe_hash=get_password_hash(password)
    )
    session.add(u)
    session.flush()  # Pour obtenir l'ID de l'utilisateur
    
    # Sauvegarder la photo de profil si fournie
    if photo_profil and photo_profil.filename:
        try:
            photo_path = save_profile_photo(photo_profil, u.id, None)  # Pas d'ancienne photo lors de la création
            u.photo_profil = photo_path
        except Exception as e:
            # En cas d'erreur, continuer sans photo
            pass
    
    log_activity(session, user=current_user, action="USER_ADD", entity="User", entity_id=None,
                 activity_data={"email": email, "role": role, "type_utilisateur": type_utilisateur}, request=request)
    session.commit()
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"/admin/users?success=1&action=add&t={timestamp}", status_code=303)

@router.post("/users/{uid}/toggle")
def admin_users_toggle(uid: int, request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    u = session.get(User, uid)
    if not u: raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    u.actif = not bool(u.actif)
    log_activity(session, user=current_user, action="USER_TOGGLE", entity="User", entity_id=u.id,
                activity_data={"active": u.actif}, request=request)
    session.commit()
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"/admin/users?success=1&action=toggle&t={timestamp}", status_code=303)

@router.post("/users/{uid}/update")
def admin_users_update(
    uid: int,
    nom_complet: str = Form(...),
    email: str = Form(...),
    telephone: Optional[str] = Form(None),
    role: str = Form(...),
    type_utilisateur: str = Form(...),
    mot_de_passe: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
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
        "role": u.role.name,
        "type_utilisateur": u.type_utilisateur.name
    }
    
    # Mettre à jour les champs
    u.nom_complet = nom_complet
    u.email = email
    u.telephone = telephone if telephone.strip() else None
    
    try: u.role = getattr(UserRole, role)
    except Exception: pass
    
    try: u.type_utilisateur = getattr(TypeUtilisateur, type_utilisateur)
    except Exception: pass
    
    # Mettre à jour le mot de passe si fourni
    if mot_de_passe and mot_de_passe.strip():
        from ...core.security import get_password_hash
        u.mot_de_passe_hash = get_password_hash(mot_de_passe)
        old_values["password_changed"] = True
    
    # Log des modifications
    log_activity(session, user=current_user, action="USER_UPDATE", entity="User", entity_id=u.id,
                 activity_data={"old": old_values, "new": {
                     "nom_complet": u.nom_complet,
                     "email": u.email,
                     "telephone": u.telephone,
                     "role": u.role.name,
                     "type_utilisateur": u.type_utilisateur.name,
                     "password_changed": mot_de_passe and mot_de_passe.strip() != ""
                                   }}, request=request)
    
    session.commit()
    # Redirection avec message de succès
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return RedirectResponse(url=f"/admin/users?success=1&action=update&t={timestamp}", status_code=303)

# ===== JURYS =====
@router.get("/jurys", response_class=HTMLResponse)
def admin_jurys(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    jurys = session.exec(select(Jury).order_by(Jury.session_le.desc())).all()
    progs = session.exec(select(Programme).order_by(Programme.code)).all()
    return templates.TemplateResponse("admin/jurys.html", {"request": request, "settings": settings, "utilisateur": current_user, "jurys": jurys, "progs": progs})

@router.post("/jurys/add")
def admin_jurys_add(programme_id: int = Form(...), session_le: str = Form(...), lieu: Optional[str] = Form(None),
                    request: Request = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    prog = session.get(Programme, programme_id)
    if not prog: raise HTTPException(status_code=404, detail="Programme introuvable")
    dt = datetime.fromisoformat(session_le)
    j = Jury(programme_id=prog.id, session_le=dt, lieu=lieu or None, statut="planifie")
    session.add(j)
    log_activity(session, user=current_user, action="JURY_ADD", entity="Jury", entity_id=None,
                 activity_data={"programme_id": prog.id, "session_le": session_le, "lieu": lieu}, request=request)
    session.commit()
    return RedirectResponse(url="/admin/jurys", status_code=303)

# ===== PARAMÈTRES =====
@router.get("/settings", response_class=HTMLResponse)
def admin_settings(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    def getv(k, default=""):
        x = session.exec(select(AppSetting).where(AppSetting.key==k)).first()
        return x.value if x else default
    ctx = {
        "THEME_PRIMARY": getv("THEME_PRIMARY", getattr(settings, "THEME_PRIMARY", "#ffd300")),
        "THEME_SECONDARY": getv("THEME_SECONDARY", getattr(settings, "THEME_SECONDARY", "#111827")),
        "MAX_UPLOAD_SIZE_MB": getv("MAX_UPLOAD_SIZE_MB", str(getattr(settings, "MAX_UPLOAD_SIZE_MB", 5))),
        "SMTP_HOST": getv("SMTP_HOST", getattr(settings, "SMTP_HOST", "")),
        "SMTP_PORT": getv("SMTP_PORT", str(getattr(settings, "SMTP_PORT", ""))),
        "SMTP_USER": getv("SMTP_USER", getattr(settings, "SMTP_USER", "")),
        "SMTP_TLS": getv("SMTP_TLS", str(getattr(settings, "SMTP_TLS", True))),
    }
    return templates.TemplateResponse("admin/settings.html", {"request": request, "settings": settings, "utilisateur": current_user, "cfg": ctx})

@router.post("/settings/save")
def admin_settings_save(
    THEME_PRIMARY: Optional[str] = Form(None),
    THEME_SECONDARY: Optional[str] = Form(None),
    MAX_UPLOAD_SIZE_MB: Optional[str] = Form(None),
    SMTP_HOST: Optional[str] = Form(None),
    SMTP_PORT: Optional[str] = Form(None),
    SMTP_USER: Optional[str] = Form(None),
    SMTP_TLS: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin_required(current_user)
    def upsert(k: str, v: Optional[str]):
        if v is None: return
        row = session.exec(select(AppSetting).where(AppSetting.key==k)).first()
        if not row:
            row = AppSetting(key=k, value=v); session.add(row)
        else:
            row.value = v; row.updated_at = datetime.now(timezone.utc)

    upsert("THEME_PRIMARY", THEME_PRIMARY)
    upsert("THEME_SECONDARY", THEME_SECONDARY)
    upsert("MAX_UPLOAD_SIZE_MB", MAX_UPLOAD_SIZE_MB)
    upsert("SMTP_HOST", SMTP_HOST)
    upsert("SMTP_PORT", SMTP_PORT)
    upsert("SMTP_USER", SMTP_USER)
    upsert("SMTP_TLS", SMTP_TLS)

    # log
    log_activity(session, user=current_user, action="SETTINGS_SAVE", entity="AppSetting", entity_id=None,
                 activity_data={"keys": ["THEME_PRIMARY","THEME_SECONDARY","MAX_UPLOAD_SIZE_MB","SMTP_*"]}, request=request)
    session.commit()
    return RedirectResponse(url="/admin/settings", status_code=303)

# ===== LOGS =====
@router.get("/logs", response_class=HTMLResponse)
def admin_logs(
    request: Request,
    session: Session = Depends(get_session),
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
        "ACD/admin/logs.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
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
    session: Session = Depends(get_session),
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

@router.post("/users/{uid}/photo")
def admin_users_photo(
    uid: int, 
    photo_profil: UploadFile = File(...),
    request: Request = None, 
    session: Session = Depends(get_session), 
    current_user: User = Depends(get_current_user)
):
    print(f"🚀 [DEBUG] admin_users_photo appelée avec uid={uid}")
    admin_required(current_user)
    
    print(f"🔍 [DEBUG] Recherche de l'utilisateur avec id={uid}")
    u = session.get(User, uid)
    if not u: 
        print(f"❌ [DEBUG] Utilisateur introuvable avec id={uid}")
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    print(f"✅ [DEBUG] Utilisateur trouvé: {u.email}")
    
    # Sauvegarder la nouvelle photo
    try:
        print(f"📸 [DEBUG] Début de la sauvegarde de la photo...")
        photo_path = save_profile_photo(photo_profil, u.id, u.photo_profil)
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
    return RedirectResponse(url=f"/admin/users?success=1&action=photo&t={timestamp}", status_code=303)

@router.post("/users/{uid}/delete")
def admin_users_delete(
    uid: int,
    request: Request = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    print(f"🚀 [DEBUG] admin_users_delete appelée avec uid={uid}")
    admin_required(current_user)
    
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
    
    # Supprimer la photo de profil si elle existe
    if u.photo_profil:
        try:
            photo_path = Path("." + u.photo_profil)
            if photo_path.exists():
                print(f"🗑️ [DEBUG] Suppression de la photo de profil: {photo_path}")
                photo_path.unlink()
                print(f"✅ [DEBUG] Photo de profil supprimée")
        except Exception as e:
            print(f"⚠️ [DEBUG] Erreur lors de la suppression de la photo: {e}")
    
    # Sauvegarder les informations pour le log avant suppression
    user_email = u.email
    user_name = u.nom_complet
    
    try:
        print(f"🗑️ [DEBUG] Suppression de l'utilisateur de la base de données")
        session.delete(u)
        session.commit()
        print(f"✅ [DEBUG] Utilisateur supprimé avec succès")
        
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
    return RedirectResponse(url=f"/admin/users?success=1&action=delete&t={timestamp}", status_code=303)
