# app/routers/inscriptions.py
from __future__ import annotations

import os
from datetime import date as _date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from sqlalchemy import func

from ...core.database import get_session
from ...core.config import settings
from ...core.security import get_current_user
from ...templates import templates

from ...models.base import (
    Programme, Candidat, Entreprise, Preinscription, Eligibilite,
    Inscription, EtapePipeline, AvancementEtape, StatutEtape,
    DecisionJuryTable, Jury, DecisionJuryCandidat, Partenaire, User, Promotion,
    ReorientationCandidat
)
from ...models.enums import TypeDocument, DecisionJury, UserRole
from ...services.ACD.eligibilite import evaluate_eligibilite, entreprise_age_annees
from ...services.ACD.service_qpv import verif_qpv
from ...services.ACD.service_siret_pappers import get_entreprise_process
from ...schemas.ACD.schema_qpv import Adresse
from ...schemas.ACD.schema_siret import SiretRequest

router = APIRouter()

def _prog_by_code(session: Session, code: str) -> Programme | None:
    return session.exec(select(Programme).where(Programme.code == code)).first()

@router.get("/inscriptions/form", response_class=HTMLResponse)
def inscriptions_ui(
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
    programme: str = Query("ACD"),
    q: Optional[str] = Query(None),
    pre_id: Optional[int] = Query(None),
):
    prog = _prog_by_code(session, programme)
    if not prog:
        # Au lieu de lever une erreur, créer un programme factice avec des valeurs vides
        class ProgrammeFactice:
            def __init__(self):
                self.id = None
                self.code = programme
                self.nom = f"Programme {programme} (non trouvé)"
        
        prog = ProgrammeFactice()

    # Liste de préinscriptions (colonnes pour la liste gauche)
    pre_rows = []
    if prog.id:
        stmt = (
            select(Preinscription, Candidat, Entreprise, Eligibilite)
            .join(Candidat, Candidat.id==Preinscription.candidat_id)
            .join(Entreprise, Entreprise.candidat_id==Candidat.id, isouter=True)
            .join(Eligibilite, Eligibilite.preinscription_id==Preinscription.id, isouter=True)
            .where(Preinscription.programme_id==prog.id)
        )
        if q:
            like = f"%{q}%"
            stmt = stmt.where((Candidat.nom.ilike(like)) | (Candidat.prenom.ilike(like)) | (Candidat.email.ilike(like)))
        pre_rows = session.exec(stmt.order_by(Preinscription.cree_le.desc()).limit(400)).all()
        
        # Debug logs
        if settings.DEBUG:
            print(f"🔍 [DEBUG] Programme ID: {prog.id}")
            print(f"📊 [DEBUG] Nombre de préinscriptions trouvées: {len(pre_rows)}")
            for i, row in enumerate(pre_rows[:3]):  # Afficher les 3 premières
                p, c, e, elig = row
                print(f"   {i+1}. Préinscription ID: {p.id}, Candidat: {c.nom} {c.prenom}")
                print(f"      📸 Photo profil: {repr(c.photo_profil)}")
                if c.photo_profil:
                    print(f"      🔗 URL générée: /media/{c.photo_profil}")

    selected = None; cand=None; ent=None; elig=None; inscription=None; pipeline=[]
    if pre_id:
        if settings.DEBUG:
            print(f"🎯 [DEBUG] Recherche de préinscription ID: {pre_id}")
        for row in pre_rows:
            if row[0].id == pre_id:
                selected, cand, ent, elig = row
                if settings.DEBUG:
                    print(f"✅ [DEBUG] Préinscription trouvée: {selected.id}, Candidat: {cand.nom} {cand.prenom}")
                break
        
        if not selected and settings.DEBUG:
            print(f"❌ [DEBUG] Préinscription ID {pre_id} non trouvée dans la liste")
            print(f"📋 [DEBUG] IDs disponibles: {[row[0].id for row in pre_rows]}")
        
        if selected:
            inscription = session.exec(
                select(Inscription).where(
                    (Inscription.programme_id==prog.id) & (Inscription.candidat_id==cand.id)
                )
            ).first()
            if inscription:
                # Pipeline (avancement attaché)
                av = session.exec(
                    select(AvancementEtape).where(AvancementEtape.inscription_id==inscription.id)
                    .join(EtapePipeline).order_by(EtapePipeline.ordre)
                ).all()
                pipeline = [{"id": a.id, "statut": a.statut, "etape": a.etape, "debut": a.debut_le, "fin": a.termine_le} for a in av]

    # KPI simples
    total_pre = 0
    total_insc = 0
    taux_conv = 0.0
    objectif_qpv_atteint = 0.0
    
    if prog.id:
        total_pre = session.exec(select(func.count(Preinscription.id)).where(Preinscription.programme_id==prog.id)).one() or 0
        total_insc = session.exec(select(func.count(Inscription.id)).where(Inscription.programme_id==prog.id)).one() or 0
        taux_conv = round((total_insc / total_pre * 100), 1) if total_pre else 0.0

        # Objectif QPV (ex: % de préinscrits ayant qpv_ok)
        qpv_ok_count = session.exec(
            select(func.count(Eligibilite.id)).join(Preinscription).where(
                (Preinscription.programme_id==prog.id) & (Eligibilite.qpv_ok.is_(True))
            )
        ).one() or 0
        objectif_qpv_atteint = round((qpv_ok_count / total_pre * 100), 1) if total_pre else 0.0

    # Jury sessions futures + récentes
    jurys = []
    if prog.id:
        jurys = session.exec(select(Jury).where(Jury.programme_id==prog.id).order_by(Jury.session_le.desc())).all()

    # Données pour le système de décisions du jury
    decisions_jury = []
    conseillers = []
    promotions = []
    partenaires = []
    
    if cand:
        # Récupérer les décisions du jury pour ce candidat
        decisions_jury = session.exec(
            select(DecisionJuryCandidat, Jury, User, Promotion, Partenaire)
            .join(Jury, Jury.id == DecisionJuryCandidat.jury_id)
            .outerjoin(User, User.id == DecisionJuryCandidat.conseiller_id)
            .outerjoin(Promotion, Promotion.id == DecisionJuryCandidat.promotion_id)
            .outerjoin(Partenaire, Partenaire.id == DecisionJuryCandidat.partenaire_id)
            .where(DecisionJuryCandidat.candidat_id == cand.id)
            .order_by(DecisionJuryCandidat.date_decision.desc())
        ).all()
    
    # Récupérer les conseillers
    conseillers = session.exec(select(User).where(User.role == UserRole.CONSEILLER.value)).all()
    
    # Récupérer les promotions
    promotions = session.exec(select(Promotion)).all()
    
    # Récupérer les partenaires actifs
    partenaires = session.exec(select(Partenaire).where(Partenaire.actif == True)).all()

    # Extraire le nom du QPV si disponible
    qpv_name = None
    if elig and elig.details_json:
        try:
            import json
            qpv_details = json.loads(elig.details_json)
            if qpv_details.get("adresses_analysees"):
                for analyse in qpv_details["adresses_analysees"]:
                    if analyse.get("resultat") and analyse["resultat"].get("nom_qp"):
                        nom_qp = analyse["resultat"]["nom_qp"]
                        if "QPV:" in nom_qp or "QPV limit:" in nom_qp:
                            qpv_name =nom_qp # nom_qp.split(":")[1] if ":" in nom_qp else nom_qp
                            break
        except (json.JSONDecodeError, KeyError, IndexError):
            qpv_name = None

    return templates.TemplateResponse(
        "ACD/inscription.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "current_programme": programme,
            "q": q or "",
            "pre_rows": pre_rows,
            "selected": selected,
            "programme": prog,
            "cand": cand,
            "ent": ent,
            "elig": elig,
            "inscription": inscription,
            "pipeline": pipeline,
            "jurys": jurys,
            "decisions_jury": decisions_jury,
            "conseillers": conseillers,
            "promotions": promotions,
            "partenaires": partenaires,
            "qpv_name": qpv_name,
            "type_documents": TypeDocument,
            "kpi": {
                "total_pre": int(total_pre),
                "total_insc": int(total_insc),
                "taux_conv": taux_conv,
                "objectif_qpv_atteint": objectif_qpv_atteint,
            },
            "timestamp": int(datetime.now().timestamp()),
        }
    )


# Crée une inscription à partir d'une préinscription
@router.post("/inscriptions/create-from-pre")
def create_from_pre(
    pre_id: int = Form(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    pre = session.get(Preinscription, pre_id)
    if not pre:
        raise HTTPException(status_code=404, detail="Préinscription introuvable")
    prog = session.get(Programme, pre.programme_id)
    if not prog:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    exists = session.exec(
        select(Inscription).where(
            (Inscription.programme_id==pre.programme_id) & (Inscription.candidat_id==pre.candidat_id)
        )
    ).first()
    if exists:
        return RedirectResponse(url=f"ACD/inscriptions/form?programme={prog.code}&pre_id={pre.id}", status_code=303)

    ins = Inscription(programme_id=pre.programme_id, candidat_id=pre.candidat_id, statut=pre.statut)
    session.add(ins); session.flush()

    # Instancie le pipeline pour ce programme
    steps = session.exec(
        select(EtapePipeline).where(
            (EtapePipeline.programme_id==prog.id) & (EtapePipeline.active.is_(True))
        ).order_by(EtapePipeline.ordre)
    ).all()
    for st in steps:
        av = AvancementEtape(inscription_id=ins.id, etape_id=st.id, statut=StatutEtape.A_FAIRE)
        session.add(av)

    session.commit()
    return RedirectResponse(url=f"ACD/inscriptions/form?programme={prog.code}&pre_id={pre.id}", status_code=303)


# Mise à jour infos candidat/entreprise
@router.post("/inscriptions/update-infos")
def update_infos(
    pre_id: int = Form(...),
    # Informations personnelles
    civilite: Optional[str] = Form(None),
    date_naissance: Optional[str] = Form(None),
    telephone: Optional[str] = Form(None),
    adresse_personnelle: Optional[str] = Form(None),
    niveau_etudes: Optional[str] = Form(None),
    secteur_activite: Optional[str] = Form(None),
    handicap: Optional[str] = Form(None),
    # Photo de profil
    photo_profil: UploadFile | None = File(None),
    # Informations entreprise
    siret: Optional[str] = Form(None),
    siren: Optional[str] = Form(None),
    raison_sociale: Optional[str] = Form(None),
    code_naf: Optional[str] = Form(None),
    date_creation: Optional[str] = Form(None),
    adresse_entreprise: Optional[str] = Form(None),
    chiffre_affaires: Optional[str] = Form(None),
    nombre_points_vente: Optional[str] = Form(None),
    # Informations restauration
    specialite_culinaire: Optional[str] = Form(None),
    nom_concept: Optional[str] = Form(None),
    site_internet: Optional[str] = Form(None),
    lien_reseaux_sociaux: Optional[str] = Form(None),
    # Informations géographiques
    qpv: Optional[str] = Form(None),
    lat: Optional[str] = Form(None),
    lng: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    pre = session.get(Preinscription, pre_id)
    if not pre:
        raise HTTPException(status_code=404, detail="Préinscription introuvable")
    cand = session.get(Candidat, pre.candidat_id)
    # Charger les documents du candidat
    if cand:
        from ...models.base import Document
        cand.documents = session.exec(select(Document).where(Document.candidat_id == cand.id)).all()
    ent = session.exec(select(Entreprise).where(Entreprise.candidat_id==cand.id)).first()
    if not ent:
        ent = Entreprise(candidat_id=cand.id)
        session.add(ent); session.flush()

    # Mise à jour des informations personnelles
    if civilite:
        cand.civilite = civilite
    if date_naissance:
        try:
            cand.date_naissance = _date.fromisoformat(date_naissance)
        except Exception:
            pass
    if telephone is not None:
        cand.telephone = telephone
    if adresse_personnelle is not None:
        cand.adresse_personnelle = adresse_personnelle
    if niveau_etudes is not None:
        cand.niveau_etudes = niveau_etudes
    if secteur_activite is not None:
        cand.secteur_activite = secteur_activite
    cand.handicap = handicap == "true"
    
    # Mise à jour de la photo de profil
    if photo_profil and photo_profil.filename:
        try:
            from ...services.uploads import validate_upload
            from pathlib import Path
            import shutil
            
            # Validation du fichier
            validate_upload(
                photo_profil,
                allowed_mime_types=settings.ALLOWED_IMAGE_MIME_TYPES,
                max_mb=settings.MAX_UPLOAD_SIZE_MB,
                field_name="photo_profil",
            )
            
            # Supprimer l'ancienne photo si elle existe
            if cand.photo_profil:
                old_path = Path(settings.MEDIA_ROOT) / cand.photo_profil
                if old_path.exists():
                    old_path.unlink()
                    if settings.DEBUG:
                        print(f"🗑️ [DEBUG] Ancienne photo supprimée: {old_path}")
            
            # Créer le dossier de destination
            prog = session.get(Programme, pre.programme_id)
            base_dir = Path(settings.MEDIA_ROOT) / "Preinscrits" / (prog.code or "UNK") / str(pre.id)
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Nom de fichier unique avec ID de préinscription
            ext = os.path.splitext(photo_profil.filename)[1].lower() or ".jpg"
            photo_path = base_dir / f"photo_profil_{pre.id}{ext}"
            
            # Sauvegarder le nouveau fichier
            with open(photo_path, "wb") as f:
                shutil.copyfileobj(photo_profil.file, f)
            
            # Mettre à jour le candidat avec le chemin relatif
            cand.photo_profil = f"Preinscrits/{prog.code or 'UNK'}/{pre.id}/photo_profil_{pre.id}{ext}"
            
            if settings.DEBUG:
                print(f"📸 [DEBUG] Nouvelle photo sauvegardée: {photo_path}")
                print(f"📸 [DEBUG] Chemin relatif: {cand.photo_profil}")
                
        except Exception as e:
            if settings.DEBUG:
                print(f"❌ [DEBUG] Erreur sauvegarde photo: {e}")
            # On continue sans la photo
    
    if chiffre_affaires is not None:
        ent.chiffre_affaires = chiffre_affaires  # Maintenant c'est une string
    if nombre_points_vente is not None and nombre_points_vente.strip():
        try:
            ent.nombre_points_vente = int(nombre_points_vente)
        except (ValueError, TypeError):
            pass  # Ignorer les valeurs invalides
    
    # Mise à jour des informations restauration
    if specialite_culinaire is not None:
        ent.specialite_culinaire = specialite_culinaire
    if nom_concept is not None:
        ent.nom_concept = nom_concept
    if site_internet is not None:
        ent.site_internet = site_internet
    if lien_reseaux_sociaux is not None:
        ent.lien_reseaux_sociaux = lien_reseaux_sociaux
    
    # Mise à jour des informations géographiques
    ent.qpv = qpv == "true"
    
    # Conversion sécurisée des coordonnées GPS
    if lat is not None and lat.strip():
        try:
            cand.lat = float(lat)
        except (ValueError, TypeError):
            pass  # Ignorer les valeurs invalides
    if lng is not None and lng.strip():
        try:
            cand.lng = float(lng)
        except (ValueError, TypeError):
            pass  # Ignorer les valeurs invalides

    # Mise à jour des informations entreprise
    if siret is not None:
        ent.siret = siret
    if siren is not None:
        ent.siren = siren
    if raison_sociale is not None:
        ent.raison_sociale = raison_sociale
    if code_naf is not None:
        ent.code_naf = code_naf
    if date_creation:
        try:
            ent.date_creation = _date.fromisoformat(date_creation)
        except Exception:
            pass
    if adresse_entreprise is not None:
        ent.adresse = adresse_entreprise

    session.commit()
    
    # Log de l'activité
    from ...services.ACD.audit import log_activity
    log_activity(
        session=session,
        user=current_user,
        action="Mise à jour informations candidat",
        entity="Candidat",
        entity_id=cand.id,
        activity_data={
            "preinscription_id": pre_id,
            "champs_modifies": [
                "civilite", "date_naissance", "telephone", "adresse_personnelle",
                "niveau_etudes", "secteur_activite", "handicap", "siret", "siren",
                "raison_sociale", "code_naf", "date_creation", "adresse_entreprise",
                "chiffre_affaires", "nombre_points_vente", "specialite_culinaire",
                "nom_concept", "site_internet", "lien_reseaux_sociaux", "qpv"
            ]
        }
    )
    
    prog = session.get(Programme, pre.programme_id)
    return RedirectResponse(url=f"/ACD/inscriptions/form?programme={prog.code}&pre_id={pre.id}&success=infos_updated", status_code=303)


# Recalcul eligibilité
@router.post("/inscriptions/eligibilite/recalc")
def elig_recalc(
    pre_id: int = Form(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        print(f"🔄 [RECALC] Début recalcul éligibilité pour préinscription {pre_id}")
        
        pre = session.get(Preinscription, pre_id)
        if not pre:
            print(f"❌ [RECALC] Préinscription {pre_id} introuvable")
            raise HTTPException(status_code=404, detail="Préinscription introuvable")
        
        prog = session.get(Programme, pre.programme_id)
        if not prog:
            print(f"❌ [RECALC] Programme {pre.programme_id} introuvable")
            raise HTTPException(status_code=404, detail="Programme introuvable")
        
        cand = session.get(Candidat, pre.candidat_id)
        if not cand:
            print(f"❌ [RECALC] Candidat {pre.candidat_id} introuvable")
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        ent = session.exec(select(Entreprise).where(Entreprise.candidat_id==cand.id)).first()
        if not ent:
            print(f"❌ [RECALC] Entreprise pour candidat {cand.id} introuvable")
            raise HTTPException(status_code=404, detail="Entreprise introuvable")

        print(f"📊 [RECALC] Données trouvées - CA: {ent.chiffre_affaires}, Date création: {ent.date_creation}")
        
        ca = ent.chiffre_affaires
        anc = entreprise_age_annees(ent.date_creation)
        
        print(f"🔍 [RECALC] Calcul ancienneté: {anc} ans")
        
        verdict, details = evaluate_eligibilite(
            adresse_perso=cand.adresse_personnelle,
            adresse_entreprise=ent.adresse,
            chiffre_affaires=ca,
            anciennete_annees=anc,
            ca_min=prog.ca_seuil_min,
            ca_max=prog.ca_seuil_max,
            anciennete_min_annees=prog.anciennete_min_annees
        )
        
        print(f"✅ [RECALC] Évaluation terminée - Verdict: {verdict}, Details: {details}")
        
        elig = session.exec(select(Eligibilite).where(Eligibilite.preinscription_id==pre.id)).first()
        if not elig:
            print(f"🆕 [RECALC] Création nouvelle éligibilité")
            elig = Eligibilite(preinscription_id=pre.id)
            session.add(elig)
        
        elig.ca_seuil_ok = details.get("ca_ok")
        elig.ca_score = None  # Pas de valeur numérique unique pour les intervalles
        elig.qpv_ok = details.get("qpv_ok")
        elig.anciennete_ok = details.get("anciennete_ok")
        elig.anciennete_annees = details.get("anciennete_annees")
        elig.verdict = verdict
        session.commit()
        
        print(f"🎉 [RECALC] Recalcul terminé avec succès")
        
        return RedirectResponse(url=f"/ACD/inscriptions/form?programme={prog.code}&pre_id={pre.id}", status_code=303)
        
    except Exception as e:
        print(f"❌ [RECALC] Erreur lors du recalcul: {e}")
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors du recalcul: {str(e)}")


# Ajouter un document
@router.post("/inscriptions/add-document")
def add_document(
    candidat_id: int = Form(...),
    type_document: str = Form(...),
    document_file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        print(f"📄 [DOC] Ajout document pour candidat {candidat_id}")
        
        # Vérifier que le candidat existe
        candidat = session.get(Candidat, candidat_id)
        if not candidat:
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        # Valider le fichier
        if not document_file.filename:
            raise HTTPException(status_code=400, detail="Aucun fichier sélectionné")
        
        # Vérifier la taille (10MB max)
        file_content = document_file.file.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 10MB)")
        
        # Vérifier l'extension
        file_ext = os.path.splitext(document_file.filename)[1].lower() or ".pdf"
        allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Format de fichier non autorisé")
        
        # Préparer le répertoire de sauvegarde spécifique au candidat
        from ...core.config import settings
        candidat_dir = settings.FICHIERS_DIR / "documents" / f"candidat_{candidat_id}"
        candidat_dir.mkdir(parents=True, exist_ok=True)
        
        # Créer le nom de fichier unique basé sur le type et l'ID candidat
        base_filename = f"{type_document.lower()}_{candidat_id}{file_ext}"
        unique_filename = base_filename
        
        # Vérifier si le fichier existe déjà et ajouter un suffixe numérique si nécessaire
        counter = 1
        while (candidat_dir / unique_filename).exists():
            name_without_ext = f"{type_document.lower()}_{candidat_id}"
            unique_filename = f"{name_without_ext}_{counter}{file_ext}"
            counter += 1
        
        file_path = candidat_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        print(f"📄 [DOC] Fichier sauvegardé: {unique_filename}")
        print(f"📁 [DOC] Dossier candidat: {candidat_dir}")
        print(f"📄 [DOC] Chemin complet: {file_path}")
        
        # Créer l'enregistrement en base
        from ...models.base import Document
        from ...models.enums import TypeDocument
        
        doc = Document(
            candidat_id=candidat_id,
            nom_fichier=document_file.filename,
            chemin_fichier=str(file_path),
            taille_octets=len(file_content),
            type_document=TypeDocument(type_document) if type_document in [e.value for e in TypeDocument] else TypeDocument.AUTRE,
            description=description,
            date_upload=datetime.now(timezone.utc)
        )
        
        session.add(doc)
        session.commit()
        
        print(f"✅ [DOC] Document ajouté avec succès: {unique_filename}")
        
        # Rediriger vers la page avec un message de succès
        preinscription = session.exec(select(Preinscription).where(Preinscription.candidat_id == candidat_id)).first()
        if preinscription:
            programme = session.get(Programme, preinscription.programme_id)
            return RedirectResponse(
                url=f"/ACD/inscriptions/form?programme={programme.code}&pre_id={preinscription.id}&success=document_added",
                status_code=303
            )
        else:
            return RedirectResponse(url="/ACD/inscriptions?success=document_added", status_code=303)
            
    except Exception as e:
        print(f"❌ [DOC] Erreur lors de l'ajout: {e}")
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'ajout du document: {str(e)}")


# Supprimer un document
@router.post("/inscriptions/delete-document")
def delete_document(
    document_id: int = Form(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        print(f"🗑️ [DOC] Suppression document {document_id}")
        
        # Récupérer le document
        from ...models.base import Document
        doc = session.get(Document, document_id)
        if not doc:
            return {"success": False, "error": "Document introuvable"}
        
        # Supprimer le fichier physique
        if doc.chemin_fichier and os.path.exists(doc.chemin_fichier):
            os.remove(doc.chemin_fichier)
            print(f"🗑️ [DOC] Fichier supprimé: {doc.chemin_fichier}")
        
        # Supprimer l'enregistrement en base
        session.delete(doc)
        session.commit()
        
        print(f"✅ [DOC] Document supprimé avec succès")
        
        # Rediriger vers la page avec un message de succès
        preinscription = session.exec(select(Preinscription).where(Preinscription.candidat_id == doc.candidat_id)).first()
        if preinscription:
            programme = session.get(Programme, preinscription.programme_id)
            return RedirectResponse(
                url=f"/ACD/inscriptions/form?programme={programme.code}&pre_id={preinscription.id}&success=document_deleted",
                status_code=303
            )
        else:
            return RedirectResponse(url="/ACD/inscriptions?success=document_deleted", status_code=303)
        
    except Exception as e:
        print(f"❌ [DOC] Erreur lors de la suppression: {e}")
        session.rollback()
        return {"success": False, "error": str(e)}


# Avancement d'étape
@router.post("/inscriptions/etape/advance")
def etape_advance(
    avancement_id: int = Form(...),
    statut: str = Form(...),  # A_FAIRE | EN_COURS | TERMINE
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    av = session.get(AvancementEtape, avancement_id)
    if not av:
        raise HTTPException(status_code=404, detail="Avancement introuvable")
    try:
        new_status = StatutEtape[statut]
    except Exception:
        raise HTTPException(status_code=400, detail="Statut invalide")

    from datetime import datetime as _dt
    av.statut = new_status
    now = _dt.utcnow()
    if new_status.name == "EN_COURS" and not av.debut_le:
        av.debut_le = now
    if new_status.name == "TERMINE":
        if not av.debut_le: av.debut_le = now
        av.termine_le = now

    session.commit()
    ins = session.get(Inscription, av.inscription_id)
    prog = session.get(Programme, ins.programme_id)
    pre = session.exec(select(Preinscription).where(Preinscription.programme_id==prog.id, Preinscription.candidat_id==ins.candidat_id)).first()
    return RedirectResponse(url=f"ACD/inscriptions?programme={prog.code}&pre_id={pre.id if pre else ''}", status_code=303)


# Décision de jury
@router.post("/inscriptions/jury/decision")
def jury_decision(
    inscription_id: int = Form(...),
    decision: str = Form(...),  # ACCEPTE | LISTE_ATTENTE | REFUSE
    commentaires: Optional[str] = Form(None),
    jury_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    ins = session.get(Inscription, inscription_id)
    if not ins:
        raise HTTPException(status_code=404, detail="Inscription introuvable")

    jury = session.get(Jury, jury_id) if jury_id else None

    # Enum DecisionJury sur ton modèle; si c’est un Enum, on mappe :
    from ...models.enums import DecisionJury as DecisionEnum  # adapte si ailleurs
    try:
        dec_enum = DecisionEnum[decision]
    except Exception:
        dec_enum = DecisionEnum.REFUSE  # fallback

    dj = DecisionJuryTable(
        inscription_id=inscription_id,
        jury_id=jury.id if jury else None,
        decision=dec_enum,
        commentaires=commentaires
    )
    session.add(dj)
    session.commit()

    prog = session.get(Programme, ins.programme_id)
    pre = session.exec(select(Preinscription).where(Preinscription.programme_id==prog.id, Preinscription.candidat_id==ins.candidat_id)).first()
    return RedirectResponse(url=f"ACD/inscriptions?programme={prog.code}&pre_id={pre.id if pre else ''}", status_code=303)


# --------- GESTION DES DÉCISIONS DU JURY ---------
@router.post("/inscriptions/jury/decision")
def create_jury_decision(
    candidat_id: int = Form(...),
    jury_id: int = Form(...),
    decision: str = Form(...),
    commentaires: Optional[str] = Form(None),
    conseiller_id: Optional[int] = Form(None),
    groupe_codev: Optional[str] = Form(None),
    promotion_id: Optional[int] = Form(None),
    partenaire_id: Optional[int] = Form(None),
    envoyer_mail_candidat: bool = Form(False),
    envoyer_mail_conseiller: bool = Form(False),
    envoyer_mail_partenaire: bool = Form(False),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Créer une décision du jury"""
    
    # Vérifier que le candidat existe
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Vérifier que le jury existe
    jury = session.get(Jury, jury_id)
    if not jury:
        raise HTTPException(status_code=404, detail="Jury introuvable")
    
    # Vérifier qu'il n'y a pas déjà une décision pour ce candidat et ce jury
    existing = session.exec(
        select(DecisionJuryCandidat).where(
            (DecisionJuryCandidat.candidat_id == candidat_id) &
            (DecisionJuryCandidat.jury_id == jury_id)
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Une décision existe déjà pour ce candidat et ce jury")
    
    # Créer la décision
    decision_obj = DecisionJuryCandidat(
        candidat_id=candidat_id,
        jury_id=jury_id,
        decision=DecisionJury(decision),
        commentaires=commentaires,
        conseiller_id=conseiller_id if decision == DecisionJury.VALIDE.value else None,
        groupe_codev=groupe_codev if decision == DecisionJury.VALIDE.value else None,
        promotion_id=promotion_id if decision == DecisionJury.VALIDE.value else None,
        partenaire_id=partenaire_id if decision == DecisionJury.REORIENTE.value else None,
        envoyer_mail_candidat=envoyer_mail_candidat,
        envoyer_mail_conseiller=envoyer_mail_conseiller,
        envoyer_mail_partenaire=envoyer_mail_partenaire,
    )
    
    session.add(decision_obj)
    session.flush()
    
    # Mettre à jour le statut du candidat
    candidat.statut = decision
    
    # Si réorienté, créer l'enregistrement de réorientation
    if decision == DecisionJury.REORIENTE.value and partenaire_id:
        reorientation = ReorientationCandidat(
            candidat_id=candidat_id,
            partenaire_id=partenaire_id,
            decision_jury_id=decision_obj.id,
            mail_envoye=envoyer_mail_partenaire,
        )
        session.add(reorientation)
    
    session.commit()
    
    # TODO: Envoyer les emails selon les cases cochées
    if envoyer_mail_candidat or envoyer_mail_conseiller or envoyer_mail_partenaire:
        # Logique d'envoi d'emails à implémenter
        pass
    
    # Log de l'activité
    from ...services.ACD.audit import log_activity
    log_activity(
        session=session,
        user=current_user,
        action="Décision jury créée",
        entity="DecisionJuryCandidat",
        entity_id=decision_obj.id,
        activity_data={
            "candidat_id": candidat_id,
            "jury_id": jury_id,
            "decision": decision,
            "emails_envoyes": {
                "candidat": envoyer_mail_candidat,
                "conseiller": envoyer_mail_conseiller,
                "partenaire": envoyer_mail_partenaire,
            }
        }
    )
    
    # Redirection vers la page d'inscription
    prog = session.exec(select(Programme).join(Preinscription).where(Preinscription.candidat_id == candidat_id)).first()
    pre = session.exec(select(Preinscription).where(Preinscription.candidat_id == candidat_id)).first()
    return RedirectResponse(url=f"/ACD/inscriptions/form?programme={prog.code if prog else 'ACD'}&pre_id={pre.id if pre else ''}&success=decision_created", status_code=303)


@router.post("/inscriptions/jury/decision/{decision_id}/delete")
def delete_jury_decision(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Supprimer une décision du jury"""
    
    decision_obj = session.get(DecisionJuryCandidat, decision_id)
    if not decision_obj:
        raise HTTPException(status_code=404, detail="Décision introuvable")
    
    candidat_id = decision_obj.candidat_id
    
    # Remettre le candidat en attente
    candidat = session.get(Candidat, candidat_id)
    if candidat:
        candidat.statut = DecisionJury.EN_ATTENTE.value
    
    # Supprimer les réorientations associées
    session.exec(
        select(ReorientationCandidat).where(
            ReorientationCandidat.decision_jury_id == decision_id
        )
    )
    
    session.delete(decision_obj)
    session.commit()
    
    # Log de l'activité
    from ...services.ACD.audit import log_activity
    log_activity(
        session=session,
        user=current_user,
        action="Décision jury supprimée",
        entity="DecisionJuryCandidat",
        entity_id=decision_id,
        activity_data={
            "candidat_id": candidat_id,
        }
    )
    
    # Redirection vers la page d'inscription
    prog = session.exec(select(Programme).join(Preinscription).where(Preinscription.candidat_id == candidat_id)).first()
    pre = session.exec(select(Preinscription).where(Preinscription.candidat_id == candidat_id)).first()
    return RedirectResponse(url=f"/ACD/inscriptions/form?programme={prog.code if prog else 'ACD'}&pre_id={pre.id if pre else ''}&success=decision_deleted", status_code=303)


# --------- INTÉGRATION QPV ET SIRET ---------
@router.post("/inscriptions/qpv-check")
async def check_qpv_candidate(
    candidat_id: int = Form(...),
    adresse_personnelle: Optional[str] = Form(None),
    adresse_entreprise: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Vérifier le statut QPV pour un candidat en analysant son adresse personnelle et celle de l'entreprise"""
    
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Récupérer les adresses depuis la base si non fournies
    if not adresse_personnelle or not adresse_entreprise:
        entreprise = session.exec(select(Entreprise).where(Entreprise.candidat_id == candidat_id)).first()
        
        # Adresse personnelle du candidat
        if not adresse_personnelle:
            adresse_personnelle = candidat.adresse_personnelle
        
        # Adresse de l'entreprise
        if not adresse_entreprise and entreprise:
            adresse_entreprise = entreprise.adresse
    
    # 🔍 VÉRIFICATION PRÉALABLE : Recherche existante ?
    preinscription = session.exec(
        select(Preinscription).where(Preinscription.candidat_id == candidat_id)
    ).first()
    
    if preinscription:
        eligibilite = session.exec(
            select(Eligibilite).where(Eligibilite.preinscription_id == preinscription.id)
        ).first()
        
        # Si une vérification QPV existe déjà et les adresses n'ont pas changé
        if eligibilite and eligibilite.qpv_ok is not None and eligibilite.details_json:
            try:
                import json
                import ast
                
                print(f"🔍 [QPV] Données existantes trouvées pour candidat {candidat_id}")
                print(f"🔍 [QPV] QPV OK: {eligibilite.qpv_ok}")
                
                # Essayer de parser le JSON
                try:
                    details_existants = json.loads(eligibilite.details_json)
                    print(f"🔍 [QPV] JSON parsé avec succès")
                except json.JSONDecodeError:
                    # Si JSON échoue, essayer de parser comme un dict Python (ancien format)
                    try:
                        details_existants = ast.literal_eval(eligibilite.details_json)
                        print(f"🔍 [QPV] Dict Python parsé avec succès (ancien format)")
                    except (ValueError, SyntaxError) as e:
                        print(f"❌ [QPV] Impossible de parser les données en cache: {e}")
                        raise
                
                # Vérifier si les adresses correspondent
                adresses_existantes = details_existants.get("adresses_analysees", [])
                print(f"🔍 [QPV] Adresses en cache: {len(adresses_existantes)}")
                
                if adresses_existantes:
                    # Comparer les adresses (simplifié)
                    adresse_existante_perso = adresses_existantes[0].get("adresse", "") if len(adresses_existantes) > 0 else ""
                    adresse_existante_ent = adresses_existantes[1].get("adresse", "") if len(adresses_existantes) > 1 else ""
                    
                    print(f"🔍 [QPV] Comparaison adresses:")
                    print(f"   - Personnelle: '{adresse_personnelle}' vs '{adresse_existante_perso}'")
                    print(f"   - Entreprise: '{adresse_entreprise}' vs '{adresse_existante_ent}'")
                    
                    # Comparaison plus flexible (ignore les espaces en début/fin)
                    perso_match = adresse_personnelle.strip() == adresse_existante_perso.strip() if adresse_personnelle else adresse_existante_perso == "Non disponible"
                    ent_match = adresse_entreprise.strip() == adresse_existante_ent.strip() if adresse_entreprise else adresse_existante_ent == "Non disponible"
                    
                    if perso_match and ent_match:
                        print(f"✅ [QPV] Utilisation des données existantes pour candidat {candidat_id}")
                        return {
                            "candidat_id": candidat_id,
                            "adresses_analysees": adresses_existantes,
                            "statut_qpv_final": "QPV" if eligibilite.qpv_ok else "NON_QPV",
                            "details": details_existants,
                            "from_cache": True
                        }
                    else:
                        print(f"⚠️ [QPV] Adresses différentes, nouvelle recherche nécessaire")
                else:
                    print(f"⚠️ [QPV] Aucune adresse en cache")
            except (json.JSONDecodeError, KeyError, IndexError, ValueError, SyntaxError) as e:
                print(f"❌ [QPV] Erreur lors de la lecture du cache: {e}")
                pass  # Continuer avec une nouvelle recherche
        else:
            print(f"⚠️ [QPV] Pas de données en cache - eligibilite: {bool(eligibilite)}, qpv_ok: {eligibilite.qpv_ok if eligibilite else None}")
    
    # Si pas de données existantes ou adresses différentes, lancer la recherche
    print(f"🔍 [QPV] Lancement nouvelle recherche pour candidat {candidat_id}")
    
    results = {
        "candidat_id": candidat_id,
        "adresses_analysees": [],
        "statut_qpv_final": "NON_QPV",
        "details": {}
    }
    
    # Analyser l'adresse personnelle du candidat si disponible
    print(f"🔍 [QPV] Adresse personnelle reçue: '{adresse_personnelle}'")
    if adresse_personnelle and adresse_personnelle.strip():
        try:
            print(f"🔍 [QPV] Analyse adresse personnelle: {adresse_personnelle}")
            qpv_personnelle = await verif_qpv({"address": adresse_personnelle}, request)
            results["adresses_analysees"].append({
                "type": "personnelle",
                "adresse": adresse_personnelle,
                "resultat": qpv_personnelle
            })
            results["details"]["personnelle"] = qpv_personnelle
            print(f"✅ [QPV] Adresse personnelle analysée avec succès")
        except Exception as e:
            print(f"❌ [QPV] Erreur analyse adresse personnelle: {e}")
            results["adresses_analysees"].append({
                "type": "personnelle",
                "adresse": adresse_personnelle,
                "erreur": str(e)
            })
    else:
        print(f"⚠️ [QPV] Adresse personnelle vide ou non fournie")
        results["adresses_analysees"].append({
            "type": "personnelle",
            "adresse": "Non disponible",
            "non_disponible": True
        })
    
    # Analyser l'adresse de l'entreprise si disponible
    print(f"🔍 [QPV] Adresse entreprise reçue: '{adresse_entreprise}'")
    if adresse_entreprise and adresse_entreprise.strip():
        try:
            print(f"🔍 [QPV] Analyse adresse entreprise: {adresse_entreprise}")
            qpv_entreprise = await verif_qpv({"address": adresse_entreprise}, request)
            results["adresses_analysees"].append({
                "type": "entreprise",
                "adresse": adresse_entreprise,
                "resultat": qpv_entreprise
            })
            results["details"]["entreprise"] = qpv_entreprise
            print(f"✅ [QPV] Adresse entreprise analysée avec succès")
        except Exception as e:
            print(f"❌ [QPV] Erreur analyse entreprise: {e}")
            results["adresses_analysees"].append({
                "type": "entreprise",
                "adresse": adresse_entreprise,
                "erreur": str(e)
            })
    else:
        print(f"⚠️ [QPV] Adresse entreprise vide ou non fournie")
        results["adresses_analysees"].append({
            "type": "entreprise",
            "adresse": "Non disponible",
            "non_disponible": True
        })
    
    # Déterminer le statut QPV final
    qpv_found = False
    for analyse in results["adresses_analysees"]:
        if "resultat" in analyse:
            nom_qp = analyse["resultat"].get("nom_qp", "")
            if "QPV:" in nom_qp or "QPV limit:" in nom_qp:
                qpv_found = True
                results["statut_qpv_final"] = "QPV"
                break
    
    # Mettre à jour l'éligibilité du candidat
    if candidat:
        preinscription = session.exec(
            select(Preinscription).where(Preinscription.candidat_id == candidat_id)
        ).first()
        
        if preinscription:
            eligibilite = session.exec(
                select(Eligibilite).where(Eligibilite.preinscription_id == preinscription.id)
            ).first()
            
            if not eligibilite:
                eligibilite = Eligibilite(preinscription_id=preinscription.id)
                session.add(eligibilite)
            
            import json
            eligibilite.qpv_ok = qpv_found
            eligibilite.details_json = json.dumps(results)  # Sauvegarder results complet, pas seulement details
            session.add(eligibilite)
            session.commit()
            
            print(f"✅ [QPV] Éligibilité mise à jour - QPV: {qpv_found}")
    
    # Log de l'activité
    from ...services.ACD.audit import log_activity
    log_activity(
        session=session,
        user=current_user,
        action="Vérification QPV candidat",
        entity="Candidat",
        entity_id=candidat_id,
        activity_data={
            "statut_qpv": results["statut_qpv_final"],
            "adresses_analysees": len(results["adresses_analysees"]),
            "details": results["details"]
        }
    )
    
    print(f"🔍 [QPV] Résultat final: {len(results['adresses_analysees'])} adresses analysées")
    print(f"🔍 [QPV] Statut final: {results['statut_qpv_final']}")
    
    return results


@router.post("/inscriptions/siret-check")
async def check_siret_candidate(
    candidat_id: int = Form(...),
    numero_siret: str = Form(...),
    request: Request = None,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Vérifier les informations SIRET pour un candidat"""
    
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    try:
        print(f"🔍 [SIRET] Recherche SIRET: {numero_siret}")
        
        # Valider le format SIRET
        siret_request = SiretRequest(numero_siret=numero_siret)
        
        # Appeler le service SIRET
        siret_info = await get_entreprise_process(siret_request.numero_siret[:9], request)
        
        # Mettre à jour les informations de l'entreprise
        entreprise = session.exec(
            select(Entreprise).where(Entreprise.candidat_id == candidat_id)
        ).first()
        
        if not entreprise:
            entreprise = Entreprise(candidat_id=candidat_id)
            session.add(entreprise)
        
        if siret_info.get("entreprise_data"):
            data = siret_info["entreprise_data"]
            
            # Mettre à jour les champs de l'entreprise
            entreprise.siret = data.get("siege", {}).get("siret")
            entreprise.siren = data.get("siren")
            entreprise.nom_entreprise = data.get("nom_entreprise")
            entreprise.forme_juridique = data.get("forme_juridique")
            entreprise.date_creation = data.get("date_creation")
            entreprise.code_naf = data.get("code_naf")
            entreprise.activite = data.get("activite")
            entreprise.effectif = data.get("effectif")
            entreprise.capital = data.get("capital")
            
            # Mettre à jour l'adresse du siège
            siege = data.get("siege", {})
            entreprise.adresse = siege.get("adresse")
            entreprise.code_postal = siege.get("code_postal")
            entreprise.ville = siege.get("ville")
            entreprise.lat = siege.get("latitude")
            entreprise.lng = siege.get("longitude")
            
            session.add(entreprise)
            session.commit()
            
            print(f"✅ [SIRET] Informations entreprise mises à jour")
        
        # Log de l'activité
        from ...services.ACD.audit import log_activity
        log_activity(
            session=session,
            user=current_user,
            action="Vérification SIRET candidat",
            entity="Candidat",
            entity_id=candidat_id,
            activity_data={
                "numero_siret": numero_siret,
                "entreprise_trouvee": bool(siret_info.get("entreprise_data")),
                "status_code": siret_info.get("status_code")
            }
        )
        
        return {
            "candidat_id": candidat_id,
            "numero_siret": numero_siret,
            "resultat": siret_info,
            "entreprise_mise_a_jour": bool(siret_info.get("entreprise_data"))
        }
        
    except Exception as e:
        print(f"❌ [SIRET] Erreur: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification SIRET: {str(e)}")


@router.get("/inscriptions/qpv-status/{candidat_id}")
def get_qpv_status(
    candidat_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Récupérer le statut QPV actuel d'un candidat"""
    
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Récupérer l'éligibilité
    preinscription = session.exec(
        select(Preinscription).where(Preinscription.candidat_id == candidat_id)
    ).first()
    
    if not preinscription:
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    eligibilite = session.exec(
        select(Eligibilite).where(Eligibilite.preinscription_id == preinscription.id)
    ).first()
    
    if not eligibilite:
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    return {
        "statut_qpv": "QPV" if eligibilite.qpv_ok else "NON_QPV",
        "details": eligibilite.details_json,
        "derniere_verification": eligibilite.cree_le
    }


# Routes pour servir les fichiers documents
@router.get("/inscriptions/document/{document_id}/view")
def view_document(
    document_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Afficher un document dans le navigateur."""
    try:
        from ...models.base import Document
        
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable")
        
        if not doc.chemin_fichier or not os.path.exists(doc.chemin_fichier):
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        
        # Déterminer le type MIME
        import mimetypes
        mime_type, _ = mimetypes.guess_type(doc.chemin_fichier)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Lire le fichier
        with open(doc.chemin_fichier, "rb") as f:
            content = f.read()
        
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"inline; filename={doc.nom_fichier}",
                "Content-Length": str(len(content))
            }
        )
        
    except Exception as e:
        print(f"❌ [DOC] Erreur lors de l'affichage: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du document: {str(e)}")


@router.get("/inscriptions/document/{document_id}/download")
def download_document(
    document_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Télécharger un document."""
    try:
        from ...models.base import Document
        from fastapi.responses import FileResponse
        
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable")
        
        if not doc.chemin_fichier or not os.path.exists(doc.chemin_fichier):
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        
        return FileResponse(
            path=doc.chemin_fichier,
            filename=doc.nom_fichier,
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        print(f"❌ [DOC] Erreur lors du téléchargement: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du téléchargement du document: {str(e)}")
