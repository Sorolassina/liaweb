# app/routers/preinscriptions.py
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone, date as _date
from pathlib import Path
from typing import Optional, Set

from fastapi import (
    APIRouter, Request, Depends, Form, HTTPException,
    Query, UploadFile, File
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app_lia_web.core.database import get_session
from app_lia_web.core.middleware import get_shared_session
from app_lia_web.core.program_schema_integration import table_exists_anywhere
from app_lia_web.core.config import settings
from app_lia_web.core.program_schema_integration import get_schema_routing_service
from app_lia_web.core.path_config import path_config
from app_lia_web.app.services.file_upload_service import FileUploadService
from app_lia_web.core.security import get_current_user
from app_lia_web.app.templates import templates

from app_lia_web.app.models.base import (
    Programme, Candidat, Entreprise,
    StatutDossier, Document
)
from app_lia_web.app.models.preinscription import Preinscription, Eligibilite
from app_lia_web.app.models.inscription import Inscription

# Enums
try:
    from app_lia_web.app.models.enums import TypeDocument  # recommandé
except Exception:
    try:
        from app_lia_web.app.models.base import TypeDocument  # fallback si défini là
    except Exception:
        TypeDocument = None  # pas d'enum dispo

from app_lia_web.app.services.geocoding import geocode_one
from app_lia_web.app.services.eligibilite import evaluate_eligibilite, entreprise_age_annees
from app_lia_web.app.services.uploads import validate_upload  # limites taille/type

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
    """Récupère le MEDIA_ROOT (config) et s'assure qu'il existe."""
    from app_lia_web.core.config import Settings
    settings = Settings()
    root = settings.MEDIA_ROOT
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

# --------- FORMULAIRE PUBLIC (pour les candidats) ---------
@router.get("/public-form", name="preinscriptions_public_form", response_class=HTMLResponse)
def preinscription_public_form(
    request: Request,
    session: Session = Depends(get_shared_session),
    programme: Optional[str] = Query(None),
):
    # Récupérer le programme spécifique si fourni
    prog = None
    if programme:
        prog = session.exec(select(Programme).where(Programme.code == programme)).first()
    
    # Récupérer tous les programmes actifs pour la liste déroulante
    programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
    
    return templates.TemplateResponse(
        "programme/preinscription_public_form.html",
        {
            "request": request,
            "settings": settings,
            "programme": prog,
            "programmes_actifs": programmes_actifs,
            "doc_types": DOC_TYPES_DEFAULT,
        },
    )

# --------- LISTE ADMIN (pour les administrateurs) ---------
@router.get("/form", name="preinscriptions_form", response_class=HTMLResponse)
def preinscriptions(
    request: Request,
    session: Session = Depends(get_shared_session),
    programme: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    q: Optional[str] = Query(None),
    schema_routing_service = Depends(get_schema_routing_service),
):
    # Programmes pour filtre
    progs = session.exec(select(Programme).where(Programme.actif.is_(True))).all()

    # Configurer le schéma pour les requêtes de préinscriptions
    programme_code = programme or "ACD"
    schema_routing_service.set_schema(programme_code.lower())
    
    # Vérifier l'existence des tables avant d'exécuter les requêtes
    if not table_exists_anywhere("preinscription", session):
        return templates.TemplateResponse("programme/preinscriptions_list.html", {
            "request": request,
            "utilisateur": current_user,
            "programmes": progs,
            "preinscriptions": [],
            "total": 0,
            "total_programme": 0,
            "programme_selectionne": programme,
            "q": q,
            "settings": settings,
            "pins": []
        })
    
    # Construire la requête SQL pour récupérer les préinscriptions avec les jointures
    sql_query = """
        SELECT p.*, c.*, prog.*, e.*
        FROM preinscription p
        JOIN candidats c ON c.id = p.candidat_id
        JOIN programmes prog ON prog.id = p.programme_id
        LEFT JOIN entreprises e ON e.candidat_id = c.id
    """
    
    params = {}
    conditions = []
    
    if programme:
        conditions.append("prog.code = :programme_code")
        params["programme_code"] = programme
    
    if q:
        conditions.append("(c.nom ILIKE :q OR c.prenom ILIKE :q OR c.email ILIKE :q)")
        params["q"] = f"%{q}%"
    
    if conditions:
        sql_query += " WHERE " + " AND ".join(conditions)
    
    sql_query += " ORDER BY p.cree_le DESC LIMIT 300"
    
    # Exécuter la requête
    try:
        result = schema_routing_service.execute_in_schema(sql_query, params)
        rows = result.fetchall()
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des préinscriptions: {e}")
        rows = []

    # KPI pour en-tête - compter toutes les préinscriptions dans le schéma
    try:
        total_result = schema_routing_service.execute_in_schema("SELECT COUNT(*) FROM preinscription")
        total = total_result.fetchone()[0] or 0
    except Exception as e:
        logging.warning(f"Erreur lors du comptage total des préinscriptions: {e}")
        total = 0
    
    # Calculer le total pour le programme sélectionné
    try:
        total_programme_result = schema_routing_service.execute_in_schema(
            "SELECT COUNT(*) FROM preinscription p JOIN programmes prog ON prog.id = p.programme_id WHERE prog.code = :programme_code",
            {"programme_code": programme_code}
        )
        total_programme = total_programme_result.fetchone()[0] or 0
    except Exception as e:
        logging.warning(f"Erreur lors du comptage des préinscriptions du programme: {e}")
        total_programme = 0

    # Pins pour carte (lat/lng depuis Entreprise si existant)
    pins = []
    for row in rows:
        try:
            # Accéder aux colonnes par nom (SQLAlchemy Row)
            nom = getattr(row, 'nom', '') or ''
            prenom = getattr(row, 'prenom', '') or ''
            programme_code = getattr(row, 'code', '') or ''
            lat = getattr(row, 'lat', None)
            lng = getattr(row, 'lng', None)
            qpv = getattr(row, 'qpv', False)
            adresse = getattr(row, 'adresse', '') or ''
            
            # Vérifier que lat et lng sont des nombres valides
            if lat is not None and lng is not None:
                try:
                    lat_float = float(lat)
                    lng_float = float(lng)
                    pins.append({
                        "nom": str(nom),
                        "prenom": str(prenom),
                        "programme": str(programme_code),
                        "lat": lat_float,
                        "lng": lng_float,
                        "qpv": bool(qpv),
                        "adresse": str(adresse),
                    })
                except (ValueError, TypeError) as e:
                    logging.warning(f"Valeurs lat/lng invalides: lat={lat}, lng={lng}, erreur: {e}")
                    continue
        except Exception as e:
            logging.warning(f"Erreur lors de la création d'un pin: {e}")
            continue

    # Debug: vérifier le contenu de pins avant sérialisation
    logging.info(f"Pins créés: {len(pins)} éléments")
    for i, pin in enumerate(pins):
        logging.info(f"Pin {i}: {pin}")

    return templates.TemplateResponse(
        "programme/preinscriptions_list.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "rows": rows,
            "progs": progs,
            "current_programme": programme,
            "q": q or "",
            "kpi": {"total": int(total), "programme": int(total_programme), "programme_code": programme_code},
            "pins": pins,
        },
    )

# --------- SOUMISSION PUBLIQUE (sans token) AVEC UPLOAD PHOTO + DOCS ---------
@router.post("/submit", name="preinscription_public_submit")
async def preinscription_public_submit(
    request: Request,
    programme_code: str = Form(...),
    schema_routing_service = Depends(get_schema_routing_service),
    civilite: str= Form(None),
    nom: str = Form(...),
    prenom: str = Form(...),
    date_naissance: str = Form(...),
    email: str = Form(...),
    telephone: str= Form(None),
    # Champs d'adresse personnelle décomposés
    numero_personnel: str= Form(None),
    rue_personnel: str = Form(None),
    code_postal_personnel: str= Form(None),
    ville_personnel: str = Form(None),
    adresse_personnelle: Optional[str] = Form(None),  # Champ consolidé
    
    # Champs d'adresse entreprise décomposés
    numero_entreprise: Optional[str] = Form(None),
    rue_entreprise: Optional[str] = Form(None),
    code_postal_entreprise: Optional[str] = Form(None),
    ville_entreprise: Optional[str] = Form(None),
    adresse_entreprise: Optional[str] = Form(None),  # Champ consolidé
    date_creation_entreprise: Optional[str] = Form(None),
    chiffre_affaire: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    niveau_etudes: Optional[str] = Form(None),
    secteur_activite: Optional[str] = Form(None),
    photo_profil: UploadFile | None = File(None),
    session: Session = Depends(get_shared_session),
):
    # Logs de surveillance si debug activé
    if settings.DEBUG:
        print(f"🔍 [DEBUG] Route /preinscriptions/submit appelée")
        print(f"📝 [DEBUG] Données reçues:")
        print(f"   - programme_code: {programme_code}")
        print(f"   - nom: {nom}")
        print(f"   - prenom: {prenom}")
        print(f"   - email: {email}")
        print(f"   - telephone: {telephone}")
        print(f"   - adresse_personnelle: {adresse_personnelle}")
        print(f"   - adresse_entreprise: {adresse_entreprise}")
        print(f"   - photo_profil: {photo_profil.filename if photo_profil else 'Aucune'}")
    
    prog = session.exec(select(Programme).where(Programme.code == programme_code)).first()
    if not prog:
        if settings.DEBUG:
            print(f"❌ [DEBUG] Programme '{programme_code}' introuvable")
        
        # Récupérer tous les programmes actifs pour la liste déroulante
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        
        # Retourner une page d'erreur claire au lieu d'une exception
        return templates.TemplateResponse(
            "programme/preinscription_public_form.html",
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

    # Le schéma est déjà configuré par le middleware selon l'URL
    # Ne pas le reconfigurer ici pour éviter les conflits
    if settings.DEBUG:
        print(f"🎯 [DEBUG] Utilisation du schéma configuré par le middleware")

    # Validation des adresses avec le schéma Pydantic
    from app_lia_web.app.schemas.preinscription_schemas import Adresse
    from pydantic import ValidationError
    
    # Validation adresse personnelle
    try:
        adresse_perso_obj = Adresse(
            address=adresse_personnelle,
            numero=numero_personnel,
            rue=rue_personnel,
            code_postal=code_postal_personnel,
            ville=ville_personnel,
            type_adresse="personnelle"
        )
        adresse_personnelle = adresse_perso_obj.address
        if settings.DEBUG:
            print(f"🏠 [DEBUG] Adresse personnelle validée et formatée: {adresse_personnelle}")
    except ValidationError as e:
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        return templates.TemplateResponse(
            "programme/preinscription_public_form.html",
            {
                "request": request,
                "settings": settings,
                "programme": prog,
                "error": f"Erreur de validation de l'adresse personnelle: {e.errors()[0]['msg']}",
                "doc_types": DOC_TYPES_DEFAULT,
                "programmes_actifs": programmes_actifs,
            },
            status_code=400
        )
    
    # Validation adresse entreprise (optionnelle)
    if any([numero_entreprise, rue_entreprise, code_postal_entreprise, ville_entreprise]):
        try:
            adresse_ent_obj = Adresse(
                address=adresse_entreprise,
                numero=numero_entreprise,
                rue=rue_entreprise,
                code_postal=code_postal_entreprise,
                ville=ville_entreprise,
                type_adresse="entreprise"
            )
            adresse_entreprise = adresse_ent_obj.address
            if settings.DEBUG:
                print(f"🏢 [DEBUG] Adresse entreprise validée et formatée: {adresse_entreprise}")
        except ValidationError as e:
            programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
            return templates.TemplateResponse(
                "programme/preinscription_public_form.html",
                {
                    "request": request,
                    "settings": settings,
                    "programme": prog,
                    "error": f"Erreur de validation de l'adresse entreprise: {e.errors()[0]['msg']}",
                    "doc_types": DOC_TYPES_DEFAULT,
                    "programmes_actifs": programmes_actifs,
                },
                status_code=400
            )

    dn = _date.fromisoformat(date_naissance)
    dce = _date.fromisoformat(date_creation_entreprise) if date_creation_entreprise else None
    # Le chiffre d'affaires est un intervalle (string), pas un nombre
    ca_string = str(chiffre_affaire).strip() if chiffre_affaire else None
    if settings.DEBUG:
        print(f"💰 [DEBUG] Chiffre d'affaires (intervalle): {ca_string}")

    cand = None
    if table_exists_anywhere("candidat", session):
        try:
            cand = session.exec(select(Candidat).where(Candidat.email == email)).first()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du candidat: {e}")
    
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
    existing_inscription_result = schema_routing_service.execute_in_schema(
        "SELECT * FROM inscription WHERE candidat_id = :candidat_id AND programme_id = :programme_id",
        {"candidat_id": cand.id, "programme_id": prog.id}
    )
    existing_inscription = existing_inscription_result.fetchone()
    
    if existing_inscription:
        if settings.DEBUG:
            print(f"⚠️ [DEBUG] Candidat déjà inscrit au programme {prog.code}")
        
        # Retourner une erreur claire
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        return templates.TemplateResponse(
            "programme/preinscription_public_form.html",
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
    existing_preinscription_result = schema_routing_service.execute_in_schema(
        "SELECT * FROM preinscription WHERE candidat_id = :candidat_id AND programme_id = :programme_id",
        {"candidat_id": cand.id, "programme_id": prog.id}
    )
    existing_preinscription = existing_preinscription_result.fetchone()
    
    if existing_preinscription:
        if settings.DEBUG:
            print(f"⚠️ [DEBUG] Candidat déjà préinscrit au programme {prog.code}")
        
        # Retourner une erreur claire
        programmes_actifs = session.exec(select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)).all()
        return templates.TemplateResponse(
            "programme/preinscription_public_form.html",
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
    cand.adresse_personnelle = adresse_personnelle  # Adresse consolidée
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
    
    ent.adresse = adresse_entreprise  # Adresse consolidée
    ent.date_creation = dce
    ent.siret = siret
    ent.chiffre_affaires = ca_string
    
    if settings.DEBUG:
        print(f"🏢 [DEBUG] Entreprise mise à jour - CA: {ent.chiffre_affaires}, SIRET: {ent.siret}")

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

    # Créer la préinscription dans le schéma du programme
    pre = Preinscription(programme_id=prog.id, candidat_id=cand.id, source="formulaire")
    
    # Utiliser le service de routage pour insérer dans le bon schéma
    schema_routing_service.execute_in_schema(
        "INSERT INTO preinscription (programme_id, candidat_id, source, statut, donnees_brutes_json, cree_le) VALUES (:programme_id, :candidat_id, :source, :statut, :donnees_brutes_json, :cree_le)",
        {
            "programme_id": prog.id,
            "candidat_id": cand.id,
            "source": "formulaire",
            "statut": "SOUMIS",
            "donnees_brutes_json": json.dumps({
                "nom": nom,
                "prenom": prenom,
                "email": email,
                "telephone": telephone,
                # Adresse personnelle (consolidée et décomposée)
                "adresse_personnelle": adresse_personnelle,
                "numero_personnel": adresse_perso_obj.numero,
                "rue_personnel": adresse_perso_obj.rue,
                "code_postal_personnel": adresse_perso_obj.code_postal,
                "ville_personnel": adresse_perso_obj.ville,
                # Adresse entreprise (consolidée et décomposée)
                "adresse_entreprise": adresse_entreprise,
                "numero_entreprise": adresse_ent_obj.numero if 'adresse_ent_obj' in locals() else numero_entreprise,
                "rue_entreprise": adresse_ent_obj.rue if 'adresse_ent_obj' in locals() else rue_entreprise,
                "code_postal_entreprise": adresse_ent_obj.code_postal if 'adresse_ent_obj' in locals() else code_postal_entreprise,
                "ville_entreprise": adresse_ent_obj.ville if 'adresse_ent_obj' in locals() else ville_entreprise,
                # Autres champs
                "date_creation_entreprise": date_creation_entreprise.isoformat() if date_creation_entreprise else None,
                "chiffre_affaires": chiffre_affaires,
                "siret": siret,
                "niveau_etudes": niveau_etudes,
                "secteur_activite": secteur_activite
            }),
            "cree_le": datetime.now(timezone.utc)
        }
    )
    
    # Récupérer l'ID de la préinscription créée
    result = schema_routing_service.execute_in_schema(
        "SELECT id FROM preinscription WHERE programme_id = :programme_id AND candidat_id = :candidat_id ORDER BY cree_le DESC LIMIT 1",
        {"programme_id": prog.id, "candidat_id": cand.id}
    )
    pre_id = result.fetchone()[0]
    
    if settings.DEBUG:
        print(f"📝 [DEBUG] Préinscription créée avec ID: {pre_id} dans le schéma {programme_code.lower()}")

    media_root = ensure_media_root()
    base_dir = media_root / "Preinscrits" / (prog.code or "UNK") / str(pre_id)
    
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
        unique_filename = f"photo_profil_{pre_id}{ext}"
        subfolder = f"Preinscrits/{prog.code or 'UNK'}/{pre_id}"
        
        # Utiliser FileUploadService pour sauvegarder le fichier
        file_info = await FileUploadService.save_file(
            photo_profil,
            "media",
            unique_filename,
            subfolder=subfolder
        )
        
        cand.photo_profil = file_info["relative_path"]
        if settings.DEBUG:
            print(f"💾 [DEBUG] Photo sauvegardée: {file_info['relative_path']}")

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
        unique_filename = f"{safe_title}_{doc.id}{ext}"
        subfolder = f"Preinscrits/{prog.code or 'UNK'}/{pre_id}"
        
        # Utiliser FileUploadService pour sauvegarder le fichier
        file_info = await FileUploadService.save_file(
            file,
            "media",
            unique_filename,
            subfolder=subfolder
        )
        
        doc.chemin_fichier = file_info["relative_path"]
        doc.taille_octets = file_info["size"]

    anciennete = entreprise_age_annees(ent.date_creation)
    verdict, details = evaluate_eligibilite(
        adresse_perso=adresse_personnelle,
        adresse_entreprise=adresse_entreprise,
        chiffre_affaires=ca_string,
        anciennete_annees=anciennete,
        ca_min=prog.ca_seuil_min,
        ca_max=prog.ca_seuil_max,
        anciennete_min_annees=prog.anciennete_min_annees,
    )
    # Créer l'éligibilité dans le schéma du programme
    schema_routing_service.execute_in_schema(
        """INSERT INTO eligibilites (preinscription_id, ca_seuil_ok, ca_score, qpv_ok, anciennete_ok, anciennete_annees, verdict, cree_le) 
           VALUES (:preinscription_id, :ca_seuil_ok, :ca_score, :qpv_ok, :anciennete_ok, :anciennete_annees, :verdict, :cree_le)""",
        {
            "preinscription_id": pre_id,
            "ca_seuil_ok": details.get("ca_ok"),
            "ca_score": None,  # Pas de valeur numérique unique pour les intervalles
            "qpv_ok": details.get("qpv_ok"),
            "anciennete_ok": details.get("anciennete_ok"),
            "anciennete_annees": details.get("anciennete_annees"),
            "verdict": verdict,
            "cree_le": datetime.now(timezone.utc)
        }
    )
    session.commit()

    # 🔍 RECHERCHE QPV AUTOMATIQUE après création de la préinscription
    try:
        from app_lia_web.app.services.service_qpv import verif_qpv
        from app_lia_web.app.schemas.preinscription_schemas import Adresse
        
        # Préparer les données pour la vérification QPV
        adresses_a_verifier = []
        
        # Adresse personnelle
        if adresse_personnelle:
            adresses_a_verifier.append({
                "address": adresse_personnelle,
                "type": "personnelle"
            })
        
        # Adresse entreprise
        if adresse_entreprise:
            adresses_a_verifier.append({
                "address": adresse_entreprise,
                "type": "entreprise"
            })
        
        # Lancer la vérification QPV pour chaque adresse
        qpv_found = False
        details_qpv = {"adresses_analysees": []}
        
        for adresse_data in adresses_a_verifier:
            try:
                adresse_obj = Adresse(**adresse_data)
                result_qpv = await verif_qpv(adresse_obj, request)
                
                if result_qpv.get("etat_qpv") == "QPV":
                    qpv_found = True
                
                details_qpv["adresses_analysees"].append({
                    "type": adresse_data["type"],
                    "adresse": adresse_data["address"],
                    "resultat": result_qpv
                })
                
            except Exception as e:
                print(f"⚠️ [QPV] Erreur lors de la vérification {adresse_data['type']}: {e}")
                details_qpv["adresses_analysees"].append({
                    "address": adresse_data["address"],
                    "type": adresse_data["type"],
                    "etat_qpv": "ERREUR",
                    "erreur": str(e)
                })
        
        # Mettre à jour l'éligibilité avec les résultats QPV
        schema_routing_service.execute_in_schema(
            "UPDATE eligibilite SET qpv_ok = :qpv_ok, details_json = :details_json WHERE preinscription_id = :preinscription_id",
            {
                "qpv_ok": qpv_found,
                "details_json": json.dumps(details_qpv),
                "preinscription_id": pre_id
            }
        )
        session.commit()
        
        print(f"✅ [QPV] Recherche automatique terminée - QPV trouvé: {qpv_found}")
        
    except Exception as e:
        print(f"⚠️ [QPV] Erreur lors de la recherche automatique QPV: {e}")
        # Ne pas faire échouer la préinscription si QPV échoue

    if settings.DEBUG:
        print(f"✅ [DEBUG] Préinscription terminée avec succès!")
        print(f"🎯 [DEBUG] Redirection vers: /preinscriptions/merci")

    return RedirectResponse(url=request.url_for("preinscriptions_merci"), status_code=303)

# --------- PAGE MERCI ---------
@router.get("/merci", name="preinscriptions_merci", response_class=HTMLResponse)
def preinscription_merci(request: Request):
    return templates.TemplateResponse(
        "programme/preinscription_merci.html",
        {"request": request, "settings": settings},
    )