# app/routers/inscriptions.py
from __future__ import annotations

import os
import logging
from datetime import date as _date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select
from sqlalchemy import func, text

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.config import settings
from ..core.security import get_current_user
from ..core.path_config import path_config
from ..core.program_schema_integration import (
    get_schema_routing_service,
    SchemaRoutingService,
    safe_count_query
)
from ..services.file_upload_service import FileUploadService
from ..templates import templates

from ..models.base import (
    Programme, Candidat, Entreprise, Preinscription, Eligibilite,
    Inscription, EtapePipeline, AvancementEtape, StatutEtape,
    DecisionJuryTable, Jury, DecisionJuryCandidat, Partenaire, User, Promotion, Groupe,
    ReorientationCandidat, Document
)
from ..schemas.preinscription_schemas import Adresse
from ..schemas.schema_qpv import QPVResponse, QPVErrorResponse
from ..schemas.schema_siret import SiretRequest
from ..services.service_qpv import verif_qpv
from ..services.service_siret_pappers import get_entreprise_process
from ..models.enums import TypeDocument, DecisionJury, UserRole, GroupeCodev, TypePromotion
from ..services.eligibilite import evaluate_eligibilite, entreprise_age_annees

router = APIRouter()

def _table_exists_in_schema(session: Session, table_name: str, schema_name: str) -> bool:
    """Vérifie si une table existe dans un schéma spécifique"""
    try:
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = :schema_name AND table_name = :table_name
            )
        """)
        return session.execute(check_query.bindparams(schema_name=schema_name, table_name=table_name)).scalar() or False
    except Exception:
        return False

def _prog_by_code(session: Session, code: str) -> Programme | None:
    # Le programme est toujours dans le schéma public
    if not _table_exists_in_schema(session, "programme", "public"):
        return None
    try:
        return session.exec(select(Programme).where(Programme.code == code)).first()
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération du programme {code}: {e}")
        return None

@router.get("/form", name="form_inscriptions_display", response_class=HTMLResponse)
def inscriptions_ui(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    programme: str = Query("ACD"),
    q: Optional[str] = Query(None),
    pre_id: Optional[int] = Query(None),
):
    # Gestion des transactions échouées - rollback si nécessaire
    try:
        session.rollback()
    except Exception:
        pass  # Ignorer les erreurs de rollback
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
    schema_name = programme.lower() if programme else "public"  # Définir schema_name au début
    
    if prog.id and _table_exists_in_schema(session, "preinscription", schema_name) and _table_exists_in_schema(session, "candidat", schema_name):
        try:
            
            # Configurer le search_path pour utiliser le schéma du programme
            session.execute(text(f"SET search_path TO {schema_name}, public"))
            
            # Utiliser des modèles dynamiques pour le schéma spécifique
            from ..core.program_schema_integration import SchemaRoutingService
            schema_routing_service = SchemaRoutingService(session)
            schema_routing_service.set_schema(schema_name)
            
            PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
            CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
            EntrepriseSchema = schema_routing_service.get_model_for_schema(Entreprise, schema_name)
            EligibiliteSchema = schema_routing_service.get_model_for_schema(Eligibilite, schema_name)
            
            stmt = (
                select(PreinscriptionSchema, CandidatSchema, EntrepriseSchema, EligibiliteSchema)
                .join(CandidatSchema, CandidatSchema.id==PreinscriptionSchema.candidat_id)
                .join(EntrepriseSchema, EntrepriseSchema.candidat_id==CandidatSchema.id, isouter=True)
                .join(EligibiliteSchema, EligibiliteSchema.preinscription_id==PreinscriptionSchema.id, isouter=True)
                .where(PreinscriptionSchema.programme_id==prog.id)
            )
            if q:
                like = f"%{q}%"
                stmt = stmt.where((CandidatSchema.nom.ilike(like)) | (CandidatSchema.prenom.ilike(like)) | (CandidatSchema.email.ilike(like)))
            pre_rows = session.exec(stmt.order_by(PreinscriptionSchema.cree_le.desc()).limit(400)).all()
        except Exception as e:
            logging.warning(f"⚠️ [WARNING] Erreur lors de la récupération des préinscriptions: {e}")
            import traceback
            logging.error(traceback.format_exc())
            session.rollback()
            pre_rows = []
    else:
        print(f"⚠️ [WARNING] Tables preinscription ou candidat manquantes - retour liste vide")
        
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
            # Utiliser le schéma du programme pour les requêtes d'inscription
            session.execute(text(f"SET search_path TO {schema_name}, public"))
            
            # Charger les documents du candidat avec le bon schéma
            cand.documents = []
            try:
                # Vérifier directement dans le schéma spécifique
                check_table = text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = :schema_name AND table_name = 'document'
                    )
                """)
                table_exists = session.execute(check_table.bindparams(schema_name=schema_name)).scalar()
                
                if table_exists:
                    # Utiliser une requête SQL directe avec le schéma explicite
                    documents_query = text(f"""
                        SELECT * FROM {schema_name}.document 
                        WHERE candidat_id = :candidat_id
                        ORDER BY depose_le DESC
                    """)
                    doc_results = session.execute(documents_query.bindparams(candidat_id=cand.id)).all()
                    for doc_row in doc_results:
                        doc_dict = dict(doc_row._mapping)
                        # Utiliser merge() pour éviter les conflits avec les objets existants
                        doc = Document(**doc_dict)
                        merged_doc = session.merge(doc)
                        cand.documents.append(merged_doc)
            except Exception as e:
                logging.warning(f"Erreur lors de la récupération des documents: {e}")
                cand.documents = []
                # Rollback pour nettoyer la session en cas d'erreur
                try:
                    session.rollback()
                except Exception:
                    pass
            
            # Récupérer l'inscription avec le schéma correct
            inscription = None
            try:
                # Vérifier directement dans le schéma spécifique
                check_table = text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = :schema_name AND table_name = 'inscription'
                    )
                """)
                table_exists = session.execute(check_table.bindparams(schema_name=schema_name)).scalar()
                
                if table_exists:
                    # Utiliser une requête SQL directe avec le schéma explicite
                    inscription_query = text(f"""
                        SELECT * FROM {schema_name}.inscription 
                        WHERE programme_id = :programme_id AND candidat_id = :candidat_id
                        LIMIT 1
                    """)
                    result = session.execute(inscription_query.bindparams(
                        programme_id=prog.id,
                        candidat_id=cand.id
                    )).first()
                    
                    if result:
                        # Créer un objet Inscription à partir du résultat
                        inscription = Inscription(**dict(result._mapping))
            except Exception as e:
                logging.warning(f"Erreur lors de la récupération de l'inscription: {e}")
                inscription = None
            
            if inscription:
                # Pipeline (avancement attaché)
                try:
                    # Vérifier directement dans le schéma spécifique
                    check_av = text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = :schema_name AND table_name = 'avancement_etape'
                        )
                    """)
                    check_ep = text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = :schema_name AND table_name = 'etape_pipeline'
                        )
                    """)
                    av_exists = session.execute(check_av.bindparams(schema_name=schema_name)).scalar()
                    ep_exists = session.execute(check_ep.bindparams(schema_name=schema_name)).scalar()
                    
                    if av_exists and ep_exists:
                        av_query = text(f"""
                            SELECT ae.*, ep.* 
                            FROM {schema_name}.avancement_etape ae
                            JOIN {schema_name}.etape_pipeline ep ON ae.etape_id = ep.id
                            WHERE ae.inscription_id = :inscription_id
                            ORDER BY ep.ordre
                        """)
                        av_results = session.execute(av_query.bindparams(inscription_id=inscription.id)).all()
                        pipeline = []
                        for av_row in av_results:
                            pipeline.append({
                                "id": av_row.id,
                                "statut": av_row.statut,
                                "etape": {"libelle": av_row.libelle, "type_etape": av_row.type_etape, "ordre": av_row.ordre},
                                "debut": av_row.debut_le,
                                "fin": av_row.termine_le
                            })
                    else:
                        pipeline = []
                except Exception as e:
                    logging.warning(f"Erreur lors de la récupération du pipeline: {e}")
                    pipeline = []

    # KPI simples
    total_pre = 0
    total_insc = 0
    taux_conv = 0.0
    objectif_qpv_atteint = 0.0
    
    if prog.id:
        total_pre = 0
        if _table_exists_in_schema(session, "preinscription", schema_name):
            total_pre = safe_count_query(session, Preinscription, programme_id=prog.id)
        
        total_insc = 0
        if _table_exists_in_schema(session, "inscription", schema_name):
            total_insc = safe_count_query(session, Inscription, programme_id=prog.id)
        taux_conv = round((total_insc / total_pre * 100), 1) if total_pre else 0.0

        # Objectif QPV (ex: % de préinscrits ayant qpv_ok) - Version sécurisée
        qpv_ok_count = 0
        if _table_exists_in_schema(session, "eligibilite", schema_name) and _table_exists_in_schema(session, "preinscription", schema_name):
            try:
                qpv_ok_count = session.exec(
                    select(func.count(Eligibilite.id)).join(Preinscription).where(
                        (Preinscription.programme_id==prog.id) & (Eligibilite.qpv_ok.is_(True))
                    )
                ).one() or 0
            except Exception as e:
                logging.warning(f"Erreur lors du comptage QPV: {e}")
                qpv_ok_count = 0
        objectif_qpv_atteint = round((qpv_ok_count / total_pre * 100), 1) if total_pre else 0.0

    # Jury sessions futures + récentes - Version sécurisée
    jurys = []
    if prog.id and _table_exists_in_schema(session, "jury", schema_name):
        try:
            # Utiliser le schéma du programme pour les jurys
            session.execute(text(f"SET search_path TO {schema_name}, public"))
            jury_query = text(f"""
                SELECT * FROM {schema_name}.jury 
                WHERE programme_id = :programme_id 
                ORDER BY session_le DESC
            """)
            jury_results = session.execute(jury_query.bindparams(programme_id=prog.id)).all()
            jurys = []
            for jury_row in jury_results:
                jurys.append(Jury(**dict(jury_row._mapping)))
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des jurys: {e}")
            jurys = []

    # Données pour le système de décisions du jury
    decisions_jury = []
    conseillers = []
    promotions = []
    partenaires = []
    
    if cand and _table_exists_in_schema(session, "decision_jury_candidat", schema_name):
        try:
            # Utiliser le schéma du programme pour les décisions du jury
            session.execute(text(f"SET search_path TO {schema_name}, public"))
            decision_query = text(f"""
                SELECT djc.* 
                FROM {schema_name}.decision_jury_candidat djc
                WHERE djc.candidat_id = :candidat_id
                ORDER BY djc.date_decision DESC
            """)
            decision_results = session.execute(decision_query.bindparams(candidat_id=cand.id)).all()
            decisions_jury = []
            for dec_row in decision_results:
                dec_dict = dict(dec_row._mapping)
                # Charger les relations si nécessaire
                decisions_jury.append(DecisionJuryCandidat(**dec_dict))
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des décisions jury: {e}")
            import traceback
            logging.error(traceback.format_exc())
            decisions_jury = []
    
    # Récupérer les conseillers
    conseillers = []
    try:
        session.rollback()
        conseillers = session.exec(select(User).where(User.role == UserRole.CONSEILLER.value)).all()
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des conseillers: {e}")
        conseillers = []
    
    # Récupérer les promotions
    promotions = []
    try:
        session.rollback()
        promotions = session.exec(select(Promotion)).all()
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des promotions: {e}")
        promotions = []
    
    # Récupérer les partenaires actifs
    partenaires = []
    try:
        session.rollback()
        partenaires = session.exec(select(Partenaire).where(Partenaire.actif == True)).all()
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des partenaires: {e}")
        partenaires = []
    
    # Récupérer les groupes actifs
    groupes = []
    try:
        session.rollback()
        groupes = session.exec(select(Groupe).where(Groupe.actif == True).order_by(Groupe.nom)).all()
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes: {e}")
        groupes = []

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

    # S'assurer que le search_path est défini avant le rendu du template
    # pour éviter les problèmes de lazy loading dans le template
    if cand and schema_name:
        try:
            session.execute(text(f"SET search_path TO {schema_name}, public"))
            # S'assurer que les documents sont déjà chargés pour éviter le lazy loading
            # Si les documents ne sont pas chargés, les charger maintenant
            if hasattr(cand, 'documents'):
                # Forcer le chargement des documents si nécessaire
                _ = cand.documents  # Cela déclenchera le lazy loading maintenant avec le bon search_path
        except Exception as e:
            logging.warning(f"Erreur lors de la configuration du search_path avant rendu: {e}")

    return templates.TemplateResponse(
        "pages/programme/inscription.html",
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
            "groupes": groupes,
            "type_promotion_enum": TypePromotion,
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
@router.post("/create-from-pre", name="create_inscription_from_preinscription")
def create_from_pre(
    request: Request,
    pre_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Crée une inscription depuis une préinscription"""
    try:
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        from ..services import InscriptionService
        
        # Utiliser le service pour créer l'inscription
        inscription = InscriptionService.create_from_preinscription(session, pre_id)
        
        # Récupérer le programme pour la redirection
        prog = session.exec(select(Programme).where(Programme.code == programme)).first()
        
        return RedirectResponse(
            url=f"{request.url_for('form_inscriptions_display')}?programme={prog.code if prog else programme}&pre_id={pre_id}", 
            status_code=303
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de l'inscription: {str(e)}")


# Mise à jour infos candidat/entreprise
@router.post("/update-infos", name="update_infos_inscription")
async def update_infos(
    request: Request,
    pre_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
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
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    import base64
    import json
    from urllib.parse import urlencode
    from fastapi import status
    
    try:
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Obtenir les modèles spécifiques au schéma
        PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
        CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
        EntrepriseSchema = schema_routing_service.get_model_for_schema(Entreprise, schema_name)
        DocumentSchema = schema_routing_service.get_model_for_schema(Document, schema_name)
        
        pre = session.get(PreinscriptionSchema, pre_id)
        if not pre:
            prog = session.get(Programme, pre.programme_id) if pre else None
            redirect_url = request.url_for("form_inscriptions_display")
            if prog:
                redirect_url = f"{redirect_url}?programme={prog.code}&pre_id={pre_id}"
            params = {
                "save_success": "false",
                "message": "Préinscription introuvable",
                "error_type": "NotFound"
            }
            return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)
        
        cand = session.get(CandidatSchema, pre.candidat_id)
        # Charger les documents du candidat avec le bon schéma
        if cand:
            cand.documents = []
            try:
                # Vérifier directement dans le schéma spécifique
                if _table_exists_in_schema(session, "document", schema_name):
                    # Utiliser une requête SQL directe avec le schéma explicite
                    documents_query = text(f"""
                        SELECT * FROM {schema_name}.document 
                        WHERE candidat_id = :candidat_id
                        ORDER BY depose_le DESC
                    """)
                    doc_results = session.execute(documents_query.bindparams(candidat_id=cand.id)).all()
                    for doc_row in doc_results:
                        doc_dict = dict(doc_row._mapping)
                        # Utiliser merge() pour éviter les conflits avec les objets existants
                        doc = DocumentSchema(**doc_dict)
                        merged_doc = session.merge(doc)
                        cand.documents.append(merged_doc)
                    logging.info(f"📋 [INSCRIPTION] Documents chargés pour candidat {cand.id}: {len(cand.documents)} documents")
            except Exception as e:
                logging.warning(f"Erreur lors de la récupération des documents: {e}")
                cand.documents = []
                # Rollback pour nettoyer la session en cas d'erreur
                try:
                    session.rollback()
                except Exception:
                    pass
        ent = None
        if _table_exists_in_schema(session, "entreprise", schema_name):
            try:
                ent = session.exec(select(EntrepriseSchema).where(EntrepriseSchema.candidat_id==cand.id)).first()
            except Exception as e:
                print(f"⚠️ [WARNING] Erreur lors de la récupération de l'entreprise: {e}")
                ent = None
        
        if not ent:
            ent = EntrepriseSchema(candidat_id=cand.id)
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
                from ..services.uploads import validate_upload
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
                    try:
                        # Essayer de supprimer depuis media/ d'abord
                        media_path = path_config.MEDIA_DIR / cand.photo_profil
                        if media_path.exists():
                            media_path.unlink()
                        else:
                            # Sinon essayer depuis uploads/ (ancien format)
                            FileUploadService.delete_file(cand.photo_profil)
                        if settings.DEBUG:
                            print(f"🗑️ [DEBUG] Ancienne photo supprimée: {cand.photo_profil}")
                    except Exception as e:
                        if settings.DEBUG:
                            print(f"⚠️ [DEBUG] Erreur lors de la suppression de l'ancienne photo: {e}")
                
                # Utiliser FileUploadService.save_media_file pour sauvegarder dans media/profile_image/{programme}/
                file_info = await FileUploadService.save_media_file(
                    photo_profil,
                    media_type="profile_image",  # Sauvegarde dans media/profile_image/
                    programme_code=programme,  # Isoler par programme : media/profile_image/{programme}/id_{pre.id}/
                    subfolder_id=pre.id  # Crée media/profile_image/{programme}/id_{pre.id}/
                )
                
                # Mettre à jour le candidat avec le chemin relatif
                cand.photo_profil = file_info["relative_path"]
                
                if settings.DEBUG:
                    print(f"📸 [DEBUG] Nouvelle photo sauvegardée: {file_info['relative_path']}")
                    
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
        from ..services.audit import log_activity
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
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={prog.code}&pre_id={pre.id}"
        
        # Message de succès
        params = {
            "save_success": "true",
            "message": "Les modifications ont été enregistrées avec succès"
        }
        
        return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)
    
    except HTTPException as http_exc:
        # Gérer les erreurs HTTP
        logging.error(f"Erreur HTTP lors de la mise à jour: {http_exc.status_code} - {http_exc.detail}")
        
        try:
            session.rollback()
        except:
            pass
        
        prog = session.get(Programme, pre.programme_id) if 'pre' in locals() and pre else None
        redirect_url = request.url_for("form_inscriptions_display")
        if prog:
            redirect_url = f"{redirect_url}?programme={prog.code}&pre_id={pre_id if 'pre_id' in locals() else ''}"
        else:
            redirect_url = f"{redirect_url}?programme={programme}&pre_id={pre_id if 'pre_id' in locals() else ''}"
        
        error_message = str(http_exc.detail) if http_exc.detail else f"Erreur HTTP {http_exc.status_code}"
        params = {
            "save_success": "false",
            "message": error_message,
            "error_type": "HTTPException"
        }
        
        return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        # Gérer les autres erreurs
        import traceback
        error_traceback = traceback.format_exc()
        error_type = type(e).__name__
        logging.error(f"Erreur lors de la mise à jour ({error_type}): {e}")
        logging.error(error_traceback)
        
        try:
            session.rollback()
        except:
            pass
        
        prog = session.get(Programme, pre.programme_id) if 'pre' in locals() and pre else None
        redirect_url = request.url_for("form_inscriptions_display")
        if prog:
            redirect_url = f"{redirect_url}?programme={prog.code}&pre_id={pre_id if 'pre_id' in locals() else ''}"
        else:
            redirect_url = f"{redirect_url}?programme={programme}&pre_id={pre_id if 'pre_id' in locals() else ''}"
        
        error_message = f"Erreur lors de l'enregistrement: {str(e)}"
        if error_type != "Exception":
            error_message = f"[{error_type}] {error_message}"
        
        params = {
            "save_success": "false",
            "message": error_message,
            "error_type": error_type
        }
        
        return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)


# Recalcul eligibilité
@router.post("/eligibilite/recalc", name="eligibilite_recalc")
async def elig_recalc(
    request: Request,
    pre_id: int = Form(...),
    programme: str = Form(...),
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    import base64
    import json
    from urllib.parse import urlencode
    from fastapi import status
    
    try:
        # Récupérer le schéma depuis request.state (injecté par le middleware)
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', None)
        if schema_name:
            schema_name = schema_name.lower()
        else:
            schema_name = "public"
        
        logging.info(f"🔄 [RECALC] Début recalcul éligibilité pour préinscription {pre_id} dans le schéma {schema_name}")
        
        # Configurer le schéma dans le service de routage
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Utiliser les modèles configurés pour le schéma
        PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
        CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
        EntrepriseSchema = schema_routing_service.get_model_for_schema(Entreprise, schema_name)
        EligibiliteSchema = schema_routing_service.get_model_for_schema(Eligibilite, schema_name)
        
        # Récupérer la préinscription avec le modèle du schéma
        pre = session.get(PreinscriptionSchema, pre_id)
        if not pre:
            logging.error(f"❌ [RECALC] Préinscription {pre_id} introuvable dans le schéma {schema_name}")
            raise HTTPException(status_code=404, detail="Préinscription introuvable")
        
        # Récupérer le programme depuis la table public
        prog = session.get(Programme, pre.programme_id)
        if not prog:
            logging.error(f"❌ [RECALC] Programme {pre.programme_id} introuvable")
            raise HTTPException(status_code=404, detail="Programme introuvable")
        
        # Récupérer le candidat avec le modèle du schéma
        cand = session.get(CandidatSchema, pre.candidat_id)
        if not cand:
            logging.error(f"❌ [RECALC] Candidat {pre.candidat_id} introuvable dans le schéma {schema_name}")
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        # Récupérer l'entreprise avec le modèle du schéma
        ent = None
        if _table_exists_in_schema(session, "entreprise", schema_name):
            try:
                ent = session.exec(select(EntrepriseSchema).where(EntrepriseSchema.candidat_id == cand.id)).first()
            except Exception as e:
                logging.warning(f"⚠️ [RECALC] Erreur lors de la récupération de l'entreprise: {e}")
                ent = None
        
        if not ent:
            logging.warning(f"⚠️ [RECALC] Entreprise pour candidat {cand.id} introuvable - utilisation des données de la préinscription")
            # Si pas d'entreprise, utiliser les données de la préinscription
            adresse_entreprise = None
            chiffre_affaires = pre.chiffre_affaires
            date_creation_entreprise = pre.date_creation_entreprise
        else:
            adresse_entreprise = ent.adresse
            chiffre_affaires = ent.chiffre_affaires if ent.chiffre_affaires else pre.chiffre_affaires
            date_creation_entreprise = ent.date_creation if ent.date_creation else pre.date_creation_entreprise
        
        # Calculer l'ancienneté
        anciennete = entreprise_age_annees(date_creation_entreprise)
        if anciennete is not None:
            anciennete = int(anciennete)
        
        # Convertir le chiffre d'affaires en string si nécessaire
        ca_string = str(chiffre_affaires) if chiffre_affaires else None
        
        logging.info(f"📊 [RECALC] Données - CA: {ca_string}, Ancienneté: {anciennete} ans, Adresse entreprise: {adresse_entreprise}")
        
        # Calculer l'éligibilité avec la nouvelle signature (sauvegarde automatique)
        verdict, details = await evaluate_eligibilite(
            adresse_perso=cand.adresse_personnelle,
            adresse_entreprise=adresse_entreprise,
            chiffre_affaires=ca_string,
            anciennete_annees=anciennete,
            programme_id=prog.id,
            session=session,
            request=request,
            preinscription_id=pre_id,
            schema_name=schema_name
        )
        
        logging.info(f"✅ [RECALC] Évaluation terminée - Verdict: {verdict}, Details: {details}")
        
        # L'éligibilité est maintenant enregistrée automatiquement par evaluate_eligibilite
        # Plus besoin d'insertion manuelle
        
        session.commit()
        
        logging.info(f"🎉 [RECALC] Recalcul terminé avec succès")
        
        # Redirection avec message de succès
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={prog.code}&pre_id={pre.id}"
        
        params = {
            "elig_recalc_success": "true",
            "message": "L'éligibilité a été recalculée avec succès"
        }
        
        return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)
        
    except HTTPException as http_exc:
        logging.error(f"❌ [RECALC] Erreur HTTP: {http_exc.status_code} - {http_exc.detail}")
        try:
            session.rollback()
        except:
            pass
        
        prog_code = programme or getattr(request.state, 'current_programme', None) or "ACD"
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={prog_code}&pre_id={pre_id if 'pre_id' in locals() else ''}"
        
        error_message = str(http_exc.detail) if http_exc.detail else f"Erreur HTTP {http_exc.status_code}"
        params = {
            "elig_recalc_success": "false",
            "message": error_message,
            "error_type": "HTTPException"
        }
        
        return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_type = type(e).__name__
        logging.error(f"❌ [RECALC] Erreur lors du recalcul ({error_type}): {e}")
        logging.error(error_traceback)
        
        try:
            session.rollback()
        except:
            pass
        
        prog_code = programme or getattr(request.state, 'current_programme', None) or "ACD"
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={prog_code}&pre_id={pre_id if 'pre_id' in locals() else ''}"
        
        error_message = f"Erreur lors du recalcul: {str(e)}"
        if error_type != "Exception":
            error_message = f"[{error_type}] {error_message}"
        
        params = {
            "elig_recalc_success": "false",
            "message": error_message,
            "error_type": error_type
        }
        
        return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)


# Ajouter un document
@router.post("/add-document", name="add_document_inscription")
async def add_document(
    request: Request,
    candidat_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
    type_document: str = Form(...),
    document_file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    try:
        print(f"📄 [DOC] Ajout document pour candidat {candidat_id}")
        
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Obtenir les modèles spécifiques au schéma
        CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
        DocumentSchema = schema_routing_service.get_model_for_schema(Document, schema_name)
        PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
        
        # Vérifier que le candidat existe
        candidat = session.get(CandidatSchema, candidat_id)
        if not candidat:
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        # Valider le fichier
        if not document_file.filename:
            raise HTTPException(status_code=400, detail="Aucun fichier sélectionné")
        
        # Utiliser FileUploadService pour sauvegarder le fichier avec isolation par programme
        # FileUploadService valide automatiquement la taille et l'extension
        file_info = await FileUploadService.save_file(
            document_file,
            "document",  # resource_type (utiliser "document" au lieu de "files" pour cohérence)
            "Preinscrits",  # folder_name
            programme_code=programme,  # Isoler par programme : uploads/Preinscrits/document/{programme}/id_{candidat_id}/
            subfolder_id=candidat_id  # Utiliser candidat_id comme subfolder_id
        )
        
        print(f"📄 [DOC] Fichier sauvegardé: {file_info['relative_path']}")
        
        # Créer l'enregistrement en base avec le modèle spécifique au schéma
        from ..models.enums import TypeDocument
        
        doc = DocumentSchema(
            candidat_id=candidat_id,
            nom_fichier=document_file.filename,
            chemin_fichier=file_info["relative_path"],
            taille_octets=file_info["size_bytes"],  # Corriger: utiliser size_bytes au lieu de size
            type_document=TypeDocument(type_document) if type_document in [e.value for e in TypeDocument] else TypeDocument.AUTRE,
            titre=description,  # Utiliser titre au lieu de description (le modèle Document n'a pas de champ description)
            mimetype=document_file.content_type,
            depose_par_id=current_user.id if current_user else None,
            depose_le=datetime.now(timezone.utc)
        )
        
        session.add(doc)
        session.commit()
        
        print(f"✅ [DOC] Document ajouté avec succès: {file_info['relative_path']}")
        
        # Retourner une réponse JSON avec message de succès
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Document ajouté avec succès",
                "document_id": doc.id,
                "document_name": document_file.filename
            }
        )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [DOC] Erreur lors de l'ajout: {e}")
        session.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erreur lors de l'ajout du document: {str(e)}"
            }
        )


# Supprimer un document
@router.post("/delete-document", name="delete_document_inscription")
def delete_document(
    request: Request,
    document_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    try:
        print(f"🗑️ [DOC] Suppression document {document_id}")
        
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Obtenir les modèles spécifiques au schéma
        DocumentSchema = schema_routing_service.get_model_for_schema(Document, schema_name)
        PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
        
        # Récupérer le document
        doc = session.get(DocumentSchema, document_id)
        if not doc:
            return {"success": False, "error": "Document introuvable"}
        
        # Supprimer le fichier physique via FileUploadService
        if doc.chemin_fichier:
            try:
                FileUploadService.delete_file(doc.chemin_fichier)
                print(f"🗑️ [DOC] Fichier supprimé: {doc.chemin_fichier}")
            except Exception as e:
                print(f"⚠️ [DOC] Erreur lors de la suppression du fichier: {e}")
        
        # Supprimer l'enregistrement en base
        candidat_id = doc.candidat_id
        session.delete(doc)
        session.commit()
        
        print(f"✅ [DOC] Document supprimé avec succès")
        
        # Retourner une réponse JSON avec message de succès
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Document supprimé avec succès",
                "document_id": document_id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [DOC] Erreur lors de la suppression: {e}")
        session.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erreur lors de la suppression du document: {str(e)}"
            }
        )


# Avancement d'étape
@router.post("/etape/advance", name="etape_advance_inscription")
def etape_advance(
    request: Request,
    avancement_id: int = Form(...),
    statut: str = Form(...),  # A_FAIRE | EN_COURS | TERMINE
    programme: str = Form(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    # Récupérer le schéma du programme
    schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
    schema_routing_service.set_schema(schema_name)
    
    # Configurer le search_path pour utiliser le schéma du programme
    session.execute(text(f"SET search_path TO {schema_name}, public"))
    
    # Obtenir les modèles spécifiques au schéma
    AvancementEtapeSchema = schema_routing_service.get_model_for_schema(AvancementEtape, schema_name)
    InscriptionSchema = schema_routing_service.get_model_for_schema(Inscription, schema_name)
    PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
    
    av = session.get(AvancementEtapeSchema, avancement_id)
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
    ins = session.get(InscriptionSchema, av.inscription_id)
    prog = session.exec(select(Programme).where(Programme.code == programme)).first()
    pre = session.exec(select(PreinscriptionSchema).where(PreinscriptionSchema.programme_id==prog.id, PreinscriptionSchema.candidat_id==ins.candidat_id)).first()
    return RedirectResponse(url=f"{request.url_for('form_inscriptions_display')}?programme={prog.code if prog else programme}&pre_id={pre.id if pre else ''}", status_code=303)


# --------- GESTION DES DÉCISIONS DU JURY ---------
@router.post("/jury/decision", name="create_jury_decision_inscription")
def create_jury_decision(
    request: Request,
    candidat_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
    jury_id: Optional[int] = Form(None),
    decision: str = Form(...),
    commentaires: Optional[str] = Form(None),
    conseiller_id: Optional[str] = Form(None), # Changé de Optional[int] à Optional[str]
    groupe_id: Optional[str] = Form(None),
    promotion_id: Optional[str] = Form(None),
    partenaire_id: Optional[str] = Form(None),
    envoyer_mail_candidat: bool = Form(False),
    envoyer_mail_conseiller: bool = Form(False),
    envoyer_mail_partenaire: bool = Form(False),
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Créer une décision du jury"""
    
    # Récupérer le schéma du programme
    schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
    schema_routing_service.set_schema(schema_name)
    
    # Configurer le search_path pour utiliser le schéma du programme
    session.execute(text(f"SET search_path TO {schema_name}, public"))
    
    # Obtenir les modèles spécifiques au schéma
    CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
    DecisionJuryCandidatSchema = schema_routing_service.get_model_for_schema(DecisionJuryCandidat, schema_name)
    ReorientationCandidatSchema = schema_routing_service.get_model_for_schema(ReorientationCandidat, schema_name)
    
    print(f"📋 [JURY] Données reçues:")
    print(f"   - candidat_id: {candidat_id} (type: {type(candidat_id)})")
    print(f"   - jury_id: {jury_id} (type: {type(jury_id)})")
    print(f"   - decision: {decision} (type: {type(decision)})")
    print(f"   - commentaires: {commentaires} (type: {type(commentaires)})")
    print(f"   - conseiller_id: {conseiller_id} (type: {type(conseiller_id)})")
    print(f"   - promotion_id: {promotion_id} (type: {type(promotion_id)})")
    print(f"   - partenaire_id: {partenaire_id} (type: {type(partenaire_id)})")
    
    # Convertir les chaînes vides en None pour les IDs
    def safe_int_convert(value):
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value)
            except ValueError:
                return None
        return None
    
    promotion_id_int = safe_int_convert(promotion_id)
    partenaire_id_int = safe_int_convert(partenaire_id)
    conseiller_id_int = safe_int_convert(conseiller_id)
    groupe_id_int = safe_int_convert(groupe_id)
    
    # Vérifier que le groupe existe (si fourni)
    groupe = None
    if groupe_id_int:
        groupe = session.get(Groupe, groupe_id_int)
        if not groupe:
            print(f"⚠️ [JURY] Groupe introuvable: {groupe_id}")
            groupe_id_int = None
    
    print(f"📋 [JURY] IDs convertis:")
    print(f"   - promotion_id_int: {promotion_id_int}")
    print(f"   - partenaire_id_int: {partenaire_id_int}")
    print(f"   - conseiller_id_int: {conseiller_id_int}")
    print(f"   - groupe_id_int: {groupe_id_int}")
    
    # Vérifier que le candidat existe
    candidat = session.get(CandidatSchema, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Vérifier que le jury existe (si fourni)
    jury = None
    if jury_id:
        jury = session.get(Jury, jury_id)  # Jury est dans le schéma public
        if not jury:
            raise HTTPException(status_code=404, detail="Jury introuvable")
    
    # Vérifier qu'il n'y a pas déjà une décision pour ce candidat et ce jury
    existing = session.exec(
        select(DecisionJuryCandidatSchema).where(
            (DecisionJuryCandidatSchema.candidat_id == candidat_id) &
            (DecisionJuryCandidatSchema.jury_id == jury_id)
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Une décision existe déjà pour ce candidat et ce jury")
    
    # Créer la décision
    decision_obj = DecisionJuryCandidatSchema(
        candidat_id=candidat_id,
        jury_id=jury_id,
        decision=DecisionJury(decision),
        commentaires=commentaires,
        conseiller_id=conseiller_id_int if decision == DecisionJury.VALIDE.value else None,
        groupe_id=groupe_id_int if decision == DecisionJury.VALIDE.value else None,
        promotion_id=promotion_id_int if decision == DecisionJury.VALIDE.value else None,
        partenaire_id=partenaire_id_int if decision == DecisionJury.REORIENTE.value else None,
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
        reorientation = ReorientationCandidatSchema(
            candidat_id=candidat_id,
            partenaire_id=partenaire_id_int,
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
    from ..services.audit import log_activity
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
    PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
    prog = session.exec(select(Programme).where(Programme.code == programme)).first()
    pre = session.exec(select(PreinscriptionSchema).where(PreinscriptionSchema.candidat_id == candidat_id)).first()
    return RedirectResponse(url=f"{request.url_for('form_inscriptions_display')}?programme={prog.code if prog else programme}&pre_id={pre.id if pre else ''}&success=decision_created", status_code=303)


@router.post("/jury/decision/{decision_id}/delete", name="delete_jury_decision_inscription")
def delete_jury_decision(
    request: Request,
    decision_id: int,
    programme: str = Form(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Supprimer une décision du jury"""
    
    # Récupérer le schéma du programme
    schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
    schema_routing_service.set_schema(schema_name)
    
    # Configurer le search_path pour utiliser le schéma du programme
    session.execute(text(f"SET search_path TO {schema_name}, public"))
    
    # Obtenir les modèles spécifiques au schéma
    DecisionJuryCandidatSchema = schema_routing_service.get_model_for_schema(DecisionJuryCandidat, schema_name)
    CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
    ReorientationCandidatSchema = schema_routing_service.get_model_for_schema(ReorientationCandidat, schema_name)
    
    decision_obj = session.get(DecisionJuryCandidatSchema, decision_id)
    if not decision_obj:
        raise HTTPException(status_code=404, detail="Décision introuvable")
    
    candidat_id = decision_obj.candidat_id
    
    # Remettre le candidat en attente
    candidat = session.get(CandidatSchema, candidat_id)
    if candidat:
        candidat.statut = DecisionJury.EN_ATTENTE.value
    
    # Supprimer les réorientations associées
    reorientations = session.exec(
        select(ReorientationCandidatSchema).where(
            ReorientationCandidatSchema.decision_jury_id == decision_id
        )
    ).all()
    for reo in reorientations:
        session.delete(reo)
    
    session.delete(decision_obj)
    session.commit()
    
    # Log de l'activité
    from ..services.audit import log_activity
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
    PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
    prog = session.exec(select(Programme).where(Programme.code == programme)).first()
    pre = session.exec(select(PreinscriptionSchema).where(PreinscriptionSchema.candidat_id == candidat_id)).first()
    return RedirectResponse(url=f"{request.url_for('form_inscriptions_display')}?programme={prog.code if prog else programme}&pre_id={pre.id if pre else ''}&success=decision_deleted", status_code=303)


# --------- INTÉGRATION QPV ET SIRET ---------
@router.post("/qpv-check", name="check_qpv_candidate_inscription")
async def check_qpv_candidate(
    candidat_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
    adresse_personnelle: Optional[str] = Form(None),
    adresse_entreprise: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Vérifier le statut QPV pour un candidat en analysant son adresse personnelle et celle de l'entreprise"""
    
    # Récupérer le schéma depuis request.state (injecté par le middleware)
    schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', None)
    if schema_name:
        schema_name = schema_name.lower()
    else:
        schema_name = "public"
    
    # Configurer le schéma dans le service de routage
    schema_routing_service.set_schema(schema_name)
    
    # Configurer le search_path pour utiliser le schéma du programme
    session.execute(text(f"SET search_path TO {schema_name}, public"))
    
    # Utiliser les modèles configurés pour le schéma
    CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
    EntrepriseSchema = schema_routing_service.get_model_for_schema(Entreprise, schema_name)
    PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
    EligibiliteSchema = schema_routing_service.get_model_for_schema(Eligibilite, schema_name)
    
    candidat = session.get(CandidatSchema, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Récupérer les adresses depuis la base si non fournies
    if not adresse_personnelle or not adresse_entreprise:
        entreprise = None
        if _table_exists_in_schema(session, "entreprise", schema_name):
            try:
                entreprise = session.exec(select(EntrepriseSchema).where(EntrepriseSchema.candidat_id == candidat_id)).first()
            except Exception as e:
                print(f"⚠️ [WARNING] Erreur lors de la récupération de l'entreprise: {e}")
                entreprise = None
        
        # Adresse personnelle du candidat
        if not adresse_personnelle:
            adresse_personnelle = candidat.adresse_personnelle
        
        # Adresse de l'entreprise
        if not adresse_entreprise and entreprise:
            adresse_entreprise = entreprise.adresse
    
    # 🔍 VÉRIFICATION PRÉALABLE : Recherche existante ?
    preinscription = session.exec(
        select(PreinscriptionSchema).where(PreinscriptionSchema.candidat_id == candidat_id)
    ).first()
    
    if preinscription:
        eligibilite = session.exec(
            select(EligibiliteSchema).where(EligibiliteSchema.preinscription_id == preinscription.id)
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
            # Récupérer preinscription_id pour le stockage des fichiers
            preinscription_id_for_qpv = preinscription.id if preinscription else None
            qpv_personnelle = await verif_qpv(
                {"address": adresse_personnelle}, 
                request,
                programme_code=programme,
                subfolder_id=preinscription_id_for_qpv
            )
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
            # Récupérer preinscription_id pour le stockage des fichiers
            preinscription_id_for_qpv = preinscription.id if preinscription else None
            qpv_entreprise = await verif_qpv(
                {"address": adresse_entreprise}, 
                request,
                programme_code=programme,
                subfolder_id=preinscription_id_for_qpv
            )
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
    
    # Déterminer le statut QPV final et le nom QPV, ainsi que les URLs des fichiers
    qpv_found = False
    qpv_nom_final = "Aucun QPV"
    qpv_carte_url_final = None
    qpv_image_url_final = None
    
    for analyse in results["adresses_analysees"]:
        if "resultat" in analyse:
            nom_qp = analyse["resultat"].get("nom_qp", "")
            if nom_qp and nom_qp.startswith("QPV"):
                qpv_found = True
                qpv_nom_final = nom_qp  # Stocker le texte complet (ex: "QPV:Les Beaudottes")
                # Récupérer les URLs de la première adresse QPV trouvée
                qpv_carte_url_final = analyse["resultat"].get("carte", "")
                qpv_image_url_final = analyse["resultat"].get("image_url", "")
                results["statut_qpv_final"] = "QPV"
                break
    
    # Mettre à jour l'éligibilité du candidat
    if candidat:
        preinscription = session.exec(
            select(PreinscriptionSchema).where(PreinscriptionSchema.candidat_id == candidat_id)
        ).first()
        
        if preinscription:
            eligibilite = session.exec(
                select(EligibiliteSchema).where(EligibiliteSchema.preinscription_id == preinscription.id)
            ).first()
            
            if not eligibilite:
                eligibilite = EligibiliteSchema(preinscription_id=preinscription.id)
                session.add(eligibilite)
            
            import json
            import copy
            
            # Créer une copie légère de results sans les images base64 (les URLs sont déjà stockées séparément)
            results_light = copy.deepcopy(results)
            for analyse in results_light.get("adresses_analysees", []):
                if "resultat" in analyse:
                    # Retirer les images base64 volumineuses (encoded_image et image_encoded), garder seulement les URLs
                    resultat = analyse["resultat"]
                    if "encoded_image" in resultat:
                        del resultat["encoded_image"]
                    if "image_encoded" in resultat:
                        del resultat["image_encoded"]
                    # Garder seulement les informations essentielles (chemins relatifs uniquement)
                    resultat_clean = {
                        "address": resultat.get("address", ""),
                        "nom_qp": resultat.get("nom_qp", ""),
                        "distance_m": resultat.get("distance_m", ""),
                        "carte": resultat.get("carte", ""),  # Chemin relatif seulement (ex: /uploads/QPV/...)
                        "image_url": resultat.get("image_url", "")  # Chemin relatif seulement (ex: /media/qpv_map/...)
                    }
                    analyse["resultat"] = resultat_clean
            
            eligibilite.qpv_ok = qpv_nom_final  # Stocker le texte complet au lieu du booléen
            eligibilite.qpv_carte_url = qpv_carte_url_final  # URL de la carte HTML
            eligibilite.qpv_image_url = qpv_image_url_final  # URL de l'image PNG
            eligibilite.details_json = json.dumps(results_light)  # Sauvegarder results sans images base64
            session.add(eligibilite)
            session.commit()
            
            print(f"✅ [QPV] Éligibilité mise à jour - QPV: {qpv_nom_final}, Carte: {qpv_carte_url_final}, Image: {qpv_image_url_final}")
    
    # Log de l'activité
    from ..services.audit import log_activity
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


@router.post("/siret-check", name="check_siret_candidate_inscription")
async def check_siret_candidate(
    request: Request,
    candidat_id: int = Form(...),
    programme: str = Form(...),  # Ajout du paramètre programme
    numero_siret: str = Form(...),
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Vérifier les informations SIRET pour un candidat"""
    
    # Récupérer le schéma du programme
    schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
    schema_routing_service.set_schema(schema_name)
    
    # Configurer le search_path pour utiliser le schéma du programme
    session.execute(text(f"SET search_path TO {schema_name}, public"))
    
    # Obtenir les modèles spécifiques au schéma
    CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
    EntrepriseSchema = schema_routing_service.get_model_for_schema(Entreprise, schema_name)
    
    candidat = session.get(CandidatSchema, candidat_id)
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
            select(EntrepriseSchema).where(EntrepriseSchema.candidat_id == candidat_id)
        ).first()
        
        if not entreprise:
            entreprise = EntrepriseSchema(candidat_id=candidat_id)
            session.add(entreprise)
        
        if siret_info.get("entreprise_data"):
            data = siret_info["entreprise_data"]
            
            # Mettre à jour les champs de l'entreprise
            entreprise.siret = data.get("siege", {}).get("siret")
            entreprise.siren = data.get("siren")
            entreprise.raison_sociale = data.get("nom_entreprise")  # Utiliser raison_sociale au lieu de nom_entreprise
            entreprise.code_naf = data.get("code_naf")
            entreprise.date_creation = data.get("date_creation")
            
            # Mettre à jour l'adresse du siège
            siege = data.get("siege", {})
            entreprise.adresse = siege.get("adresse")
            entreprise.lat = siege.get("latitude")
            entreprise.lng = siege.get("longitude")
            
            session.add(entreprise)
            session.commit()
            
            print(f"✅ [SIRET] Informations entreprise mises à jour")
        
        # Log de l'activité
        from ..services.audit import log_activity
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


@router.get("/qpv-status/{candidat_id}", name="get_qpv_status_inscription")
def get_qpv_status(
    request: Request,
    candidat_id: int,
    programme: str = Query(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Récupérer le statut QPV actuel d'un candidat"""
    
    # Récupérer le schéma du programme
    schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
    schema_routing_service.set_schema(schema_name)
    
    # Configurer le search_path pour utiliser le schéma du programme
    session.execute(text(f"SET search_path TO {schema_name}, public"))
    
    # Obtenir les modèles spécifiques au schéma
    CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
    PreinscriptionSchema = schema_routing_service.get_model_for_schema(Preinscription, schema_name)
    EligibiliteSchema = schema_routing_service.get_model_for_schema(Eligibilite, schema_name)
    
    candidat = session.get(CandidatSchema, candidat_id)
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Récupérer l'éligibilité
    preinscription = session.exec(
        select(PreinscriptionSchema).where(PreinscriptionSchema.candidat_id == candidat_id)
    ).first()
    
    if not preinscription:
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    eligibilite = session.exec(
        select(EligibiliteSchema).where(EligibiliteSchema.preinscription_id == preinscription.id)
    ).first()
    
    if not eligibilite:
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    # Vérifier si qpv_ok contient "QPV" (peut être "QPV:nom" ou "Aucun QPV")
    qpv_status = "QPV" if eligibilite.qpv_ok and eligibilite.qpv_ok.startswith("QPV") else "NON_QPV"
    
    return {
        "statut_qpv": qpv_status,
        "details": eligibilite.details_json,
        "derniere_verification": eligibilite.calcule_le.isoformat() if eligibilite.calcule_le else None
    }


@router.post("/download-siret-document", name="download_siret_document_inscription")
async def download_siret_document(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Télécharge un document depuis l'API SIRET et l'ajoute aux documents du candidat"""
    try:
        data = await request.json()
        candidat_id = data.get("candidat_id")
        programme = data.get("programme") or getattr(request.state, 'current_programme', 'acd')  # Récupérer depuis JSON ou request.state
        token = data.get("token")
        nom_fichier = data.get("nom_fichier", "document_siret.pdf")
        type_document = data.get("type_document", "AUTRE")
        
        if not candidat_id or not token:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Candidat ID et token requis"}
            )
        
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Obtenir les modèles spécifiques au schéma
        CandidatSchema = schema_routing_service.get_model_for_schema(Candidat, schema_name)
        DocumentSchema = schema_routing_service.get_model_for_schema(Document, schema_name)
        
        # Vérifier que le token n'est pas vide
        if not token.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Token de téléchargement invalide"}
            )
        
        # Vérifier que le candidat existe
        candidat = session.get(CandidatSchema, candidat_id)
        if not candidat:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Candidat non trouvé"}
            )
        
        # Vérifier que l'API key Pappers est configurée
        if not settings.PAPPERS_API_KEY:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "API key Pappers non configurée"}
            )
        
        # Télécharger le document depuis l'API Pappers
        import requests
        pappers_url = f"https://api.pappers.fr/v2/document/telechargement?token={token}&api_token={settings.PAPPERS_API_KEY}"
        
        print(f"📥 [SIRET DOC] Téléchargement depuis: {pappers_url}")
        print(f"🔑 [SIRET DOC] Token utilisé: {token[:20]}...")
        print(f"🔑 [SIRET DOC] API key utilisée: {settings.PAPPERS_API_KEY[:10]}...")
        
        response = requests.get(pappers_url, timeout=30)
        print(f"📊 [SIRET DOC] Status code: {response.status_code}")
        print(f"📊 [SIRET DOC] Headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ [SIRET DOC] Erreur téléchargement: {response.status_code}")
            print(f"❌ [SIRET DOC] Réponse: {response.text[:200]}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"Erreur lors du téléchargement du document (HTTP {response.status_code})"}
            )
        
        # Utiliser FileUploadService pour sauvegarder le fichier avec isolation par programme
        from fastapi import UploadFile
        from io import BytesIO
        
        file_content = response.content
        file_upload = UploadFile(
            filename=nom_fichier,
            file=BytesIO(file_content)
        )
        
        file_info = await FileUploadService.save_file(
            file_upload,
            "document",  # resource_type
            "Preinscrits",  # folder_name
            programme_code=programme,  # Isoler par programme
            subfolder_id=candidat_id  # Utiliser candidat_id comme subfolder_id
        )
        
        print(f"✅ [SIRET DOC] Fichier sauvegardé: {file_info['relative_path']}")
        
        # Créer l'enregistrement en base de données avec le modèle spécifique au schéma
        from ..models.enums import TypeDocument
        
        document = DocumentSchema(
            candidat_id=candidat_id,
            nom_fichier=nom_fichier,
            chemin_fichier=file_info["relative_path"],
            type_document=TypeDocument(type_document) if type_document in [e.value for e in TypeDocument] else TypeDocument.AUTRE,
            taille_octets=file_info["size_bytes"],
            depose_par_id=current_user.id if current_user else None,
            depose_le=datetime.now(timezone.utc)
        )
        
        session.add(document)
        session.commit()
        session.refresh(document)
        
        print(f"✅ [SIRET DOC] Document enregistré en base: ID {document.id}")
        print(f"📋 [SIRET DOC] Détails du document:")
        print(f"   - Candidat ID: {document.candidat_id}")
        print(f"   - Nom fichier: {document.nom_fichier}")
        print(f"   - Type document: {document.type_document}")
        print(f"   - Chemin: {document.chemin_fichier}")
        print(f"   - Taille: {document.taille_octets} bytes")
        
        # Vérification immédiate que le document existe en base
        verification = session.exec(select(DocumentSchema).where(DocumentSchema.id == document.id)).first()
        if verification:
            print(f"✅ [SIRET DOC] Vérification OK: Document {document.id} trouvé en base")
        else:
            print(f"❌ [SIRET DOC] ERREUR: Document {document.id} non trouvé en base")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True, 
                "message": f"Document '{nom_fichier}' téléchargé et ajouté avec succès",
                "document_id": document.id,
                "filename": file_info["saved_filename"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [SIRET DOC] Erreur: {str(e)}")
        session.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur lors du traitement: {str(e)}"}
        )

# Routes pour servir les fichiers documents
@router.get("/document/{document_id}/view", name="inscriptions_document_view")
def view_document(
    request: Request,
    document_id: int,
    programme: str = Query(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Afficher un document dans le navigateur."""
    try:
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Obtenir le modèle spécifique au schéma
        DocumentSchema = schema_routing_service.get_model_for_schema(Document, schema_name)
        
        doc = session.get(DocumentSchema, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable")
        
        # Utiliser FileUploadService pour servir le fichier
        try:
            return FileUploadService.serve_file(doc.chemin_fichier)
        except HTTPException:
            # Fallback vers l'ancien système si FileUploadService échoue
            from pathlib import Path
            file_path = path_config.UPLOAD_DIR / doc.chemin_fichier
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Fichier introuvable")
            
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"
            
            from fastapi.responses import Response
            with open(file_path, "rb") as f:
                content = f.read()
            
            return Response(
                content=content,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f"inline; filename={doc.nom_fichier}",
                    "Content-Length": str(len(content))
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [DOC] Erreur lors de l'affichage: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du document: {str(e)}")


@router.get("/document/{document_id}/download", name="inscriptions_document_download")
def download_document(
    request: Request,
    document_id: int,
    programme: str = Query(...),  # Ajout du paramètre programme
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Télécharger un document."""
    try:
        # Récupérer le schéma du programme
        schema_name = programme.lower() if programme else getattr(request.state, 'current_programme', 'acd').lower()
        schema_routing_service.set_schema(schema_name)
        
        # Configurer le search_path pour utiliser le schéma du programme
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        # Obtenir le modèle spécifique au schéma
        DocumentSchema = schema_routing_service.get_model_for_schema(Document, schema_name)
        
        doc = session.get(DocumentSchema, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable")
        
        # Utiliser FileUploadService pour servir le fichier
        try:
            return FileUploadService.serve_file(doc.chemin_fichier)
        except HTTPException:
            # Fallback vers l'ancien système si FileUploadService échoue
            from fastapi.responses import FileResponse
            file_path = path_config.get_physical_path("files", doc.chemin_fichier)
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Fichier introuvable")
            
            return FileResponse(
                path=str(file_path),
                filename=doc.nom_fichier,
                media_type="application/octet-stream"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [DOC] Erreur lors du téléchargement: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du téléchargement du document: {str(e)}")


# ============================================================================
# ROUTES QPV ET SIRET (fusionnées depuis route_qpv.py et route_siret_pappers.py)
# ============================================================================

@router.post("/inscriptions/qpv-check", name="check_qpv_route", response_model=QPVResponse)
async def check_qpv_route(address: Adresse, request: Request):
    """
    Vérifier le statut QPV d'une adresse
    
    Args:
        address: Objet Adresse contenant l'adresse à vérifier
        request: Requête FastAPI pour récupérer l'URL de base
        
    Returns:
        dict: Résultat de la vérification QPV avec cartes et images
    """
    import time
    start_time = time.time()
    data = address.model_dump()

    print("✅ [ROUTE QPV] Adresse validée:", address)

    # Vérification des données d'entrée
    if not data.get("address") or not data["address"].strip():
        return {
            "address": "Adresse vide",
            "nom_qp": "Aucun QPV",
            "distance_m": "N/A",
            "carte": "",
            "image_url": "",
            "image_encoded": ""
        }
    
    # Validation basique du format d'adresse
    adresse = data["address"].strip()
    if len(adresse) < 5 or adresse.isdigit():
        return {
            "address": "Format d'adresse invalide",
            "nom_qp": "Aucun QPV", 
            "distance_m": "N/A",
            "carte": "",
            "image_url": "",
            "image_encoded": ""
        }

    try:
        # Appel du service de vérification QPV
        result = await verif_qpv(data, request)
        
        duration = round(time.time() - start_time, 2)
        print(f"✅ [ROUTE QPV] Vérification terminée en {duration}s")
        
        return result
        
    except Exception as e:
        print(f"❌ [ROUTE QPV] Erreur lors de la vérification: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la vérification QPV: {str(e)}"
        )


@router.post("/inscriptions/siret-check", name="check_siret_route")
async def check_siret_route(siret_request: SiretRequest, request: Request):
    """
    Vérifier les informations d'une entreprise via son SIRET/SIREN
    
    Args:
        siret_request: Objet SiretRequest contenant le numéro SIRET/SIREN
        request: Requête FastAPI pour récupérer l'URL de base
        
    Returns:
        dict: Informations de l'entreprise avec données CSV
    """
    import time
    print(f"🚀 [ROUTE SIRET] Début du traitement")
    print(f"📝 [ROUTE SIRET] SIRET reçu: {siret_request.numero_siret}")
    
    start_time = time.time()
    data = siret_request.model_dump()
    
    # Validation du format SIRET/SIREN
    numero_siret = data.get("numero_siret", "").strip()
    print(f"🔍 [ROUTE SIRET] Validation format: {numero_siret}")
    
    if not numero_siret or not numero_siret.isdigit():
        print("❌ [ROUTE SIRET] Format SIRET invalide")
        raise HTTPException(
            status_code=400,
            detail="Le numéro SIRET/SIREN doit contenir uniquement des chiffres"
        )
    
    if len(numero_siret) not in [9, 14]:
        print("❌ [ROUTE SIRET] Longueur SIRET invalide")
        raise HTTPException(
            status_code=400,
            detail="Le numéro doit faire 9 chiffres (SIREN) ou 14 chiffres (SIRET)"
        )
    
    # Extraction du SIREN (9 premiers chiffres)
    siren = numero_siret[:9]
    print(f"🔢 [ROUTE SIRET] SIREN extrait: {siren}")

    try:
        # Appel du service Pappers
        result = await get_entreprise_process(siren, request)
        
        duration = round(time.time() - start_time, 2)
        print(f"✅ [ROUTE SIRET] Traitement terminé en {duration}s")
        
        return result
        
    except HTTPException:
        # Re-lever les HTTPException du service
        raise
    except Exception as e:
        print(f"❌ [ROUTE SIRET] Erreur inattendue: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la vérification SIRET: {str(e)}"
        )
