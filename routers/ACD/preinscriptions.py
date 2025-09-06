# app/routers/preinscriptions.py
from __future__ import annotations

import os
import re
import uuid
import shutil
from datetime import datetime, timezone, date as _date
from pathlib import Path
from typing import Optional, Set

from fastapi import (
    APIRouter, Request, Depends, Form, HTTPException,
    BackgroundTasks, Query, UploadFile, File
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ...core.database import get_session
from ...core.config import settings
from ...core.security import get_current_user
from ...templates import templates

from ...models.base import (
    Programme, Candidat, Entreprise, Preinscription, Eligibilite,
    StatutDossier, Document
)

# Enums
try:
    from ...models.enums import TypeDocument  # recommandé
except Exception:
    try:
        from ...models.base import TypeDocument  # fallback si défini là
    except Exception:
        TypeDocument = None  # pas d'enum dispo

from ...models.ACD.preinscription_invite import PreinscriptionInvite
from ...services.ACD.mailer import SmtpMailer, EmailMessage
from ...services.geocoding import geocode_one
from ...services.ACD.eligibilite import evaluate_eligibilite, entreprise_age_annees
from ...services.uploads import validate_upload  # limites taille/type

router = APIRouter()

# ---------- Constantes / helpers ----------
SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Liste proposée au front (si l'enum existe on s'aligne)
if TypeDocument:
    DOC_TYPES_DEFAULT = [td.value for td in TypeDocument]
else:
    DOC_TYPES_DEFAULT = ["CNI", "KBIS", "JUSTIFICATIF_DOMICILE", "RIB", "CV", "DIPLOME", "ATTESTATION", "AUTRE"]


def safe_name(s: str) -> str:
    """Nettoie un titre de document pour le rendre filesystem-friendly."""
    s = (s or "").strip().replace(" ", "_")
    s = SAFE_RE.sub("_", s)
    return s[:120] or "doc"


def ensure_media_root() -> Path:
    """Récupère le MEDIA_ROOT (config) ou 'media' par défaut, et s'assure qu'il existe."""
    root = Path(getattr(settings, "MEDIA_ROOT", "media"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload(dst: Path, file: UploadFile):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)


def coerce_doc_type(value: Optional[str]):
    """Essaie de convertir la chaîne reçue en Enum TypeDocument si possible, sinon renvoie la valeur brute."""
    if not TypeDocument:
        return value  # pas d'enum -> texte libre
    if value is None:
        return getattr(TypeDocument, "AUTRE", list(TypeDocument)[0])
    try:
        return TypeDocument[value]  # par name
    except Exception:
        try:
            return TypeDocument(value)  # par value
        except Exception:
            return getattr(TypeDocument, "AUTRE", list(TypeDocument)[0])


# --------- UI LISTE ---------
@router.get("/preinscriptions/form", response_class=HTMLResponse)
def preinscriptions(
    request: Request,
    session: Session = Depends(get_session),
    programme: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    q: Optional[str] = Query(None),
):
    # Programmes pour filtre
    progs = session.exec(select(Programme).where(Programme.actif.is_(True))).all()

    stmt = (
        select(Preinscription, Candidat, Programme, Entreprise)
        .join(Candidat, Candidat.id == Preinscription.candidat_id)
        .join(Programme, Programme.id == Preinscription.programme_id)
        .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
    )
    if programme:
        stmt = stmt.where(Programme.code == programme)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Candidat.nom.ilike(like))
            | (Candidat.prenom.ilike(like))
            | (Candidat.email.ilike(like))
        )

    rows = session.exec(stmt.order_by(Preinscription.cree_le.desc()).limit(300)).all()

    # KPI pour en-tête
    total = session.exec(select(func.count(Preinscription.id))).one() or 0
    total_acd = (
        session.exec(
            select(func.count(Preinscription.id)).join(Programme).where(Programme.code == "ACD")
        ).one()
        or 0
    )

    # Pins pour carte (lat/lng depuis Entreprise si existant)
    pins = []
    for p, c, prog, e in rows:
        if e and getattr(e, "lat", None) is not None and getattr(e, "lng", None) is not None:
            pins.append(
                {
                    "nom": c.nom,
                    "prenom": c.prenom,
                    "programme": prog.code,
                    "lat": float(e.lat),
                    "lng": float(e.lng),
                    "qpv": bool(getattr(e, "qpv", False)),
                    "adresse": e.adresse or c.adresse_personnelle or "",
                }
            )

    return templates.TemplateResponse(
        "ACD/preinscriptions_list.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "rows": rows,
            "progs": progs,
            "current_programme": programme,
            "q": q or "",
            "kpi": {"total": int(total), "acd": int(total_acd)},
            "pins": pins,
        },
    )

# --------- SOUMISSION (sans token) AVEC UPLOAD PHOTO + DOCS ---------
@router.post("/preinscriptions/submit")
async def preinscription_public_submit(
    request: Request,
    programme_code: str = Form(...),
    civilite: Optional[str] = Form(None),
    nom: str = Form(...),
    prenom: str = Form(...),
    date_naissance: str = Form(...),
    email: str = Form(...),
    telephone: Optional[str] = Form(None),
    adresse_personnelle: str = Form(...),
    adresse_entreprise: Optional[str] = Form(None),
    date_creation_entreprise: Optional[str] = Form(None),
    chiffre_affaire: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    niveau_etudes: Optional[str] = Form(None),
    secteur_activite: Optional[str] = Form(None),
    photo_profil: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    # Logs de surveillance si debug activé
    if settings.DEBUG:
        print(f"🔍 [DEBUG] Route /ACD/preinscriptions/submit appelée")
        print(f"📝 [DEBUG] Données reçues:")
        print(f"   - programme_code: {programme_code}")
        print(f"   - nom: {nom}")
        print(f"   - prenom: {prenom}")
        print(f"   - email: {email}")
        print(f"   - telephone: {telephone}")
        print(f"   - adresse_personnelle: {adresse_personnelle}")
        print(f"   - photo_profil: {photo_profil.filename if photo_profil else 'Aucune'}")
    
    prog = session.exec(select(Programme).where(Programme.code == programme_code)).first()
    if not prog:
        if settings.DEBUG:
            print(f"❌ [DEBUG] Programme '{programme_code}' introuvable")
        
        # Récupérer tous les programmes actifs pour la liste déroulante
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        
        # Retourner une page d'erreur claire au lieu d'une exception
        return templates.TemplateResponse(
            "ACD/preinscription_public_form.html",
            {
                "request": request,
                "settings": settings,
                "programme": None,
                "error": f"Le programme '{programme_code}' n'existe pas dans notre base de données. Veuillez contacter l'administrateur ou choisir un autre programme.",
                "doc_types": DOC_TYPES_DEFAULT,
                "programmes_actifs": programmes_actifs,  # Programmes disponibles
            },
            status_code=400
        )
    
    if settings.DEBUG:
        print(f"✅ [DEBUG] Programme trouvé: {prog.code} - {prog.nom}")

    dn = _date.fromisoformat(date_naissance)
    dce = _date.fromisoformat(date_creation_entreprise) if date_creation_entreprise else None
    try:
        ca_float = float(str(chiffre_affaire).replace(" ", "").replace(",", "."))
    except Exception:
        ca_float = None

    cand = session.exec(select(Candidat).where(Candidat.email == email)).first()
    if not cand:
        if settings.DEBUG:
            print(f"🆕 [DEBUG] Création nouveau candidat: {email}")
        cand = Candidat(email=email, nom=nom, prenom=prenom)
        session.add(cand)
        session.flush()
    else:
        if settings.DEBUG:
            print(f"🔄 [DEBUG] Candidat existant mis à jour: {email}")
    
    # Vérifier si le candidat est déjà inscrit à ce programme
    existing_inscription = session.exec(
        select(Inscription).where(
            (Inscription.candidat_id == cand.id) & 
            (Inscription.programme_id == prog.id)
        )
    ).first()
    
    if existing_inscription:
        if settings.DEBUG:
            print(f"⚠️ [DEBUG] Candidat déjà inscrit au programme {prog.code}")
        
        # Retourner une erreur claire
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        return templates.TemplateResponse(
            "ACD/preinscription_public_form.html",
            {
                "request": request,
                "settings": settings,
                "programme": prog,
                "error": f"Vous êtes déjà inscrit au programme '{prog.code} - {prog.nom}'. Vous ne pouvez vous inscrire qu'une seule fois par programme.",
                "doc_types": DOC_TYPES_DEFAULT,
                "programmes_actifs": programmes_actifs,
            },
            status_code=400
        )
    
    # Vérifier si le candidat est déjà préinscrit à ce programme
    existing_preinscription = session.exec(
        select(Preinscription).where(
            (Preinscription.candidat_id == cand.id) & 
            (Preinscription.programme_id == prog.id)
        )
    ).first()
    
    if existing_preinscription:
        if settings.DEBUG:
            print(f"⚠️ [DEBUG] Candidat déjà préinscrit au programme {prog.code}")
        
        # Retourner une erreur claire
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        return templates.TemplateResponse(
            "ACD/preinscription_public_form.html",
            {
                "request": request,
                "settings": settings,
                "programme": prog,
                "error": f"Vous êtes déjà préinscrit au programme '{prog.code} - {prog.nom}'. Vous ne pouvez vous préinscrire qu'une seule fois par programme.",
                "doc_types": DOC_TYPES_DEFAULT,
                "programmes_actifs": programmes_actifs,
            },
            status_code=400
        )
    
    cand.civilite = civilite
    cand.date_naissance = dn
    cand.telephone = telephone
    cand.adresse_personnelle = adresse_personnelle
    cand.niveau_etudes = niveau_etudes
    cand.secteur_activite = secteur_activite

    ent = session.exec(select(Entreprise).where(Entreprise.candidat_id == cand.id)).first()
    if not ent:
        if settings.DEBUG:
            print(f"🏢 [DEBUG] Création nouvelle entreprise pour candidat {cand.id}")
        ent = Entreprise(candidat_id=cand.id)
        session.add(ent)
        session.flush()
    else:
        if settings.DEBUG:
            print(f"🏢 [DEBUG] Entreprise existante mise à jour pour candidat {cand.id}")
    
    ent.adresse = adresse_entreprise
    ent.date_creation = dce
    ent.siret = siret
    ent.chiffre_affaires = ca_float

    addr_for_geo = adresse_entreprise or adresse_personnelle
    if addr_for_geo:
        if settings.DEBUG:
            print(f"🗺️ [DEBUG] Géocodage de l'adresse: {addr_for_geo}")
        latlng = await geocode_one(addr_for_geo)
        if latlng:
            ent.lat, ent.lng = latlng
            if settings.DEBUG:
                print(f"✅ [DEBUG] Coordonnées trouvées: lat={latlng[0]}, lng={latlng[1]}")
        else:
            if settings.DEBUG:
                print(f"⚠️ [DEBUG] Géocodage échoué pour: {addr_for_geo}")

    pre = Preinscription(programme_id=prog.id, candidat_id=cand.id, source="formulaire")
    session.add(pre)
    session.flush()
    
    if settings.DEBUG:
        print(f"📝 [DEBUG] Préinscription créée avec ID: {pre.id}")

    media_root = ensure_media_root()
    base_dir = media_root / "Preinscrits" / (prog.code or "UNK") / str(pre.id)
    
    if settings.DEBUG:
        print(f"📁 [DEBUG] Dossier média: {base_dir}")

    # Photo (validation + save)
    if photo_profil and getattr(photo_profil, "filename", ""):
        if settings.DEBUG:
            print(f"📸 [DEBUG] Traitement photo: {photo_profil.filename}")
        validate_upload(
            photo_profil,
            allowed_mime_types=settings.ALLOWED_IMAGE_MIME_TYPES,
            max_mb=settings.MAX_UPLOAD_SIZE_MB,
            field_name="photo_profil",
        )
        ext = os.path.splitext(photo_profil.filename)[1].lower() or ".jpg"
        photo_path = base_dir / f"photo_profil_{pre.id}{ext}"
        save_upload(photo_path, photo_profil)
        cand.photo_profil = str(photo_path)
        if settings.DEBUG:
            print(f"💾 [DEBUG] Photo sauvegardée: {photo_path}")

    # Documents dynamiques
    form = await request.form()
    indices: Set[str] = set()
    for k in form.keys():
        if k.startswith("doc_type_"):
            indices.add(k.split("_")[-1])
    
    if settings.DEBUG:
        print(f"📄 [DEBUG] Documents trouvés: {len(indices)} document(s)")

    for idx in indices:
        doc_type_val = form.get(f"doc_type_{idx}")
        title = form.get(f"doc_title_{idx}")
        file = form.get(f"doc_file_{idx}")  # UploadFile

        if not file or not getattr(file, "filename", ""):
            if settings.DEBUG:
                print(f"⚠️ [DEBUG] Document {idx} ignoré: fichier manquant")
            continue

        if settings.DEBUG:
            print(f"📄 [DEBUG] Traitement document {idx}: {doc_type_val} - {title} - {file.filename}")
        
        validate_upload(
            file,
            allowed_mime_types=settings.ALLOWED_DOC_MIME_TYPES,
            max_mb=settings.MAX_UPLOAD_SIZE_MB,
            field_name=f"doc_file_{idx}",
        )

        doc_type_for_db = coerce_doc_type(doc_type_val)

        doc = Document(
            candidat_id=cand.id,
            type_document=doc_type_for_db,
            titre=title,
            nom_fichier=file.filename,
            chemin_fichier="",
            mimetype=getattr(file, "content_type", None),
            taille_octets=None,
            depose_par_id=None,
        )
        session.add(doc)
        session.flush()

        ext = os.path.splitext(file.filename)[1].lower() or ""
        safe_title = safe_name(title or os.path.splitext(file.filename)[0])
        final_path = base_dir / f"{safe_title}_{doc.id}{ext}"
        save_upload(final_path, file)  # type: ignore[arg-type]

        doc.chemin_fichier = str(final_path)
        try:
            doc.taille_octets = final_path.stat().st_size
        except Exception:
            pass

    anciennete = entreprise_age_annees(ent.date_creation)
    verdict, details = evaluate_eligibilite(
        adresse_perso=adresse_personnelle,
        adresse_entreprise=adresse_entreprise,
        chiffre_affaires=ca_float,
        anciennete_annees=anciennete,
        ca_min=prog.ca_seuil_min,
        ca_max=prog.ca_seuil_max,
        anciennete_min_annees=prog.anciennete_min_annees,
    )
    el = Eligibilite(
        preinscription_id=pre.id,
        ca_seuil_ok=details.get("ca_ok"),
        ca_score=ca_float,
        qpv_ok=details.get("qpv_ok"),
        anciennete_ok=details.get("anciennete_ok"),
        anciennete_annees=details.get("anciennete_annees"),
        verdict=verdict,
    )
    session.add(el)
    session.commit()

    if settings.DEBUG:
        print(f"✅ [DEBUG] Préinscription terminée avec succès!")
        print(f"🎯 [DEBUG] Redirection vers: /ACD/preinscriptions/merci")

    return RedirectResponse(url="/ACD/preinscriptions/merci", status_code=303)

# --------- PAGE MERCI ---------
@router.get("/preinscriptions/merci", response_class=HTMLResponse)
def preinscription_merci(request: Request):
    return templates.TemplateResponse(
        "ACD/preinscription_merci.html",
        {"request": request, "settings": settings},
    )


# --------- ENVOI D’INVITATION PAR MAIL ---------
@router.post("/preinscriptions/send-link")
def send_preinscription_link(
    background: BackgroundTasks,
    email: str = Form(...),
    programme_code: str = Form(...),
    message: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_session),
):
    prog = session.exec(select(Programme).where(Programme.code == programme_code)).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    token = uuid.uuid4().hex
    inv = PreinscriptionInvite(token=token, email=email, programme_id=prog.id, message=message)
    session.add(inv)
    session.commit()

    # Lien public
    base_url = str(request.base_url).rstrip("/")
    link = f"{base_url}/preinscriptions/form/{token}"

    subject = f"Préinscription {prog.code} — LIA Coaching"
    html = f"""
      <p>Bonjour,</p>
      <p>Vous pouvez compléter votre préinscription au programme <b>{prog.nom}</b> en cliquant sur le lien ci-dessous :</p>
      <p><a href="{link}">{link}</a></p>
      {"<p>Message : " + message + "</p>" if message else ""}
      <p>Bien cordialement,</p>
      <p>L’équipe LIA Coaching</p>
    """
    background.add_task(SmtpMailer().send, EmailMessage(to=[email], subject=subject, html=html))
    return {"ok": True}


# --------- FORMULAIRE PUBLIC (lien token) ---------
@router.get("/preinscriptions/form/{token}", response_class=HTMLResponse)
def preinscription_public_form_token(token: str, request: Request, session: Session = Depends(get_session)):
    inv = session.exec(select(PreinscriptionInvite).where(PreinscriptionInvite.token == token)).first()
    
            # Debug logs pour comprendre l'expiration
    if settings.DEBUG and inv:
        now = datetime.now(timezone.utc)
        print(f"🔍 [DEBUG] Vérification token: {token}")
        print(f"📅 [DEBUG] Date de création: {inv.cree_le}")
        print(f"⏰ [DEBUG] Date d'expiration: {inv.expire_le}")
        print(f"🕐 [DEBUG] Date actuelle (UTC): {now}")
        print(f"⏳ [DEBUG] Temps restant: {inv.expire_le - now}")
        print(f"❌ [DEBUG] Token expiré: {inv.expire_le < now}")
        print(f"✅ [DEBUG] Token utilisé: {inv.utilise}")
    
    if not inv or inv.utilise or inv.expire_le < datetime.now(timezone.utc):
        if settings.DEBUG:
            print(f"🚫 [DEBUG] Token rejeté - inv: {bool(inv)}, utilisé: {inv.utilise if inv else 'N/A'}, expiré: {inv.expire_le < datetime.now(timezone.utc) if inv else 'N/A'}")
        return templates.TemplateResponse(
            "preinscription_public_form.html",
            {"request": request, "settings": settings, "error": "Lien invalide ou expiré."},
            status_code=400,
        )
    prog = session.get(Programme, inv.programme_id)
    return templates.TemplateResponse(
        "ACD/preinscription_public_form.html",
        {
            "request": request,
            "settings": settings,
            "invite": inv,
            "programme": prog,
            "doc_types": DOC_TYPES_DEFAULT,
        },
    )


# --------- FORMULAIRE PUBLIC (sans token) ---------
@router.get("/preinscriptions/public_form", response_class=HTMLResponse)
def preinscription_public_form(
    request: Request,
    programme: Optional[str] = None,
    email: Optional[str] = None,
    session: Session = Depends(get_session),
):
    # Récupérer tous les programmes actifs pour la liste déroulante
    programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
    
    prog = None
    if programme:
        prog = session.exec(select(Programme).where(Programme.code == programme)).first()
    
    return templates.TemplateResponse(
        "ACD/preinscription_public_form.html",
        {
            "request": request,
            "settings": settings,
            "programme": prog,
            "prefill_email": email,
            "doc_types": DOC_TYPES_DEFAULT,
            "programmes_actifs": programmes_actifs,  # Nouveau : tous les programmes actifs
        },
    )


# --------- SOUMISSION (token) AVEC UPLOAD PHOTO + DOCS ---------
@router.post("/preinscriptions/form/{token}")
async def preinscription_public_submit_token(
    token: str,
    request: Request,
    # champs formulaire
    civilite: Optional[str] = Form(None),
    nom: str = Form(...),
    prenom: str = Form(...),
    date_naissance: str = Form(...),  # 'YYYY-MM-DD'
    email: str = Form(...),
    telephone: Optional[str] = Form(None),
    adresse_personnelle: str = Form(...),
    adresse_entreprise: Optional[str] = Form(None),
    date_creation_entreprise: Optional[str] = Form(None),
    chiffre_affaire: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    niveau_etudes: Optional[str] = Form(None),
    secteur_activite: Optional[str] = Form(None),
    # fichiers
    photo_profil: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    inv = session.exec(select(PreinscriptionInvite).where(PreinscriptionInvite.token == token)).first()
    
            # Debug logs pour comprendre l'expiration
    if settings.DEBUG and inv:
        now = datetime.now(timezone.utc)
        print(f"🔍 [DEBUG] Vérification token (POST): {token}")
        print(f"📅 [DEBUG] Date de création: {inv.cree_le}")
        print(f"⏰ [DEBUG] Date d'expiration: {inv.expire_le}")
        print(f"🕐 [DEBUG] Date actuelle (UTC): {now}")
        print(f"⏳ [DEBUG] Temps restant: {inv.expire_le - now}")
        print(f"❌ [DEBUG] Token expiré: {inv.expire_le < now}")
        print(f"✅ [DEBUG] Token utilisé: {inv.utilise}")
    
    if not inv or inv.utilise or inv.expire_le < datetime.now(timezone.utc):
        if settings.DEBUG:
            print(f"🚫 [DEBUG] Token rejeté (POST) - inv: {bool(inv)}, utilisé: {inv.utilise if inv else 'N/A'}, expiré: {inv.expire_le < datetime.now(timezone.utc) if inv else 'N/A'}")
        raise HTTPException(status_code=400, detail="Lien invalide ou expiré.")
    prog = session.get(Programme, inv.programme_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable.")

    # Parse dates & CA
    dn = _date.fromisoformat(date_naissance)
    dce = _date.fromisoformat(date_creation_entreprise) if date_creation_entreprise else None
    try:
        ca_float = float(str(chiffre_affaire).replace(" ", "").replace(",", "."))
    except Exception:
        ca_float = None

    # Upsert Candidat
    cand = session.exec(select(Candidat).where(Candidat.email == email)).first()
    if not cand:
        cand = Candidat(email=email, nom=nom, prenom=prenom)
        session.add(cand)
        session.flush()
    
    # Vérifier si le candidat est déjà inscrit à ce programme
    existing_inscription = session.exec(
        select(Inscription).where(
            (Inscription.candidat_id == cand.id) & 
            (Inscription.programme_id == prog.id)
        )
    ).first()
    
    if existing_inscription:
        if settings.DEBUG:
            print(f"⚠️ [DEBUG] Candidat déjà inscrit au programme {prog.code} (via token)")
        raise HTTPException(status_code=400, detail=f"Vous êtes déjà inscrit au programme '{prog.code} - {prog.nom}'. Vous ne pouvez vous inscrire qu'une seule fois par programme.")
    
    # Vérifier si le candidat est déjà préinscrit à ce programme
    existing_pre = session.exec(
        select(Preinscription).where(
            (Preinscription.candidat_id == cand.id) & 
            (Preinscription.programme_id == prog.id)
        )
    ).first()
    
    if existing_pre:
        if settings.DEBUG:
            print(f"⚠️ [DEBUG] Candidat déjà préinscrit au programme {prog.code} (via token)")
        raise HTTPException(status_code=400, detail=f"Vous êtes déjà préinscrit au programme '{prog.code} - {prog.nom}'. Vous ne pouvez vous préinscrire qu'une seule fois par programme.")
    
    cand.civilite = civilite
    cand.date_naissance = dn
    cand.telephone = telephone
    cand.adresse_personnelle = adresse_personnelle
    cand.niveau_etudes = niveau_etudes
    cand.secteur_activite = secteur_activite

    # Entreprise
    ent = session.exec(select(Entreprise).where(Entreprise.candidat_id == cand.id)).first()
    if not ent:
        ent = Entreprise(candidat_id=cand.id)
        session.add(ent)
        session.flush()
    ent.adresse = adresse_entreprise
    ent.date_creation = dce
    ent.siret = siret
    ent.chiffre_affaires = ca_float

    # Géocodage (adresse entreprise prioritaire, sinon perso)
    addr_for_geo = adresse_entreprise or adresse_personnelle
    if addr_for_geo:
        latlng = await geocode_one(addr_for_geo)
        if latlng:
            ent.lat, ent.lng = latlng

    # Crée la Préinscription
    pre = Preinscription(programme_id=prog.id, candidat_id=cand.id, source="formulaire")
    session.add(pre)
    session.flush()  # pour avoir pre.id

    # Dossier de stockage
    media_root = ensure_media_root()
    base_dir = media_root / "Preinscrits" / (prog.code or "UNK") / str(pre.id)

    # 1) Photo de profil (validation + save)
    if photo_profil and getattr(photo_profil, "filename", ""):
        validate_upload(
            photo_profil,
            allowed_mime_types=settings.ALLOWED_IMAGE_MIME_TYPES,
            max_mb=settings.MAX_UPLOAD_SIZE_MB,
            field_name="photo_profil",
        )
        ext = os.path.splitext(photo_profil.filename)[1].lower() or ".jpg"
        photo_path = base_dir / f"photo_profil_{pre.id}{ext}"
        save_upload(photo_path, photo_profil)
        cand.photo_profil = str(photo_path)

    # 2) Documents multiples dynamiques
    form = await request.form()
    indices: Set[str] = set()
    for k in form.keys():
        if k.startswith("doc_type_"):
            indices.add(k.split("_")[-1])

    for idx in indices:
        doc_type_val = form.get(f"doc_type_{idx}")
        title = form.get(f"doc_title_{idx}")
        file = form.get(f"doc_file_{idx}")  # UploadFile depuis FormData

        if not file or not getattr(file, "filename", ""):
            continue

        # validation fichier
        validate_upload(
            file,
            allowed_mime_types=settings.ALLOWED_DOC_MIME_TYPES,
            max_mb=settings.MAX_UPLOAD_SIZE_MB,
            field_name=f"doc_file_{idx}",
        )

        doc_type_for_db = coerce_doc_type(doc_type_val)

        # Création en DB
        doc = Document(
            candidat_id=cand.id,
            type_document=doc_type_for_db,  # enum ou texte libre
            titre=title,
            nom_fichier=file.filename,
            chemin_fichier="",  # MAJ après écriture
            mimetype=getattr(file, "content_type", None),
            taille_octets=None,
            depose_par_id=None,  # public
        )
        session.add(doc)
        session.flush()  # doc.id

        ext = os.path.splitext(file.filename)[1].lower() or ""
        safe_title = safe_name(title or os.path.splitext(file.filename)[0])
        final_path = base_dir / f"{safe_title}_{doc.id}{ext}"
        save_upload(final_path, file)  # type: ignore[arg-type]

        # MAJ chemin & taille
        doc.chemin_fichier = str(final_path)
        try:
            doc.taille_octets = final_path.stat().st_size
        except Exception:
            pass

    # Éligibilité
    anciennete = entreprise_age_annees(ent.date_creation)
    verdict, details = evaluate_eligibilite(
        adresse_perso=adresse_personnelle,
        adresse_entreprise=adresse_entreprise,
        chiffre_affaires=ca_float,
        anciennete_annees=anciennete,
        ca_min=prog.ca_seuil_min,
        ca_max=prog.ca_seuil_max,
        anciennete_min_annees=prog.anciennete_min_annees,
    )
    el = Eligibilite(
        preinscription_id=pre.id,
        ca_seuil_ok=details.get("ca_ok"),
        ca_score=ca_float,
        qpv_ok=details.get("qpv_ok"),
        anciennete_ok=details.get("anciennete_ok"),
        anciennete_annees=details.get("anciennete_annees"),
        verdict=verdict,
        details_json=None,  # json.dumps(details) si tu veux conserver le détail
    )
    session.add(el)

    # Marque l’invitation comme utilisée
    inv.utilise = True
    session.commit()

    return RedirectResponse(url="/preinscriptions/merci", status_code=303)


