# app/routers/inscriptions.py
from __future__ import annotations

import os
import logging
import secrets
import string
from datetime import date as _date, datetime, timezone
from typing import Optional, Literal

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
    safe_count_query,
    get_schema_from_request,
    table_exists_anywhere
)
from ..services.file_upload_service import FileUploadService
from ..templates import templates

from ..models.base import (
    Programme, Candidat, Entreprise, Preinscription, Eligibilite,
    EtapePipeline, AvancementEtape, StatutEtape,
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
from ..services.audit import log_activity
from .admin import admin_required, configure_schema

logger = logging.getLogger("app.inscriptions")

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
        result = session.exec(check_query.bindparams(schema_name=schema_name, table_name=table_name))
        first_row = result.first()
        return first_row[0] if first_row else False
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


# ============================================================================
# HELPERS POUR inscriptions_ui
# ============================================================================

def _generate_temp_password(length: int = 12) -> str:
    """Génère un mot de passe temporaire sécurisé"""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def _create_user_for_candidat(session: Session, candidat_id: int, schema_name: str) -> Optional[User]:
    """Crée un compte User pour un candidat validé"""
    try:
        # Récupérer les informations du candidat
        candidat_query = text(f"""
            SELECT email, nom, prenom, partenaire_bpi
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        
        if not candidat_result:
            logging.warning(f"❌ [CREATE_USER_CANDIDAT] Candidat {candidat_id} non trouvé")
            return None
        
        email = candidat_result.email if hasattr(candidat_result, 'email') else candidat_result[0]
        nom = candidat_result.nom if hasattr(candidat_result, 'nom') else candidat_result[1]
        prenom = candidat_result.prenom if hasattr(candidat_result, 'prenom') else candidat_result[2]
        partenaire_bpi = candidat_result.partenaire_bpi if hasattr(candidat_result, 'partenaire_bpi') else (candidat_result[3] if len(candidat_result) > 3 else None)
        
        if not email:
            logging.warning(f"❌ [CREATE_USER_CANDIDAT] Candidat {candidat_id} n'a pas d'email")
            return None
        
        # Vérifier si un compte existe déjà avec cet email
        existing_user_query = text("SELECT id, actif FROM public.\"user\" WHERE email = :email")
        existing_user = session.exec(existing_user_query.bindparams(email=email)).first()
        
        if existing_user:
            user_id = existing_user.id if hasattr(existing_user, 'id') else existing_user[0]
            is_active = existing_user.actif if hasattr(existing_user, 'actif') else existing_user[1]
            
            # Si le compte existe mais est désactivé, le réactiver et générer un nouveau mot de passe
            if not is_active:
                temp_password = _generate_temp_password()
                from ..core.security import get_password_hash
                password_hash = get_password_hash(temp_password)
                
                update_user_query = text("""
                    UPDATE public."user"
                    SET actif = true,
                        mot_de_passe_hash = :password_hash,
                        position = :position,
                        partenaire_bpi = :partenaire_bpi
                    WHERE id = :user_id
                """)
                session.exec(update_user_query.bindparams(
                    password_hash=password_hash,
                    position="Candidat",
                    partenaire_bpi=partenaire_bpi,
                    user_id=user_id
                ))
                logging.info(f"✅ [CREATE_USER_CANDIDAT] Compte User réactivé pour candidat {candidat_id} (email: {email})")
                return session.get(User, user_id)
            else:
                logging.info(f"ℹ️ [CREATE_USER_CANDIDAT] Compte User existe déjà et est actif pour candidat {candidat_id} (email: {email})")
                return session.get(User, user_id)
        
        # Créer un nouveau compte User
        nom_complet = f"{prenom} {nom}".strip()
        temp_password = _generate_temp_password()
        from ..core.security import get_password_hash
        from ..models.enums import UserRole, TypeUtilisateur
        
        password_hash = get_password_hash(temp_password)
        
        insert_user_query = text("""
            INSERT INTO public."user"
            (email, nom_complet, mot_de_passe_hash, role, type_utilisateur, actif, position, partenaire_bpi, cree_le)
            VALUES (:email, :nom_complet, :password_hash, :role, :type_utilisateur, true, :position, :partenaire_bpi, :cree_le)
            RETURNING id
        """)
        from datetime import datetime as _dt
        now = _dt.utcnow()
        
        user_result = session.exec(insert_user_query.bindparams(
            email=email,
            nom_complet=nom_complet,
            password_hash=password_hash,
            role=UserRole.CANDIDAT.value,
            type_utilisateur=TypeUtilisateur.EXTERNE.value,
            position="Candidat",
            partenaire_bpi=partenaire_bpi,
            cree_le=now
        )).first()
        
        user_id = user_result.id if hasattr(user_result, 'id') else user_result[0]
        logging.info(f"✅ [CREATE_USER_CANDIDAT] Compte User créé pour candidat {candidat_id} (email: {email}, user_id: {user_id})")
        
        return session.get(User, user_id)
        
    except Exception as e:
        logging.error(f"❌ [CREATE_USER_CANDIDAT] Erreur lors de la création du compte User pour candidat {candidat_id}: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return None

def _deactivate_user_for_candidat(session: Session, candidat_id: int, schema_name: str) -> bool:
    """Désactive le compte User d'un candidat invalidé"""
    try:
        # Récupérer l'email du candidat
        candidat_query = text(f"""
            SELECT email
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        
        if not candidat_result:
            logging.warning(f"❌ [DEACTIVATE_USER_CANDIDAT] Candidat {candidat_id} non trouvé")
            return False
        
        email = candidat_result.email if hasattr(candidat_result, 'email') else candidat_result[0]
        
        if not email:
            logging.warning(f"❌ [DEACTIVATE_USER_CANDIDAT] Candidat {candidat_id} n'a pas d'email")
            return False
        
        # Désactiver le compte User
        update_user_query = text("""
            UPDATE public."user"
            SET actif = false
            WHERE email = :email AND position = 'Candidat'
        """)
        result = session.exec(update_user_query.bindparams(email=email))
        session.commit()
        
        logging.info(f"✅ [DEACTIVATE_USER_CANDIDAT] Compte User désactivé pour candidat {candidat_id} (email: {email})")
        return True
        
    except Exception as e:
        logging.error(f"❌ [DEACTIVATE_USER_CANDIDAT] Erreur lors de la désactivation du compte User pour candidat {candidat_id}: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def _get_preinscriptions(session: Session, prog, schema_name: str, q: Optional[str] = None, current_user: Optional[User] = None):
    """Récupère la liste des préinscriptions pour un programme via requête SQL directe"""
    logging.info(f"🔵 [DEBUG _get_preinscriptions] Début - schema={schema_name}, prog.id={prog.id if prog else None}, q={q}")
    pre_rows = []
    
    if not (prog.id and table_exists_anywhere("preinscription", session, schema_name) and 
            table_exists_anywhere("candidat", session, schema_name)):
        logging.warning(f"🔵 [DEBUG _get_preinscriptions] ⚠ Tables manquantes ou prog.id=None")
        if settings.DEBUG:
            print(f"⚠️ [WARNING] Tables preinscription ou candidat manquantes - retour liste vide")
        return pre_rows
    
    try:
        logging.info(f"🔵 [DEBUG _get_preinscriptions] Configuration du search_path")
        # Configurer le search_path pour utiliser le schéma du programme
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        logging.info(f"🔵 [DEBUG _get_preinscriptions] ✓ Search_path configuré")
        
        # Construire la requête SQL directe avec JOINs
        logging.info(f"🔵 [DEBUG _get_preinscriptions] Construction de la requête SQL directe")
        
        # Vérifier si les tables entreprise et eligibilite existent
        has_entreprise = table_exists_anywhere("entreprise", session, schema_name)
        has_eligibilite = table_exists_anywhere("eligibilite", session, schema_name)
        
        # Construire la requête SELECT avec tous les champs explicitement listés pour éviter les conflits
        # Utiliser des alias pour chaque colonne pour éviter les conflits de noms
        preinscription_fields = """
            p.id as pre_id, p.programme_id as pre_programme_id, p.candidat_id as pre_candidat_id,
            p.source as pre_source, p.statut as pre_statut, p.cree_le as pre_cree_le,
            p.civilite as pre_civilite, p.nom as pre_nom, p.prenom as pre_prenom,
            p.date_naissance as pre_date_naissance, p.email as pre_email, p.telephone as pre_telephone,
            p.situation_socio as pre_situation_socio, p.numero_personnel as pre_numero_personnel,
            p.rue_personnel as pre_rue_personnel, p.code_postal_personnel as pre_code_postal_personnel,
            p.ville_personnel as pre_ville_personnel, p.numero_entreprise as pre_numero_entreprise,
            p.rue_entreprise as pre_rue_entreprise, p.code_postal_entreprise as pre_code_postal_entreprise,
            p.ville_entreprise as pre_ville_entreprise, p.date_creation_entreprise as pre_date_creation_entreprise,
            p.siret as pre_siret, p.chiffre_affaires as pre_chiffre_affaires,
            p.niveau_etudes as pre_niveau_etudes, p.secteur_activite as pre_secteur_activite
        """
        
        candidat_fields = """
            c.id as cand_id, c.civilite as cand_civilite, c.nom as cand_nom, c.prenom as cand_prenom,
            c.date_naissance as cand_date_naissance, c.email as cand_email, c.telephone as cand_telephone,
            c.adresse_personnelle as cand_adresse_personnelle, c.niveau_etudes as cand_niveau_etudes,
            c.secteur_activite as cand_secteur_activite, c.photo_profil as cand_photo_profil,
            c.lat as cand_lat, c.lng as cand_lng, c.handicap as cand_handicap,
            c.type_handicap as cand_type_handicap, c.besoins_accommodation as cand_besoins_accommodation,
            c.statut as cand_statut
        """
        
        if has_entreprise:
            entreprise_fields = """
                e.id as ent_id, e.candidat_id as ent_candidat_id, e.siret as ent_siret,
                e.siren as ent_siren, e.raison_sociale as ent_raison_sociale, e.code_naf as ent_code_naf,
                e.date_creation as ent_date_creation, e.adresse as ent_adresse, e.qpv as ent_qpv,
                e.chiffre_affaires as ent_chiffre_affaires, e.nombre_points_vente as ent_nombre_points_vente,
                e.specialite_culinaire as ent_specialite_culinaire, e.nom_concept as ent_nom_concept,
                e.lien_reseaux_sociaux as ent_lien_reseaux_sociaux, e.site_internet as ent_site_internet,
                e.territoire as ent_territoire, e.lat as ent_lat, e.lng as ent_lng
            """
            entreprise_join = f"LEFT JOIN {schema_name}.entreprise e ON e.candidat_id = c.id"
        else:
            entreprise_fields = """
                NULL as ent_id, NULL as ent_candidat_id, NULL as ent_siret, NULL as ent_siren,
                NULL as ent_raison_sociale, NULL as ent_code_naf, NULL as ent_date_creation,
                NULL as ent_adresse, NULL as ent_qpv, NULL as ent_chiffre_affaires,
                NULL as ent_nombre_points_vente, NULL as ent_specialite_culinaire, NULL as ent_nom_concept,
                NULL as ent_lien_reseaux_sociaux, NULL as ent_site_internet, NULL as ent_territoire,
                NULL as ent_lat, NULL as ent_lng
            """
            entreprise_join = ""
        
        if has_eligibilite:
            eligibilite_fields = """
                elig.id as elig_id, elig.preinscription_id as elig_preinscription_id,
                elig.ca_seuil_ok as elig_ca_seuil_ok, elig.ca_score as elig_ca_score,
                elig.qpv_ok as elig_qpv_ok, elig.anciennete_ok as elig_anciennete_ok,
                elig.anciennete_annees as elig_anciennete_annees, elig.verdict as elig_verdict,
                elig.details_json as elig_details_json, elig.qpv_carte_url as elig_qpv_carte_url,
                elig.qpv_image_url as elig_qpv_image_url, elig.calcule_le as elig_calcule_le
            """
            eligibilite_join = f"LEFT JOIN {schema_name}.eligibilite elig ON elig.preinscription_id = p.id"
        else:
            eligibilite_fields = """
                NULL as elig_id, NULL as elig_preinscription_id, NULL as elig_ca_seuil_ok,
                NULL as elig_ca_score, NULL as elig_qpv_ok, NULL as elig_anciennete_ok,
                NULL as elig_anciennete_annees, NULL as elig_verdict, NULL as elig_details_json,
                NULL as elig_qpv_carte_url, NULL as elig_qpv_image_url, NULL as elig_calcule_le
            """
            eligibilite_join = ""
        
        # Construire la clause WHERE
        where_conditions = ["p.programme_id = :programme_id"]
        params = {"programme_id": prog.id}
        
        if q:
            where_conditions.append("(c.nom ILIKE :search OR c.prenom ILIKE :search OR c.email ILIKE :search)")
            params["search"] = f"%{q}%"
            logging.info(f"🔵 [DEBUG _get_preinscriptions] Filtre de recherche appliqué: {q}")
        
        # Ajouter le filtre partenaire_bpi si nécessaire
        from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
        add_partenaire_bpi_filter(current_user, where_conditions, params, "c.")
        
        where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Requête SQL complète
        query = text(f"""
            SELECT 
                {preinscription_fields},
                {candidat_fields},
                {entreprise_fields},
                {eligibilite_fields}
            FROM {schema_name}.preinscription p
            INNER JOIN {schema_name}.candidat c ON c.id = p.candidat_id
            {entreprise_join}
            {eligibilite_join}
            {where_clause}
            ORDER BY p.cree_le DESC
            LIMIT 400
        """)
        
        logging.info(f"🔵 [DEBUG _get_preinscriptions] Exécution de la requête SQL directe")
        result = session.exec(query.bindparams(**params))
        rows = result.all()
        
        # Convertir les résultats en tuples (pre, cand, ent, elig) pour compatibilité avec le code existant
        for row in rows:
            row_dict = dict(row._mapping)
            
            # Extraire les données de preinscription (préfixe pre_)
            pre_data = {
                'id': row_dict.get('pre_id'),
                'programme_id': row_dict.get('pre_programme_id'),
                'candidat_id': row_dict.get('pre_candidat_id'),
                'source': row_dict.get('pre_source'),
                'statut': row_dict.get('pre_statut'),
                'cree_le': row_dict.get('pre_cree_le'),
                'civilite': row_dict.get('pre_civilite'),
                'nom': row_dict.get('pre_nom'),
                'prenom': row_dict.get('pre_prenom'),
                'date_naissance': row_dict.get('pre_date_naissance'),
                'email': row_dict.get('pre_email'),
                'telephone': row_dict.get('pre_telephone'),
                'situation_socio': row_dict.get('pre_situation_socio'),
                'numero_personnel': row_dict.get('pre_numero_personnel'),
                'rue_personnel': row_dict.get('pre_rue_personnel'),
                'code_postal_personnel': row_dict.get('pre_code_postal_personnel'),
                'ville_personnel': row_dict.get('pre_ville_personnel'),
                'numero_entreprise': row_dict.get('pre_numero_entreprise'),
                'rue_entreprise': row_dict.get('pre_rue_entreprise'),
                'code_postal_entreprise': row_dict.get('pre_code_postal_entreprise'),
                'ville_entreprise': row_dict.get('pre_ville_entreprise'),
                'date_creation_entreprise': row_dict.get('pre_date_creation_entreprise'),
                'siret': row_dict.get('pre_siret'),
                'chiffre_affaires': row_dict.get('pre_chiffre_affaires'),
                'niveau_etudes': row_dict.get('pre_niveau_etudes'),
                'secteur_activite': row_dict.get('pre_secteur_activite'),
            }
            
            # Extraire les données de candidat (préfixe cand_)
            cand_data = {
                'id': row_dict.get('cand_id'),
                'civilite': row_dict.get('cand_civilite'),
                'nom': row_dict.get('cand_nom'),
                'prenom': row_dict.get('cand_prenom'),
                'date_naissance': row_dict.get('cand_date_naissance'),
                'email': row_dict.get('cand_email'),
                'telephone': row_dict.get('cand_telephone'),
                'adresse_personnelle': row_dict.get('cand_adresse_personnelle'),
                'niveau_etudes': row_dict.get('cand_niveau_etudes'),
                'secteur_activite': row_dict.get('cand_secteur_activite'),
                'photo_profil': row_dict.get('cand_photo_profil'),
                'lat': row_dict.get('cand_lat'),
                'lng': row_dict.get('cand_lng'),
                'handicap': row_dict.get('cand_handicap'),
                'type_handicap': row_dict.get('cand_type_handicap'),
                'besoins_accommodation': row_dict.get('cand_besoins_accommodation'),
                'statut': row_dict.get('cand_statut'),
            }
            
            # Extraire les données d'entreprise si disponible (préfixe ent_)
            ent_data = {}
            if has_entreprise and row_dict.get('ent_id') is not None:
                ent_data = {
                    'id': row_dict.get('ent_id'),
                    'candidat_id': row_dict.get('ent_candidat_id'),
                    'siret': row_dict.get('ent_siret'),
                    'siren': row_dict.get('ent_siren'),
                    'raison_sociale': row_dict.get('ent_raison_sociale'),
                    'code_naf': row_dict.get('ent_code_naf'),
                    'date_creation': row_dict.get('ent_date_creation'),
                    'adresse': row_dict.get('ent_adresse'),
                    'qpv': row_dict.get('ent_qpv'),
                    'chiffre_affaires': row_dict.get('ent_chiffre_affaires'),
                    'nombre_points_vente': row_dict.get('ent_nombre_points_vente'),
                    'specialite_culinaire': row_dict.get('ent_specialite_culinaire'),
                    'nom_concept': row_dict.get('ent_nom_concept'),
                    'lien_reseaux_sociaux': row_dict.get('ent_lien_reseaux_sociaux'),
                    'site_internet': row_dict.get('ent_site_internet'),
                    'territoire': row_dict.get('ent_territoire'),
                    'lat': row_dict.get('ent_lat'),
                    'lng': row_dict.get('ent_lng'),
                }
            
            # Extraire les données d'éligibilité si disponible (préfixe elig_)
            elig_data = {}
            if has_eligibilite and row_dict.get('elig_id') is not None:
                elig_data = {
                    'id': row_dict.get('elig_id'),
                    'preinscription_id': row_dict.get('elig_preinscription_id'),
                    'ca_seuil_ok': row_dict.get('elig_ca_seuil_ok'),
                    'ca_score': row_dict.get('elig_ca_score'),
                    'qpv_ok': row_dict.get('elig_qpv_ok'),
                    'anciennete_ok': row_dict.get('elig_anciennete_ok'),
                    'anciennete_annees': row_dict.get('elig_anciennete_annees'),
                    'verdict': row_dict.get('elig_verdict'),
                    'details_json': row_dict.get('elig_details_json'),
                    'qpv_carte_url': row_dict.get('elig_qpv_carte_url'),
                    'qpv_image_url': row_dict.get('elig_qpv_image_url'),
                    'calcule_le': row_dict.get('elig_calcule_le'),
                }
            
            # Créer des objets simples pour compatibilité avec le code existant
            pre_obj = type('Preinscription', (), pre_data)()
            cand_obj = type('Candidat', (), cand_data)()
            ent_obj = type('Entreprise', (), ent_data)() if ent_data else None
            elig_obj = type('Eligibilite', (), elig_data)() if elig_data else None
            
            pre_rows.append((pre_obj, cand_obj, ent_obj, elig_obj))
        
        logging.info(f"🔵 [DEBUG _get_preinscriptions] ✓ Requête exécutée: {len(pre_rows)} résultats")
        
        if pre_rows:
            logging.info(f"🔵 [DEBUG _get_preinscriptions] Exemples de préinscriptions: {[row[0].id for row in pre_rows[:5]]}")
        
        if settings.DEBUG and pre_rows:
            print(f"🔍 [DEBUG] Programme ID: {prog.id}")
            print(f"📊 [DEBUG] Nombre de préinscriptions trouvées: {len(pre_rows)}")
            for i, row in enumerate(pre_rows[:3]):  # Afficher les 3 premières
                p, c, e, elig = row
                print(f"   {i+1}. Préinscription ID: {p.id}, Candidat: {c.nom} {c.prenom}")
                if hasattr(c, 'photo_profil') and c.photo_profil:
                    print(f"      🔗 URL générée: /media/{c.photo_profil}")
                    
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_preinscriptions] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_preinscriptions] Traceback:\n{traceback.format_exc()}")
        try:
            session.rollback()
            logging.info(f"🔵 [DEBUG _get_preinscriptions] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _get_preinscriptions] ❌ Erreur rollback: {rollback_err}")
        pre_rows = []
    
    logging.info(f"🔵 [DEBUG _get_preinscriptions] Fin - retour de {len(pre_rows)} préinscriptions")
    return pre_rows


def _load_candidat_documents(session: Session, cand, schema_name: str):
    """Charge les documents d'un candidat"""
    logging.info(f"🔵 [DEBUG _load_candidat_documents] Début - candidat_id={cand.id if cand else None}, schema={schema_name}")
    if not cand:
        logging.warning(f"🔵 [DEBUG _load_candidat_documents] ⚠ Candidat est None, retour")
        return
    
    cand.documents = []
    try:
        check_table = text(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = :schema_name AND table_name = 'document'
            )
        """)
        result = session.exec(check_table.bindparams(schema_name=schema_name))
        first_row = result.first()
        table_exists = first_row[0] if first_row else False
        
        if table_exists:
            documents_query = text(f"""
                SELECT * FROM {schema_name}.document 
                WHERE candidat_id = :candidat_id
                ORDER BY depose_le DESC
            """)
            doc_results = session.exec(documents_query.bindparams(candidat_id=cand.id)).all()
            for doc_row in doc_results:
                doc_dict = dict(doc_row._mapping)
                doc = Document(**doc_dict)
                merged_doc = session.merge(doc)
                cand.documents.append(merged_doc)
            logging.info(f"🔵 [DEBUG _load_candidat_documents] ✓ {len(cand.documents)} documents chargés")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _load_candidat_documents] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _load_candidat_documents] Traceback:\n{traceback.format_exc()}")
        cand.documents = []
        try:
            session.rollback()
            logging.info(f"🔵 [DEBUG _load_candidat_documents] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _load_candidat_documents] ❌ Erreur rollback: {rollback_err}")


def _get_inscription_for_candidat(session: Session, cand, prog, schema_name: str):
    """Récupère l'inscription d'un candidat pour un programme"""
    logging.info(f"🔵 [DEBUG _get_inscription_for_candidat] Début - candidat_id={cand.id if cand else None}, prog_id={prog.id if prog else None}, schema={schema_name}")
    inscription = None
    if not cand:
        logging.warning(f"🔵 [DEBUG _get_inscription_for_candidat] ⚠ Candidat est None, retour")
        return inscription
        
    try:
        check_table = text(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = :schema_name AND table_name = 'inscription'
            )
        """)
        result = session.exec(check_table.bindparams(schema_name=schema_name))
        first_row = result.first()
        table_exists = first_row[0] if first_row else False
        
        if table_exists:
            inscription_query = text(f"""
                SELECT * FROM {schema_name}.inscription 
                WHERE programme_id = :programme_id AND candidat_id = :candidat_id
                LIMIT 1
            """)
            result = session.exec(inscription_query.bindparams(
                programme_id=prog.id,
                candidat_id=cand.id
            )).first()
            
            # NOTE: Le modèle Inscription a été supprimé. Les candidats validés sont identifiés par leur statut dans la table Candidat.
            if result:
                # inscription = Inscription(**dict(result._mapping))
                # logging.info(f"🔵 [DEBUG _get_inscription_for_candidat] ✓ Inscription créée: ID={inscription.id}")
                logging.info(f"🔵 [DEBUG _get_inscription_for_candidat] ✓ Résultat trouvé (modèle Inscription supprimé)")
            else:
                logging.info(f"🔵 [DEBUG _get_inscription_for_candidat] ⚠ Aucun résultat trouvé")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_inscription_for_candidat] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_inscription_for_candidat] Traceback:\n{traceback.format_exc()}")
    
    # NOTE: Le modèle Inscription a été supprimé. Retourner None.
    logging.info(f"🔵 [DEBUG _get_inscription_for_candidat] Fin - modèle Inscription supprimé")
    return None


def _get_pipeline_for_inscription(session: Session, candidat, schema_name: str):
    """Récupère le pipeline (avancement) d'un candidat - NOTE: Le modèle Inscription a été supprimé"""
    candidat_id = candidat.id if candidat and hasattr(candidat, 'id') else None
    logging.info(f"🔵 [DEBUG _get_pipeline_for_inscription] Début - candidat_id={candidat_id}, schema={schema_name}")
    pipeline = []
    if not candidat:
        logging.warning(f"🔵 [DEBUG _get_pipeline_for_inscription] ⚠ Candidat est None, retour")
        return pipeline
        
    try:
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
        result_av = session.exec(check_av.bindparams(schema_name=schema_name))
        first_row_av = result_av.first()
        av_exists = first_row_av[0] if first_row_av else False
        
        result_ep = session.exec(check_ep.bindparams(schema_name=schema_name))
        first_row_ep = result_ep.first()
        ep_exists = first_row_ep[0] if first_row_ep else False
        
        if av_exists and ep_exists:
            av_query = text(f"""
                SELECT ae.*, ep.* 
                FROM {schema_name}.avancement_etape ae
                JOIN {schema_name}.etape_pipeline ep ON ae.etape_id = ep.id
                WHERE ae.inscription_id = :inscription_id
                ORDER BY ep.ordre
            """)
            # NOTE: AvancementEtape utilise maintenant candidat_id au lieu de inscription_id
            candidat_id = candidat.id if hasattr(candidat, 'id') else None
            av_results = session.exec(av_query.bindparams(inscription_id=candidat_id)).all() if candidat_id else []
            pipeline = []
            for av_row in av_results:
                pipeline.append({
                    "id": av_row.id,
                    "statut": av_row.statut,
                    "etape": {"libelle": av_row.libelle, "type_etape": av_row.type_etape, "ordre": av_row.ordre},
                    "debut": av_row.debut_le,
                    "fin": av_row.termine_le
                })
            logging.info(f"🔵 [DEBUG _get_pipeline_for_inscription] ✓ {len(pipeline)} étapes récupérées")
        else:
            logging.info(f"🔵 [DEBUG _get_pipeline_for_inscription] ⚠ Tables avancement_etape ou etape_pipeline manquantes")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_pipeline_for_inscription] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_pipeline_for_inscription] Traceback:\n{traceback.format_exc()}")
        pipeline = []
    
    logging.info(f"🔵 [DEBUG _get_pipeline_for_inscription] Fin - {len(pipeline)} étapes")
    return pipeline


def _calculate_kpis(session: Session, prog, schema_name: str):
    """Calcule les KPI pour un programme"""
    logging.info(f"🔵 [DEBUG _calculate_kpis] Début - prog_id={prog.id if prog else None}, schema={schema_name}")
    total_pre = 0
    total_insc = 0
    taux_conv = 0.0
    objectif_qpv_atteint = 0.0
    
    if not prog.id:
        logging.warning(f"🔵 [DEBUG _calculate_kpis] ⚠ prog.id est None, retour valeurs par défaut")
        return {"total_pre": 0, "total_insc": 0, "taux_conv": 0.0, "objectif_qpv_atteint": 0.0}
    
    try:
        session.exec(text(f"SET search_path TO {schema_name}, public"))
    except Exception as e:
        logging.warning(f"Erreur lors de la définition du search_path pour KPI: {e}")
    
    if _table_exists_in_schema(session, "preinscription", schema_name):
        try:
            total_pre = safe_count_query(session, Preinscription, programme_id=prog.id)
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des préinscriptions: {e}")
            total_pre = 0
    
    # NOTE: Le modèle Inscription a été supprimé. Les candidats validés sont identifiés par leur statut dans la table Candidat.
    if _table_exists_in_schema(session, "inscription", schema_name):
        try:
            # total_insc = safe_count_query(session, Inscription, programme_id=prog.id)
            total_insc = 0  # Modèle Inscription supprimé
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des inscriptions: {e}")
            total_insc = 0
    
    taux_conv = round((total_insc / total_pre * 100), 1) if total_pre else 0.0

    # Objectif QPV
    # Note: qpv_ok est un VARCHAR qui stocke "QPV:nom", "QPV limit:nom", ou "Aucun QPV"
    # Il faut vérifier si la valeur commence par "QPV" au lieu d'utiliser IS TRUE
    qpv_ok_count = 0
    if _table_exists_in_schema(session, "eligibilite", schema_name) and _table_exists_in_schema(session, "preinscription", schema_name):
        try:
            session.exec(text(f"SET search_path TO {schema_name}, public"))
            # Utiliser une requête SQL brute pour vérifier si qpv_ok commence par "QPV"
            qpv_query = text(f"""
                SELECT count(e.id) 
                FROM {schema_name}.eligibilite e
                JOIN {schema_name}.preinscription p ON p.id = e.preinscription_id
                WHERE p.programme_id = :programme_id 
                AND e.qpv_ok IS NOT NULL 
                AND e.qpv_ok LIKE 'QPV%'
            """)
            result = session.exec(qpv_query.bindparams(programme_id=prog.id))
            first_row = result.first()
            qpv_ok_count = first_row[0] if first_row else 0
            logging.info(f"🔵 [DEBUG _calculate_kpis] ✓ Comptage QPV réussi: {qpv_ok_count}")
        except Exception as e:
            logging.error(f"🔵 [DEBUG _calculate_kpis] ❌ ERREUR lors du comptage QPV: {type(e).__name__}: {str(e)}")
            import traceback
            logging.error(f"🔵 [DEBUG _calculate_kpis] Traceback:\n{traceback.format_exc()}")
            try:
                session.rollback()
                logging.info(f"🔵 [DEBUG _calculate_kpis] ✓ Rollback effectué après erreur QPV")
            except Exception as rollback_err:
                logging.error(f"🔵 [DEBUG _calculate_kpis] ❌ Erreur rollback: {rollback_err}")
            qpv_ok_count = 0
    
    objectif_qpv_atteint = round((qpv_ok_count / total_pre * 100), 1) if total_pre else 0.0
    
    return {
        "total_pre": total_pre,
        "total_insc": total_insc,
        "taux_conv": taux_conv,
        "objectif_qpv_atteint": objectif_qpv_atteint
    }


def _get_jurys(session: Session, prog, schema_name: str):
    """Récupère les jurys d'un programme"""
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_jurys] Début - prog_id={prog.id if prog else None}, schema={schema_name}")
    jurys = []
    
    if not prog.id:
        if settings.DEBUG:
            logging.warning(f"🔵 [DEBUG _get_jurys] ⚠ prog.id est None, retour liste vide")
        return jurys
    
    if not _table_exists_in_schema(session, "jury", "public"):
        if settings.DEBUG:
            logging.warning(f"🔵 [DEBUG _get_jurys] ⚠ Table 'jury' n'existe pas dans le schéma 'public'")
        return jurys
    
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_jurys] Table 'jury' existe, exécution de la requête")
    try:
        # Les jurys sont stockés dans le schéma public, pas dans le schéma du programme
        # Configurer le search_path vers public
        session.exec(text("SET search_path TO public, public"))
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_jurys] ✓ Search_path configuré vers 'public'")
        
        # Utiliser directement le modèle Jury (qui pointe vers public.jury)
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_jurys] Exécution de la requête pour programme_id={prog.id}")
        
        # Récupérer tous les jurys pour vérifier
        all_jurys_check = session.exec(select(Jury)).all()
        total_jurys = len(all_jurys_check)
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_jurys] Total de jurys dans 'public': {total_jurys}")
        
        if total_jurys > 0:
            prog_ids_all = list(set([j.programme_id for j in all_jurys_check]))
            if settings.DEBUG:
                logging.info(f"🔵 [DEBUG _get_jurys] Programme IDs des jurys existants: {prog_ids_all}")
        
        # Utiliser une requête SQL directe pour récupérer les données comme dictionnaires
        # Cela évite complètement les problèmes de lazy loading et d'objets SQLAlchemy
        jury_query = text("""
            SELECT 
                id,
                programme_id,
                promotion_id,
                session_le,
                lieu,
                statut
            FROM public.jury
            WHERE programme_id = :programme_id
            ORDER BY session_le DESC
        """)
        
        result = session.exec(jury_query.bindparams(programme_id=prog.id))
        rows = result.all()
        
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_jurys] ✓ Requête SQL directe exécutée: {len(rows)} jurys trouvés pour programme_id={prog.id}")
        
        if len(rows) == 0 and total_jurys > 0:
            if settings.DEBUG:
                logging.warning(f"🔵 [DEBUG _get_jurys] ⚠ Il y a {total_jurys} jurys dans 'public' mais aucun pour programme_id={prog.id}")
                logging.warning(f"🔵 [DEBUG _get_jurys] Programme IDs disponibles: {prog_ids_all}")
        
        # Convertir les résultats en dictionnaires directement
        # Les Row objects de SQLAlchemy peuvent être convertis en dict via _mapping
        jurys = []
        for row in rows:
            try:
                # Convertir le Row object en dictionnaire directement
                # Utiliser _mapping pour obtenir un dictionnaire ordonné
                jury_dict = dict(row._mapping)
                jurys.append(jury_dict)
                
                if settings.DEBUG:
                    logging.info(f"🔵 [DEBUG _get_jurys] ✓ Jury converti: ID={jury_dict.get('id')}, programme_id={jury_dict.get('programme_id')}, session_le={jury_dict.get('session_le')}, lieu={jury_dict.get('lieu')}")
            except Exception as e:
                logging.error(f"🔵 [DEBUG _get_jurys] ❌ Erreur lors de la conversion du jury: {e}")
                import traceback
                logging.error(traceback.format_exc())
                continue
        
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_jurys] ✓ {len(jurys)} jurys récupérés avec succès et convertis en dictionnaires")
            if len(jurys) > 0:
                logging.info(f"🔵 [DEBUG _get_jurys] Type du premier élément: {type(jurys[0])}")
                logging.info(f"🔵 [DEBUG _get_jurys] Clés du premier dictionnaire: {list(jurys[0].keys()) if isinstance(jurys[0], dict) else 'N/A'}")
        
        # Remettre le search_path sur le schéma du programme pour la suite
        session.exec(text(f"SET search_path TO {schema_name}, public"))
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_jurys] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_jurys] Traceback:\n{traceback.format_exc()}")
        try:
            session.rollback()
            if settings.DEBUG:
                logging.info(f"🔵 [DEBUG _get_jurys] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _get_jurys] ❌ Erreur rollback: {rollback_err}")
        jurys = []
    
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_jurys] Fin - {len(jurys)} jurys")
        # Vérification finale stricte
        for i, item in enumerate(jurys):
            if not isinstance(item, dict):
                logging.error(f"🔵 [DEBUG _get_jurys] ❌ ERREUR: L'élément {i} n'est pas un dictionnaire, type: {type(item)}")
    
    # Retourner uniquement les dictionnaires (sécurité supplémentaire)
    return [item for item in jurys if isinstance(item, dict)]


def _get_decisions_jury(session: Session, cand, schema_name: str):
    """Récupère les décisions du jury pour un candidat sous forme de dictionnaires"""
    decisions_jury = []
    if not (cand and _table_exists_in_schema(session, "decision_jury_candidat", schema_name)):
        return decisions_jury
        
    try:
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        # Requête SQL avec JOINs pour récupérer toutes les données nécessaires
        decision_query = text(f"""
            SELECT 
                djc.*,
                j.session_le as jury_session_le,
                j.lieu as jury_lieu,
                u.nom_complet as conseiller_nom_complet,
                u.email as conseiller_email,
                g.nom as groupe_nom,
                p.libelle as promotion_libelle,
                pt.nom as partenaire_nom
            FROM {schema_name}.decision_jury_candidat djc
            LEFT JOIN public.jury j ON djc.jury_id = j.id
            LEFT JOIN public."user" u ON djc.conseiller_id = u.id
            LEFT JOIN public.groupe g ON djc.groupe_id = g.id
            LEFT JOIN public.promotion p ON djc.promotion_id = p.id
            LEFT JOIN public.partenaire pt ON djc.partenaire_id = pt.id
            WHERE djc.candidat_id = :candidat_id
            ORDER BY djc.date_decision DESC
        """)
        decision_results = session.exec(decision_query.bindparams(candidat_id=cand.id)).all()
        # Convertir directement en dictionnaires avec les relations incluses
        for dec_row in decision_results:
            dec_dict = dict(dec_row._mapping)
            # Ajouter les données des relations pour faciliter l'accès dans le template
            if dec_dict.get('conseiller_nom_complet'):
                dec_dict['conseiller'] = {
                    'nom_complet': dec_dict.get('conseiller_nom_complet') or dec_dict.get('conseiller_email', '')
                }
            if dec_dict.get('groupe_nom'):
                dec_dict['groupe'] = {'nom': dec_dict.get('groupe_nom')}
            if dec_dict.get('promotion_libelle'):
                dec_dict['promotion'] = {'libelle': dec_dict.get('promotion_libelle')}
            if dec_dict.get('partenaire_nom'):
                dec_dict['partenaire'] = {'nom': dec_dict.get('partenaire_nom')}
            if dec_dict.get('jury_session_le'):
                dec_dict['jury'] = {
                    'session_le': dec_dict.get('jury_session_le'),
                    'lieu': dec_dict.get('jury_lieu')
                }
            decisions_jury.append(dec_dict)
    except Exception as e:
        logging.warning(f"Erreur lors de la récupération des décisions jury: {e}")
        import traceback
        logging.error(traceback.format_exc())
        decisions_jury = []
    
    return decisions_jury


def _get_conseillers(session: Session):
    """Récupère les conseillers sous forme de dictionnaires"""
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_conseillers] Début")
    conseillers = []
    try:
        # Les utilisateurs sont dans le schéma public
        session.exec(text("SET search_path TO public, public"))
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_conseillers] ✓ Search_path configuré vers 'public'")
        
        # Requête SQL directe
        conseiller_query = text("""
            SELECT 
                id,
                nom_complet,
                email
            FROM public."user"
            WHERE role = :role
        """)
        
        result = session.exec(conseiller_query.bindparams(role=UserRole.CONSEILLER.value))
        rows = result.all()
        
        # Convertir en dictionnaires
        for row in rows:
            row_dict = dict(row._mapping)
            conseillers.append({
                "id": row_dict.get("id"),
                "nom": None,  # User n'a pas de nom séparé
                "prenom": None,  # User n'a pas de prénom séparé
                "email": row_dict.get("email"),
                "nom_complet": row_dict.get("nom_complet") or row_dict.get("email", "")
            })
        
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_conseillers] ✓ {len(conseillers)} conseillers récupérés")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_conseillers] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_conseillers] Traceback:\n{traceback.format_exc()}")
        try:
            session.rollback()
            if settings.DEBUG:
                logging.info(f"🔵 [DEBUG _get_conseillers] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _get_conseillers] ❌ Erreur rollback: {rollback_err}")
        conseillers = []
    
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_conseillers] Fin - {len(conseillers)} conseillers")
    return conseillers


def _get_promotions(session: Session):
    """Récupère les promotions actives sous forme de dictionnaires"""
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_promotions] Début")
    promotions = []
    try:
        # Les promotions sont dans le schéma public
        session.exec(text("SET search_path TO public, public"))
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_promotions] ✓ Search_path configuré vers 'public'")
        
        # Requête SQL directe
        promo_query = text("""
            SELECT 
                id,
                libelle,
                programme_id,
                capacite,
                date_debut,
                date_fin,
                actif
            FROM public.promotion
            WHERE actif = true
        """)
        
        result = session.exec(promo_query)
        rows = result.all()
        
        # Convertir en dictionnaires
        for row in rows:
            promotions.append(dict(row._mapping))
        
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_promotions] ✓ {len(promotions)} promotions récupérées")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_promotions] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_promotions] Traceback:\n{traceback.format_exc()}")
        try:
            session.rollback()
            if settings.DEBUG:
                logging.info(f"🔵 [DEBUG _get_promotions] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _get_promotions] ❌ Erreur rollback: {rollback_err}")
        promotions = []
    
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_promotions] Fin - {len(promotions)} promotions")
    return promotions


def _get_partenaires(session: Session):
    """Récupère les partenaires actifs sous forme de dictionnaires"""
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_partenaires] Début")
    partenaires = []
    try:
        # Les partenaires sont dans le schéma public
        session.exec(text("SET search_path TO public, public"))
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_partenaires] ✓ Search_path configuré vers 'public'")
        
        # Requête SQL directe
        partenaire_query = text("""
            SELECT 
                id,
                nom,
                actif
            FROM public.partenaire
            WHERE actif = true
        """)
        
        result = session.exec(partenaire_query)
        rows = result.all()
        
        # Convertir en dictionnaires
        for row in rows:
            partenaires.append(dict(row._mapping))
        
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_partenaires] ✓ {len(partenaires)} partenaires récupérés")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_partenaires] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_partenaires] Traceback:\n{traceback.format_exc()}")
        try:
            session.rollback()
            if settings.DEBUG:
                logging.info(f"🔵 [DEBUG _get_partenaires] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _get_partenaires] ❌ Erreur rollback: {rollback_err}")
        partenaires = []
    
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_partenaires] Fin - {len(partenaires)} partenaires")
    return partenaires


def _get_groupes(session: Session):
    """Récupère les groupes actifs sous forme de dictionnaires"""
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_groupes] Début")
    groupes = []
    try:
        # Les groupes sont dans le schéma public
        session.exec(text("SET search_path TO public, public"))
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_groupes] ✓ Search_path configuré vers 'public'")
        
        # Requête SQL directe
        groupe_query = text("""
            SELECT 
                id,
                nom,
                actif
            FROM public.groupe
            WHERE actif = true
            ORDER BY nom
        """)
        
        result = session.exec(groupe_query)
        rows = result.all()
        
        # Convertir en dictionnaires
        for row in rows:
            groupes.append(dict(row._mapping))
        
        if settings.DEBUG:
            logging.info(f"🔵 [DEBUG _get_groupes] ✓ {len(groupes)} groupes récupérés")
    except Exception as e:
        logging.error(f"🔵 [DEBUG _get_groupes] ❌ ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"🔵 [DEBUG _get_groupes] Traceback:\n{traceback.format_exc()}")
        try:
            session.rollback()
            if settings.DEBUG:
                logging.info(f"🔵 [DEBUG _get_groupes] ✓ Rollback effectué")
        except Exception as rollback_err:
            logging.error(f"🔵 [DEBUG _get_groupes] ❌ Erreur rollback: {rollback_err}")
        groupes = []
    
    if settings.DEBUG:
        logging.info(f"🔵 [DEBUG _get_groupes] Fin - {len(groupes)} groupes")
    return groupes


def _extract_qpv_name(elig):
    """Extrait le nom du QPV depuis les détails d'éligibilité"""
    qpv_name = None
    if not (elig and elig.details_json):
        return qpv_name
        
    try:
        import json
        qpv_details = json.loads(elig.details_json)
        if qpv_details.get("adresses_analysees"):
            for analyse in qpv_details["adresses_analysees"]:
                if analyse.get("resultat") and analyse["resultat"].get("nom_qp"):
                    nom_qp = analyse["resultat"]["nom_qp"]
                    if "QPV:" in nom_qp or "QPV limit:" in nom_qp:
                        qpv_name = nom_qp
                        break
    except (json.JSONDecodeError, KeyError, IndexError):
        qpv_name = None
    
    return qpv_name


def _prepare_user_for_template(current_user):
    """Charge les attributs de l'utilisateur pour éviter le lazy loading"""
    if not current_user:
        return current_user
        
    try:
        # Forcer le chargement de tous les attributs nécessaires
        _ = current_user.id
        _ = current_user.email
        _ = current_user.nom_complet if hasattr(current_user, 'nom_complet') else None
        _ = current_user.photo_profil if hasattr(current_user, 'photo_profil') else None
        _ = current_user.role if hasattr(current_user, 'role') else None
    except Exception as e:
        logging.warning(f"Erreur lors du chargement des attributs utilisateur: {e}")
        # En cas d'erreur, créer un objet simple pour éviter le lazy loading
        current_user_dict = {
            "id": getattr(current_user, 'id', None),
            "email": getattr(current_user, 'email', ''),
            "nom_complet": getattr(current_user, 'nom_complet', '') if hasattr(current_user, 'nom_complet') else '',
            "photo_profil": getattr(current_user, 'photo_profil', None) if hasattr(current_user, 'photo_profil') else None,
            "role": getattr(current_user, 'role', None) if hasattr(current_user, 'role') else None
        }
        current_user = type('UserDict', (), current_user_dict)()
    
    return current_user


@router.get("/form", name="form_inscriptions_display", response_class=HTMLResponse)
def inscriptions_ui(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    programme: str = Query("ACD"),
    q: Optional[str] = Query(None),
    pre_id: Optional[int] = Query(None),
):
    """Page de gestion des inscriptions avec préinscriptions"""
    logging.info(f"🔵 [DEBUG] ===== DEBUT inscriptions_ui =====")
    logging.info(f"🔵 [DEBUG] Paramètres: programme={programme}, q={q}, pre_id={pre_id}")
    
    try:
        # Gestion des transactions échouées - rollback si nécessaire
        logging.info(f"🔵 [DEBUG] Étape 1: Rollback initial de la session")
        try:
            session.rollback()
            logging.info(f"🔵 [DEBUG] ✓ Rollback réussi")
        except Exception as e:
            logging.warning(f"🔵 [DEBUG] ⚠ Erreur lors du rollback initial: {e}")
        
        # Récupérer le programme
        logging.info(f"🔵 [DEBUG] Étape 2: Récupération du programme '{programme}'")
        prog = _prog_by_code(session, programme)
        if not prog:
            logging.warning(f"🔵 [DEBUG] ⚠ Programme '{programme}' non trouvé, création d'un programme factice")
            # Créer un programme factice avec des valeurs vides
            class ProgrammeFactice:
                def __init__(self):
                    self.id = None
                    self.code = programme
                    self.nom = f"Programme {programme} (non trouvé)"
            prog = ProgrammeFactice()
        else:
            logging.info(f"🔵 [DEBUG] ✓ Programme trouvé: ID={prog.id}, Nom={prog.nom}")

        schema_name = programme.lower() if programme else "public"
        logging.info(f"🔵 [DEBUG] Schema name: {schema_name}")
        
        # Récupérer les préinscriptions
        logging.info(f"🔵 [DEBUG] Étape 3: Récupération des préinscriptions")
        pre_rows = _get_preinscriptions(session, prog, schema_name, q, current_user)
        logging.info(f"🔵 [DEBUG] ✓ {len(pre_rows)} préinscriptions récupérées")

        # Si une préinscription spécifique est demandée
        selected = None
        cand = None
        ent = None
        elig = None
        inscription = None
        pipeline = []
        
        if pre_id:
            logging.info(f"🔵 [DEBUG] Étape 4: Recherche de préinscription ID={pre_id}")
            if settings.DEBUG:
                print(f"🎯 [DEBUG] Recherche de préinscription ID: {pre_id}")
            
            # Chercher la préinscription dans la liste
            for row in pre_rows:
                if row[0].id == pre_id:
                    selected, cand, ent, elig = row
                    logging.info(f"🔵 [DEBUG] ✓ Préinscription trouvée: ID={selected.id}, Candidat={cand.nom} {cand.prenom}")
                    if settings.DEBUG:
                        print(f"✅ [DEBUG] Préinscription trouvée: {selected.id}, Candidat: {cand.nom} {cand.prenom}")
                    break
            
            if not selected:
                logging.warning(f"🔵 [DEBUG] ⚠ Préinscription ID {pre_id} non trouvée dans la liste")
                available_ids = [row[0].id for row in pre_rows]
                logging.warning(f"🔵 [DEBUG] IDs disponibles: {available_ids}")
                if settings.DEBUG:
                    print(f"❌ [DEBUG] Préinscription ID {pre_id} non trouvée dans la liste")
                    print(f"📋 [DEBUG] IDs disponibles: {available_ids}")
            
            # Charger les données du candidat sélectionné
            if selected:
                logging.info(f"🔵 [DEBUG] Étape 5: Chargement des données du candidat sélectionné")
                try:
                    session.exec(text(f"SET search_path TO {schema_name}, public"))
                    logging.info(f"🔵 [DEBUG] ✓ Search_path défini: {schema_name}")
                    
                    logging.info(f"🔵 [DEBUG] 5.1: Chargement des documents")
                    _load_candidat_documents(session, cand, schema_name)
                    logging.info(f"🔵 [DEBUG] ✓ Documents chargés: {len(cand.documents) if hasattr(cand, 'documents') else 0}")
                    
                    logging.info(f"🔵 [DEBUG] 5.2: Récupération de l'inscription")
                    # NOTE: Le modèle Inscription a été supprimé. Utiliser directement le candidat.
                    # inscription = _get_inscription_for_candidat(session, cand, prog, schema_name)
                    # if inscription:
                    #     logging.info(f"🔵 [DEBUG] ✓ Inscription trouvée: ID={inscription.id}")
                    # else:
                    #     logging.info(f"🔵 [DEBUG] ⚠ Aucune inscription trouvée pour ce candidat")
                    
                    if cand:
                        logging.info(f"🔵 [DEBUG] 5.3: Récupération du pipeline")
                        pipeline = _get_pipeline_for_inscription(session, inscription, schema_name)
                        logging.info(f"🔵 [DEBUG] ✓ Pipeline récupéré: {len(pipeline)} étapes")
                except Exception as e:
                    logging.error(f"🔵 [DEBUG] ❌ Erreur lors du chargement des données candidat: {e}")
                    import traceback
                    logging.error(traceback.format_exc())

        # Calculer les KPI
        logging.info(f"🔵 [DEBUG] Étape 6: Calcul des KPI")
        kpi_data = _calculate_kpis(session, prog, schema_name)
        logging.info(f"🔵 [DEBUG] ✓ KPI calculés: total_pre={kpi_data['total_pre']}, total_insc={kpi_data['total_insc']}, taux_conv={kpi_data['taux_conv']}%")

        # Récupérer les données supplémentaires
        logging.info(f"🔵 [DEBUG] Étape 7: Récupération des données supplémentaires")
        
        logging.info(f"🔵 [DEBUG] 7.1: Jurys")
        jurys = _get_jurys(session, prog, schema_name)
        logging.info(f"🔵 [DEBUG] ✓ {len(jurys)} jurys récupérés")
        if len(jurys) > 0:
            logging.info(f"🔵 [DEBUG] Type du premier jury: {type(jurys[0])}")
            if isinstance(jurys[0], dict):
                logging.info(f"🔵 [DEBUG] ✓ Les jurys sont bien des dictionnaires")
            else:
                logging.warning(f"🔵 [DEBUG] ⚠ Les jurys ne sont PAS des dictionnaires, type: {type(jurys[0])}")
        
        logging.info(f"🔵 [DEBUG] 7.2: Décisions jury")
        decisions_jury = _get_decisions_jury(session, cand, schema_name)
        logging.info(f"🔵 [DEBUG] ✓ {len(decisions_jury)} décisions récupérées")
        
        logging.info(f"🔵 [DEBUG] 7.3: Conseillers")
        conseillers = _get_conseillers(session)
        logging.info(f"🔵 [DEBUG] ✓ {len(conseillers)} conseillers récupérés")
        
        logging.info(f"🔵 [DEBUG] 7.4: Promotions")
        promotions = _get_promotions(session)
        logging.info(f"🔵 [DEBUG] ✓ {len(promotions)} promotions récupérées")
        
        logging.info(f"🔵 [DEBUG] 7.5: Partenaires")
        partenaires = _get_partenaires(session)
        logging.info(f"🔵 [DEBUG] ✓ {len(partenaires)} partenaires récupérés")
        
        logging.info(f"🔵 [DEBUG] 7.6: Groupes")
        groupes = _get_groupes(session)
        logging.info(f"🔵 [DEBUG] ✓ {len(groupes)} groupes récupérés")
        
        # Extraire le nom QPV
        logging.info(f"🔵 [DEBUG] Étape 8: Extraction du nom QPV")
        qpv_name = _extract_qpv_name(elig)
        logging.info(f"🔵 [DEBUG] ✓ QPV name: {qpv_name}")

        # Préparer le search_path et les documents avant le rendu
        logging.info(f"🔵 [DEBUG] Étape 9: Préparation avant rendu template")
        if cand and schema_name:
            try:
                session.exec(text(f"SET search_path TO {schema_name}, public"))
                if hasattr(cand, 'documents'):
                    _ = cand.documents
                logging.info(f"🔵 [DEBUG] ✓ Search_path et documents préparés")
            except Exception as e:
                logging.warning(f"🔵 [DEBUG] ⚠ Erreur lors de la configuration du search_path avant rendu: {e}")
        
        # Préparer l'utilisateur pour le template
        logging.info(f"🔵 [DEBUG] Étape 10: Préparation de l'utilisateur")
        current_user = _prepare_user_for_template(current_user)
        logging.info(f"🔵 [DEBUG] ✓ Utilisateur préparé: ID={getattr(current_user, 'id', None)}")
        
        logging.info(f"🔵 [DEBUG] Étape 11: Rendu du template")

        logging.info(f"🔵 [DEBUG] Préparation du contexte template")
        template_context = {
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
                "total_pre": int(kpi_data["total_pre"]),
                "total_insc": int(kpi_data["total_insc"]),
                "taux_conv": kpi_data["taux_conv"],
                "objectif_qpv_atteint": kpi_data["objectif_qpv_atteint"],
            },
            "timestamp": int(datetime.now().timestamp()),
        }
        logging.info(f"🔵 [DEBUG] ✓ Contexte préparé, rendu du template")
        logging.info(f"🔵 [DEBUG] ===== FIN inscriptions_ui (SUCCÈS) =====")
        
        return templates.TemplateResponse(
            "pages/programme/inscription.html",
            template_context
        )
    except Exception as e:
        # Logger l'erreur complète pour le débogage
        import traceback
        error_traceback = traceback.format_exc()
        logging.error(f"🔵 [DEBUG] ===== ERREUR dans inscriptions_ui =====")
        logging.error(f"🔵 [DEBUG] ❌ Type d'erreur: {type(e).__name__}")
        logging.error(f"🔵 [DEBUG] ❌ Message: {str(e)}")
        logging.error(f"🔵 [DEBUG] ❌ Traceback complet:\n{error_traceback}")
        logging.error(f"🔵 [DEBUG] ===== FIN inscriptions_ui (ERREUR) =====")
        
        # Rollback de la session en cas d'erreur
        try:
            session.rollback()
            logging.info(f"🔵 [DEBUG] ✓ Rollback effectué après erreur")
        except Exception as rollback_error:
            logging.error(f"🔵 [DEBUG] ❌ Erreur lors du rollback: {rollback_error}")
        
        # Retourner une réponse d'erreur au lieu de laisser FastAPI gérer
        # Cela permettra de mieux voir l'erreur dans les logs
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du chargement de la page d'inscriptions: {str(e)}. Consultez les logs pour plus de détails."
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
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
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
    situation_socio: Optional[str] = Form(None),
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
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que les tables existent
        if not table_exists_anywhere("preinscription", session, schema_name):
            raise HTTPException(status_code=404, detail="Préinscription introuvable dans ce programme")
        if not table_exists_anywhere("candidat", session, schema_name):
            raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
        
        # Récupérer la préinscription via requête SQL directe
        pre_query = text(f"""
            SELECT id, candidat_id, programme_id
            FROM {schema_name}.preinscription
            WHERE id = :pre_id
        """)
        pre_result = session.exec(pre_query.bindparams(pre_id=pre_id)).first()
        if not pre_result:
            prog_query = text("SELECT code FROM public.programme WHERE code = :programme_code")
            prog_result = session.exec(prog_query.bindparams(programme_code=programme.upper())).first()
            prog_code = prog_result.code if prog_result and hasattr(prog_result, 'code') else (prog_result[0] if prog_result else programme)
            redirect_url = request.url_for("form_inscriptions_display")
            redirect_url = f"{redirect_url}?programme={prog_code}&pre_id={pre_id}"
            params = {
                "save_success": "false",
                "message": "Préinscription introuvable",
                "error_type": "NotFound"
            }
            return RedirectResponse(url=f"{redirect_url}&{urlencode(params)}", status_code=status.HTTP_302_FOUND)
        
        candidat_id = pre_result.candidat_id if hasattr(pre_result, 'candidat_id') else pre_result[1]
        programme_id = pre_result.programme_id if hasattr(pre_result, 'programme_id') else pre_result[2]
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, photo_profil
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        cand_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        if not cand_result:
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        cand_id = cand_result.id if hasattr(cand_result, 'id') else cand_result[0]
        old_photo_profil = cand_result.photo_profil if hasattr(cand_result, 'photo_profil') else (cand_result[1] if len(cand_result) > 1 else None)
        
        # Vérifier si l'entreprise existe via requête SQL directe
        entreprise_id = None
        if table_exists_anywhere("entreprise", session, schema_name):
            entreprise_query = text(f"""
                SELECT id
                FROM {schema_name}.entreprise
                WHERE candidat_id = :candidat_id
                LIMIT 1
            """)
            ent_result = session.exec(entreprise_query.bindparams(candidat_id=candidat_id)).first()
            if ent_result:
                entreprise_id = ent_result.id if hasattr(ent_result, 'id') else ent_result[0]
        
        # Créer l'entreprise si elle n'existe pas
        if not entreprise_id:
            insert_entreprise_query = text(f"""
                INSERT INTO {schema_name}.entreprise (candidat_id)
                VALUES (:candidat_id)
                RETURNING id
            """)
            ent_result = session.exec(insert_entreprise_query.bindparams(candidat_id=candidat_id)).first()
            entreprise_id = ent_result.id if hasattr(ent_result, 'id') else ent_result[0]
        
        # Construire la requête UPDATE pour le candidat
        candidat_update_fields = []
        candidat_params = {"candidat_id": candidat_id}
        
        if civilite:
            candidat_update_fields.append("civilite = :civilite")
            candidat_params["civilite"] = civilite
        if date_naissance:
            try:
                candidat_update_fields.append("date_naissance = :date_naissance")
                candidat_params["date_naissance"] = _date.fromisoformat(date_naissance)
            except Exception:
                pass
        if telephone is not None:
            candidat_update_fields.append("telephone = :telephone")
            candidat_params["telephone"] = telephone
        if adresse_personnelle is not None:
            candidat_update_fields.append("adresse_personnelle = :adresse_personnelle")
            candidat_params["adresse_personnelle"] = adresse_personnelle
        if niveau_etudes is not None:
            candidat_update_fields.append("niveau_etudes = :niveau_etudes")
            candidat_params["niveau_etudes"] = niveau_etudes
        if secteur_activite is not None:
            candidat_update_fields.append("secteur_activite = :secteur_activite")
            candidat_params["secteur_activite"] = secteur_activite
        if situation_socio is not None:
            # Convertir les valeurs vides ou 'nc' en 'Non communiqué'
            if situation_socio.strip() == '' or situation_socio.strip().lower() == 'nc':
                situation_socio = 'Non communiqué'
            candidat_update_fields.append("situation_socio = :situation_socio")
            candidat_params["situation_socio"] = situation_socio
        if handicap is not None:
            candidat_update_fields.append("handicap = :handicap")
            candidat_params["handicap"] = handicap == "true"
        if lat is not None and lat.strip():
            try:
                candidat_update_fields.append("lat = :lat")
                candidat_params["lat"] = float(lat)
            except (ValueError, TypeError):
                pass
        if lng is not None and lng.strip():
            try:
                candidat_update_fields.append("lng = :lng")
                candidat_params["lng"] = float(lng)
            except (ValueError, TypeError):
                pass
        
        # Mise à jour de la photo de profil
        new_photo_path = None
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
                if old_photo_profil:
                    try:
                        # Essayer de supprimer depuis media/ d'abord
                        media_path = path_config.MEDIA_DIR / old_photo_profil
                        if media_path.exists():
                            media_path.unlink()
                        else:
                            # Sinon essayer depuis uploads/ (ancien format)
                            FileUploadService.delete_file(old_photo_profil)
                        if settings.DEBUG:
                            print(f"🗑️ [DEBUG] Ancienne photo supprimée: {old_photo_profil}")
                    except Exception as e:
                        if settings.DEBUG:
                            print(f"⚠️ [DEBUG] Erreur lors de la suppression de l'ancienne photo: {e}")
                
                # Utiliser FileUploadService.save_media_file pour sauvegarder dans media/profile_image/{programme}/
                file_info = await FileUploadService.save_media_file(
                    photo_profil,
                    media_type="profile_image",
                    programme_code=programme,
                    subfolder_id=pre_id
                )
                
                new_photo_path = file_info["relative_path"]
                candidat_update_fields.append("photo_profil = :photo_profil")
                candidat_params["photo_profil"] = new_photo_path
                
                if settings.DEBUG:
                    print(f"📸 [DEBUG] Nouvelle photo sauvegardée: {new_photo_path}")
                    
            except Exception as e:
                if settings.DEBUG:
                    print(f"❌ [DEBUG] Erreur sauvegarde photo: {e}")
                # On continue sans la photo
        
        # Exécuter la mise à jour du candidat si nécessaire
        if candidat_update_fields:
            update_candidat_query = text(f"""
                UPDATE {schema_name}.candidat
                SET {', '.join(candidat_update_fields)}
                WHERE id = :candidat_id
            """)
            session.exec(update_candidat_query.bindparams(**candidat_params))
        
        # Construire la requête UPDATE pour l'entreprise
        entreprise_update_fields = []
        entreprise_params = {"entreprise_id": entreprise_id}
        
        if chiffre_affaires is not None:
            entreprise_update_fields.append("chiffre_affaires = :chiffre_affaires")
            entreprise_params["chiffre_affaires"] = chiffre_affaires
        if nombre_points_vente is not None and nombre_points_vente.strip():
            try:
                entreprise_update_fields.append("nombre_points_vente = :nombre_points_vente")
                entreprise_params["nombre_points_vente"] = int(nombre_points_vente)
            except (ValueError, TypeError):
                pass
        if specialite_culinaire is not None:
            entreprise_update_fields.append("specialite_culinaire = :specialite_culinaire")
            entreprise_params["specialite_culinaire"] = specialite_culinaire
        if nom_concept is not None:
            entreprise_update_fields.append("nom_concept = :nom_concept")
            entreprise_params["nom_concept"] = nom_concept
        if site_internet is not None:
            entreprise_update_fields.append("site_internet = :site_internet")
            entreprise_params["site_internet"] = site_internet
        if lien_reseaux_sociaux is not None:
            entreprise_update_fields.append("lien_reseaux_sociaux = :lien_reseaux_sociaux")
            entreprise_params["lien_reseaux_sociaux"] = lien_reseaux_sociaux
        if qpv is not None:
            entreprise_update_fields.append("qpv = :qpv")
            entreprise_params["qpv"] = qpv == "true"
        if siret is not None:
            entreprise_update_fields.append("siret = :siret")
            entreprise_params["siret"] = siret
        if siren is not None:
            entreprise_update_fields.append("siren = :siren")
            entreprise_params["siren"] = siren
        if raison_sociale is not None:
            entreprise_update_fields.append("raison_sociale = :raison_sociale")
            entreprise_params["raison_sociale"] = raison_sociale
        if code_naf is not None:
            entreprise_update_fields.append("code_naf = :code_naf")
            entreprise_params["code_naf"] = code_naf
        if date_creation:
            try:
                entreprise_update_fields.append("date_creation = :date_creation")
                entreprise_params["date_creation"] = _date.fromisoformat(date_creation)
            except Exception:
                pass
        if adresse_entreprise is not None:
            entreprise_update_fields.append("adresse = :adresse")
            entreprise_params["adresse"] = adresse_entreprise
        
        # Exécuter la mise à jour de l'entreprise si nécessaire
        if entreprise_update_fields:
            update_entreprise_query = text(f"""
                UPDATE {schema_name}.entreprise
                SET {', '.join(entreprise_update_fields)}
                WHERE id = :entreprise_id
            """)
            session.exec(update_entreprise_query.bindparams(**entreprise_params))
        
        # Mettre à jour situation_socio dans la préinscription également
        if situation_socio is not None and table_exists_anywhere("preinscription", session, schema_name):
            # Convertir les valeurs vides ou 'nc' en 'Non communiqué'
            situation_socio_pre = situation_socio
            if situation_socio_pre.strip() == '' or situation_socio_pre.strip().lower() == 'nc':
                situation_socio_pre = 'Non communiqué'
            update_preinscription_query = text(f"""
                UPDATE {schema_name}.preinscription
                SET situation_socio = :situation_socio
                WHERE id = :pre_id
            """)
            session.exec(update_preinscription_query.bindparams(
                situation_socio=situation_socio_pre,
                pre_id=pre_id
            ))
        
        session.commit()
        
        # Log de l'activité
        from ..services.audit import log_activity
        log_activity(
            session=session,
            user=current_user,
            action="Mise à jour informations candidat",
            entity="Candidat",
            entity_id=cand_id,
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
        
        # Récupérer le programme pour la redirection
        prog_query = text("SELECT code FROM public.programme WHERE id = :programme_id")
        prog_result = session.exec(prog_query.bindparams(programme_id=programme_id)).first()
        prog_code = prog_result.code if prog_result and hasattr(prog_result, 'code') else (prog_result[0] if prog_result else programme)
        
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={prog_code}&pre_id={pre_id}"
        
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
        
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={programme}&pre_id={pre_id}"
        
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
        
        redirect_url = request.url_for("form_inscriptions_display")
        redirect_url = f"{redirect_url}?programme={programme}&pre_id={pre_id}"
        
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
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        logging.info(f"🔄 [RECALC] Début recalcul éligibilité pour préinscription {pre_id} dans le schéma {schema_name}")
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que les tables existent
        if not table_exists_anywhere("preinscription", session, schema_name):
            raise HTTPException(status_code=404, detail="Préinscription introuvable dans ce programme")
        if not table_exists_anywhere("candidat", session, schema_name):
            raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
        
        # Récupérer la préinscription via requête SQL directe
        pre_query = text(f"""
            SELECT id, candidat_id, programme_id, chiffre_affaires, date_creation_entreprise
            FROM {schema_name}.preinscription
            WHERE id = :pre_id
        """)
        pre_result = session.exec(pre_query.bindparams(pre_id=pre_id)).first()
        if not pre_result:
            logging.error(f"❌ [RECALC] Préinscription {pre_id} introuvable dans le schéma {schema_name}")
            raise HTTPException(status_code=404, detail="Préinscription introuvable")
        
        candidat_id = pre_result.candidat_id if hasattr(pre_result, 'candidat_id') else pre_result[1]
        programme_id = pre_result.programme_id if hasattr(pre_result, 'programme_id') else pre_result[2]
        pre_chiffre_affaires = pre_result.chiffre_affaires if hasattr(pre_result, 'chiffre_affaires') else (pre_result[3] if len(pre_result) > 3 else None)
        pre_date_creation = pre_result.date_creation_entreprise if hasattr(pre_result, 'date_creation_entreprise') else (pre_result[4] if len(pre_result) > 4 else None)
        
        # Récupérer le programme depuis la table public
        prog_query = text("SELECT id, code FROM public.programme WHERE id = :programme_id")
        prog_result = session.exec(prog_query.bindparams(programme_id=programme_id)).first()
        if not prog_result:
            logging.error(f"❌ [RECALC] Programme {programme_id} introuvable")
            raise HTTPException(status_code=404, detail="Programme introuvable")
        prog_id = prog_result.id if hasattr(prog_result, 'id') else prog_result[0]
        prog_code = prog_result.code if hasattr(prog_result, 'code') else prog_result[1]
        
        # Récupérer le candidat via requête SQL directe
        cand_query = text(f"""
            SELECT id, adresse_personnelle
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        cand_result = session.exec(cand_query.bindparams(candidat_id=candidat_id)).first()
        if not cand_result:
            logging.error(f"❌ [RECALC] Candidat {candidat_id} introuvable dans le schéma {schema_name}")
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        adresse_personnelle = cand_result.adresse_personnelle if hasattr(cand_result, 'adresse_personnelle') else (cand_result[1] if len(cand_result) > 1 else None)
        
        # Récupérer l'entreprise via requête SQL directe
        adresse_entreprise = None
        chiffre_affaires = pre_chiffre_affaires
        date_creation_entreprise = pre_date_creation
        
        if table_exists_anywhere("entreprise", session, schema_name):
            ent_query = text(f"""
                SELECT adresse, chiffre_affaires, date_creation
                FROM {schema_name}.entreprise
                WHERE candidat_id = :candidat_id
                LIMIT 1
            """)
            ent_result = session.exec(ent_query.bindparams(candidat_id=candidat_id)).first()
            if ent_result:
                adresse_entreprise = ent_result.adresse if hasattr(ent_result, 'adresse') else (ent_result[0] if len(ent_result) > 0 else None)
                ent_chiffre_affaires = ent_result.chiffre_affaires if hasattr(ent_result, 'chiffre_affaires') else (ent_result[1] if len(ent_result) > 1 else None)
                ent_date_creation = ent_result.date_creation if hasattr(ent_result, 'date_creation') else (ent_result[2] if len(ent_result) > 2 else None)
                chiffre_affaires = ent_chiffre_affaires if ent_chiffre_affaires else pre_chiffre_affaires
                date_creation_entreprise = ent_date_creation if ent_date_creation else pre_date_creation
        
        # Calculer l'ancienneté
        anciennete = entreprise_age_annees(date_creation_entreprise)
        if anciennete is not None:
            anciennete = int(anciennete)
        
        # Convertir le chiffre d'affaires en string si nécessaire
        ca_string = str(chiffre_affaires) if chiffre_affaires else None
        
        logging.info(f"📊 [RECALC] Données - CA: {ca_string}, Ancienneté: {anciennete} ans, Adresse entreprise: {adresse_entreprise}")
        
        # Calculer l'éligibilité avec la nouvelle signature (sauvegarde automatique)
        verdict, details = await evaluate_eligibilite(
            adresse_perso=adresse_personnelle,
            adresse_entreprise=adresse_entreprise,
            chiffre_affaires=ca_string,
            anciennete_annees=anciennete,
            programme_id=prog_id,
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
        redirect_url = f"{redirect_url}?programme={prog_code}&pre_id={pre_id}"
        
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
        
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que les tables existent
        if not table_exists_anywhere("candidat", session, schema_name):
            raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
        if not table_exists_anywhere("document", session, schema_name):
            raise HTTPException(status_code=404, detail="Table document introuvable dans ce programme")
        
        # Vérifier que le candidat existe via requête SQL directe
        candidat_query = text(f"""
            SELECT id
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        if not candidat_result:
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
        
        # Créer l'enregistrement en base via requête SQL directe
        from ..models.enums import TypeDocument
        
        type_doc_value = TypeDocument(type_document).value if type_document in [e.value for e in TypeDocument] else TypeDocument.AUTRE.value
        depose_par_id = current_user.id if current_user else None
        depose_le = datetime.now(timezone.utc)
        
        insert_doc_query = text(f"""
            INSERT INTO {schema_name}.document
            (candidat_id, nom_fichier, chemin_fichier, taille_octets, type_document, titre, mimetype, depose_par_id, depose_le)
            VALUES (:candidat_id, :nom_fichier, :chemin_fichier, :taille_octets, :type_document, :titre, :mimetype, :depose_par_id, :depose_le)
            RETURNING id
        """)
        doc_result = session.exec(insert_doc_query.bindparams(
            candidat_id=candidat_id,
            nom_fichier=document_file.filename,
            chemin_fichier=file_info["relative_path"],
            taille_octets=file_info["size_bytes"],
            type_document=type_doc_value,
            titre=description,
            mimetype=document_file.content_type,
            depose_par_id=depose_par_id,
            depose_le=depose_le
        )).first()
        
        doc_id = doc_result.id if hasattr(doc_result, 'id') else doc_result[0]
        session.commit()
        
        print(f"✅ [DOC] Document ajouté avec succès: {file_info['relative_path']}")
        
        # Retourner une réponse JSON avec message de succès
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Document ajouté avec succès",
                "document_id": doc_id,
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
        
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que la table document existe
        if not table_exists_anywhere("document", session, schema_name):
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Document introuvable dans ce programme"}
            )
        
        # Récupérer le document via requête SQL directe
        doc_query = text(f"""
            SELECT id, candidat_id, chemin_fichier
            FROM {schema_name}.document
            WHERE id = :document_id
        """)
        doc_result = session.exec(doc_query.bindparams(document_id=document_id)).first()
        if not doc_result:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Document introuvable"}
            )
        
        candidat_id = doc_result.candidat_id if hasattr(doc_result, 'candidat_id') else doc_result[1]
        chemin_fichier = doc_result.chemin_fichier if hasattr(doc_result, 'chemin_fichier') else doc_result[2]
        
        # Supprimer le fichier physique via FileUploadService
        if chemin_fichier:
            try:
                FileUploadService.delete_file(chemin_fichier)
                print(f"🗑️ [DOC] Fichier supprimé: {chemin_fichier}")
            except Exception as e:
                print(f"⚠️ [DOC] Erreur lors de la suppression du fichier: {e}")
        
        # Supprimer l'enregistrement en base via requête SQL directe
        delete_doc_query = text(f"""
            DELETE FROM {schema_name}.document
            WHERE id = :document_id
        """)
        session.exec(delete_doc_query.bindparams(document_id=document_id))
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
    # Récupérer et configurer le schéma (même méthode que seminaire.py)
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    
    # Vérifier que la table avancement_etape existe dans le schéma
    if not table_exists_anywhere("avancement_etape", session, schema_name):
        raise HTTPException(status_code=404, detail="Avancement introuvable dans ce programme")
    
    # Récupérer l'avancement via requête SQL directe
    avancement_query = text(f"""
        SELECT id, candidat_id, etape_id, statut, debut_le, termine_le
        FROM {schema_name}.avancement_etape
        WHERE id = :avancement_id
    """)
    av_result = session.exec(avancement_query.bindparams(avancement_id=avancement_id)).first()
    if not av_result:
        raise HTTPException(status_code=404, detail="Avancement introuvable")
    
    try:
        new_status = StatutEtape[statut]
    except Exception:
        raise HTTPException(status_code=400, detail="Statut invalide")

    from datetime import datetime as _dt
    now = _dt.utcnow()
    
    # Construire la requête UPDATE selon le statut
    update_fields = ["statut = :statut"]
    params = {
        "avancement_id": avancement_id,
        "statut": new_status.value
    }
    
    if new_status.name == "EN_COURS":
        # Vérifier si debut_le est déjà défini
        if not av_result.debut_le:
            update_fields.append("debut_le = :debut_le")
            params["debut_le"] = now
    
    if new_status.name == "TERMINE":
        if not av_result.debut_le:
            update_fields.append("debut_le = :debut_le")
            params["debut_le"] = now
        update_fields.append("termine_le = :termine_le")
        params["termine_le"] = now
    
    # Exécuter la mise à jour
    update_query = text(f"""
        UPDATE {schema_name}.avancement_etape
        SET {', '.join(update_fields)}
        WHERE id = :avancement_id
    """)
    session.exec(update_query.bindparams(**params))
    session.commit()
    
    # Récupérer le candidat_id et le programme pour la redirection
    candidat_id = av_result.candidat_id
    
    # Récupérer la préinscription via requête SQL directe
    pre_query = text(f"""
        SELECT id, programme_id
        FROM {schema_name}.preinscription
        WHERE candidat_id = :candidat_id
        LIMIT 1
    """)
    pre_result = session.exec(pre_query.bindparams(candidat_id=candidat_id)).first()
    
    if pre_result:
        prog_query = text("SELECT code FROM public.programme WHERE id = :programme_id")
        prog_result = session.exec(prog_query.bindparams(programme_id=pre_result.programme_id)).first()
        prog_code = prog_result.code if prog_result else programme
        pre_id = pre_result.id
    else:
        prog_code = programme
        pre_id = ''
    
    # Préparer les paramètres de succès avec message
    from urllib.parse import urlencode
    statut_labels = {
        "A_FAIRE": "à faire",
        "EN_COURS": "en cours",
        "TERMINE": "terminé"
    }
    statut_label = statut_labels.get(statut, statut.lower())
    success_message = f"L'étape a été mise à jour avec succès. Statut: {statut_label}."
    
    redirect_url = request.url_for('form_inscriptions_display')
    params = {
        "programme": prog_code,
        "pre_id": pre_id,
        "etape_advance_success": "true",
        "message": success_message
    }
    redirect_url = f"{redirect_url}?{urlencode(params)}"
    
    return RedirectResponse(url=redirect_url, status_code=303)


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
    try:
        if settings.DEBUG:
            logging.info("=" * 80)
            logging.info("🔵 [CREATE_JURY_DECISION] Début de la création d'une décision de jury")
            logging.info(f"🔵 [CREATE_JURY_DECISION] URL: {request.url}")
            logging.info(f"🔵 [CREATE_JURY_DECISION] Méthode: {request.method}")
            logging.info(f"🔵 [CREATE_JURY_DECISION] User: {current_user.id if current_user else 'None'} ({current_user.nom_complet if current_user else 'None'})")
        
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Programme: {programme} → Schéma: {schema_name}")
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Search path configuré: {schema_name}, public")
        
        # Vérifier que les tables existent dans le schéma
        if not table_exists_anywhere("candidat", session, schema_name):
            raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
        if not table_exists_anywhere("decision_jury_candidat", session, schema_name):
            raise HTTPException(status_code=404, detail="Table decision_jury_candidat introuvable dans ce programme")
        
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Données reçues du formulaire:")
            logging.info(f"   - candidat_id: {candidat_id} (type: {type(candidat_id).__name__})")
            logging.info(f"   - jury_id: {jury_id} (type: {type(jury_id).__name__})")
            logging.info(f"   - decision: {decision} (type: {type(decision).__name__})")
            logging.info(f"   - commentaires: {commentaires} (type: {type(commentaires).__name__})")
            logging.info(f"   - conseiller_id: {conseiller_id} (type: {type(conseiller_id).__name__})")
            logging.info(f"   - groupe_id: {groupe_id} (type: {type(groupe_id).__name__})")
            logging.info(f"   - promotion_id: {promotion_id} (type: {type(promotion_id).__name__})")
            logging.info(f"   - partenaire_id: {partenaire_id} (type: {type(partenaire_id).__name__})")
            logging.info(f"   - envoyer_mail_candidat: {envoyer_mail_candidat}")
            logging.info(f"   - envoyer_mail_conseiller: {envoyer_mail_conseiller}")
            logging.info(f"   - envoyer_mail_partenaire: {envoyer_mail_partenaire}")
        
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
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Vérification du groupe ID: {groupe_id_int}")
            groupe = session.get(Groupe, groupe_id_int)
            if not groupe:
                if settings.DEBUG:
                    logging.warning(f"⚠️ [CREATE_JURY_DECISION] Groupe introuvable: {groupe_id} (converti: {groupe_id_int})")
                groupe_id_int = None
            else:
                if settings.DEBUG:
                    logging.info(f"🔵 [CREATE_JURY_DECISION] Groupe trouvé: {groupe.nom}")
        
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] IDs convertis:")
            logging.info(f"   - promotion_id_int: {promotion_id_int}")
            logging.info(f"   - partenaire_id_int: {partenaire_id_int}")
            logging.info(f"   - conseiller_id_int: {conseiller_id_int}")
            logging.info(f"   - groupe_id_int: {groupe_id_int}")
        
        # Vérifier que le candidat existe via requête SQL directe
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Vérification du candidat ID: {candidat_id}")
        candidat_query = text(f"""
            SELECT id, nom, prenom, statut
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        if not candidat_result:
            logging.error(f"❌ [CREATE_JURY_DECISION] Candidat introuvable: {candidat_id}")
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Candidat trouvé: {candidat_result.nom} {candidat_result.prenom} (ID: {candidat_result.id})")
        
        # Vérifier que le jury existe (si fourni)
        jury = None
        if jury_id:
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Vérification du jury ID: {jury_id}")
            # Jury est dans le schéma public, utiliser une requête SQL directe avec schéma explicite
            # Configurer temporairement le search_path vers public pour s'assurer que la requête fonctionne
            session.exec(text("SET search_path TO public, public"))
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Search_path temporairement configuré vers 'public'")
            
            jury_query = text("""
                SELECT id, programme_id, promotion_id, session_le, lieu, statut
                FROM public.jury
                WHERE id = :jury_id
            """)
            # Utiliser bindparams pour passer les paramètres
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Exécution de la requête SQL pour jury_id={jury_id}")
            jury_result = session.exec(jury_query.bindparams(jury_id=jury_id)).first()
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Résultat de la requête: {jury_result}")
                logging.info(f"🔵 [CREATE_JURY_DECISION] Type du résultat: {type(jury_result)}")
            
            # Restaurer le search_path pour le schéma du programme
            session.exec(text(f"SET search_path TO {schema_name}, public"))
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Search_path restauré vers '{schema_name}, public'")
            
            if not jury_result:
                logging.error(f"❌ [CREATE_JURY_DECISION] Jury introuvable: {jury_id}")
                raise HTTPException(status_code=404, detail="Jury introuvable")
            
            # Convertir le résultat en dictionnaire
            if hasattr(jury_result, '_mapping'):
                jury = dict(jury_result._mapping)
            elif hasattr(jury_result, '__dict__'):
                jury = dict(jury_result.__dict__)
            else:
                # Si c'est un tuple, le convertir en dict
                jury = {
                    "id": jury_result[0] if len(jury_result) > 0 else None,
                    "programme_id": jury_result[1] if len(jury_result) > 1 else None,
                    "promotion_id": jury_result[2] if len(jury_result) > 2 else None,
                    "session_le": jury_result[3] if len(jury_result) > 3 else None,
                    "lieu": jury_result[4] if len(jury_result) > 4 else None,
                    "statut": jury_result[5] if len(jury_result) > 5 else None,
                }
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Jury trouvé: Session du {jury.get('session_le')} - {jury.get('lieu')}")
        
        # Vérifier s'il existe déjà une décision pour ce candidat et ce jury via requête SQL directe
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Vérification d'une décision existante pour candidat_id={candidat_id}, jury_id={jury_id}")
        existing_query = text(f"""
            SELECT id
            FROM {schema_name}.decision_jury_candidat
            WHERE candidat_id = :candidat_id AND jury_id = :jury_id
        """)
        existing_result = session.exec(existing_query.bindparams(
            candidat_id=candidat_id,
            jury_id=jury_id
        )).first()
        
        if existing_result:
            existing_id = existing_result.id if hasattr(existing_result, 'id') else existing_result[0]
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Une décision existe déjà pour ce candidat et ce jury (ID: {existing_id}), suppression de l'ancienne décision")
            # Supprimer les réorientations associées à l'ancienne décision via requête SQL directe
            if table_exists_anywhere("reorientation_candidat", session, schema_name):
                delete_reorientations_query = text(f"""
                    DELETE FROM {schema_name}.reorientation_candidat
                    WHERE decision_jury_id = :decision_id
                """)
                session.exec(delete_reorientations_query.bindparams(decision_id=existing_id))
            # Supprimer l'ancienne décision via requête SQL directe
            delete_existing_query = text(f"""
                DELETE FROM {schema_name}.decision_jury_candidat
                WHERE id = :decision_id
            """)
            session.exec(delete_existing_query.bindparams(decision_id=existing_id))
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Ancienne décision supprimée, création de la nouvelle")
        else:
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Aucune décision existante trouvée, création possible")
        
        # Créer la décision via requête SQL directe
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Création de la décision via SQL direct")
        
        from datetime import datetime as _dt
        now = _dt.utcnow()
        
        # Préparer les valeurs pour l'INSERT
        decision_value = DecisionJury(decision).value
        conseiller_id_val = conseiller_id_int if decision == DecisionJury.VALIDE.value else None
        groupe_id_val = groupe_id_int if decision == DecisionJury.VALIDE.value else None
        promotion_id_val = promotion_id_int if decision == DecisionJury.VALIDE.value else None
        partenaire_id_val = partenaire_id_int if decision == DecisionJury.REORIENTE.value else None
        
        # Insérer la décision via requête SQL directe
        insert_decision_query = text(f"""
            INSERT INTO {schema_name}.decision_jury_candidat
            (candidat_id, jury_id, decision, commentaires, conseiller_id, groupe_id, promotion_id, partenaire_id,
             envoyer_mail_candidat, envoyer_mail_conseiller, envoyer_mail_partenaire, date_decision)
            VALUES (:candidat_id, :jury_id, :decision, :commentaires, :conseiller_id, :groupe_id, :promotion_id, :partenaire_id,
                    :envoyer_mail_candidat, :envoyer_mail_conseiller, :envoyer_mail_partenaire, :date_decision)
            RETURNING id
        """)
        decision_result = session.exec(insert_decision_query.bindparams(
            candidat_id=candidat_id,
            jury_id=jury_id,
            decision=decision_value,
            commentaires=commentaires,
            conseiller_id=conseiller_id_val,
            groupe_id=groupe_id_val,
            promotion_id=promotion_id_val,
            partenaire_id=partenaire_id_val,
            envoyer_mail_candidat=envoyer_mail_candidat,
            envoyer_mail_conseiller=envoyer_mail_conseiller,
            envoyer_mail_partenaire=envoyer_mail_partenaire,
            date_decision=now
        )).first()
        
        decision_id = decision_result.id if hasattr(decision_result, 'id') else decision_result[0]
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Décision créée, ID généré: {decision_id}")
        
        # Mettre à jour le statut du candidat via requête SQL directe
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Mise à jour du statut du candidat: {candidat_result.statut if hasattr(candidat_result, 'statut') else 'N/A'} → {decision}")
        update_candidat_query = text(f"""
            UPDATE {schema_name}.candidat
            SET statut = :statut
            WHERE id = :candidat_id
        """)
        session.exec(update_candidat_query.bindparams(
            statut=decision_value,
            candidat_id=candidat_id
        ))
        
        # Créer ou réactiver le compte User si le candidat est validé
        if decision == DecisionJury.VALIDE.value:
            user = _create_user_for_candidat(session, candidat_id, schema_name)
            if user and settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Compte User créé/réactivé pour candidat {candidat_id}")
        elif decision in [DecisionJury.REFUSE.value, DecisionJury.REORIENTE.value]:
            # Désactiver le compte User si le candidat est refusé ou réorienté
            _deactivate_user_for_candidat(session, candidat_id, schema_name)
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Compte User désactivé pour candidat {candidat_id} (décision: {decision})")
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Statut du candidat mis à jour: {decision_value}")
        
        # Si réorienté, créer l'enregistrement de réorientation via requête SQL directe
        if decision == DecisionJury.REORIENTE.value and partenaire_id_int:
            if settings.DEBUG:
                logging.info(f"🔵 [CREATE_JURY_DECISION] Décision REORIENTE, création de l'enregistrement de réorientation")
            if table_exists_anywhere("reorientation_candidat", session, schema_name):
                insert_reorientation_query = text(f"""
                    INSERT INTO {schema_name}.reorientation_candidat
                    (candidat_id, partenaire_id, decision_jury_id, mail_envoye)
                    VALUES (:candidat_id, :partenaire_id, :decision_jury_id, :mail_envoye)
                """)
                session.exec(insert_reorientation_query.bindparams(
                    candidat_id=candidat_id,
                    partenaire_id=partenaire_id_int,
                    decision_jury_id=decision_id,
                    mail_envoye=envoyer_mail_partenaire
                ))
                if settings.DEBUG:
                    logging.info(f"🔵 [CREATE_JURY_DECISION] Réorientation créée pour partenaire_id: {partenaire_id_int}")
        
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Commit de la transaction")
        session.commit()
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] ✅ Transaction commitée avec succès")
        
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
            entity_id=decision_id,
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
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Préparation de la redirection")
        # Récupérer la préinscription via requête SQL directe
        pre_query = text(f"""
            SELECT id
            FROM {schema_name}.preinscription
            WHERE candidat_id = :candidat_id
            LIMIT 1
        """)
        pre_result = session.exec(pre_query.bindparams(candidat_id=candidat_id)).first()
        pre_id = pre_result.id if pre_result and hasattr(pre_result, 'id') else (pre_result[0] if pre_result else '')
        
        prog_query = text("SELECT code FROM public.programme WHERE code = :programme_code")
        prog_result = session.exec(prog_query.bindparams(programme_code=programme.upper())).first()
        prog_code = prog_result.code if prog_result and hasattr(prog_result, 'code') else (prog_result[0] if prog_result else programme)
        
        from urllib.parse import urlencode
        
        # Préparer les paramètres de succès
        decision_labels = {
            DecisionJury.VALIDE.value: "validé",
            DecisionJury.REORIENTE.value: "réorienté",
            DecisionJury.REJETE.value: "rejeté",
            DecisionJury.EN_ATTENTE.value: "mis en attente"
        }
        decision_label = decision_labels.get(decision, "traité")
        success_message = f"La décision de jury a été enregistrée avec succès. Le candidat a été {decision_label}."
        
        redirect_url = request.url_for('form_inscriptions_display')
        params = {
            "programme": prog_code,
            "pre_id": pre_id,
            "jury_decision_success": "true",
            "message": success_message
        }
        redirect_url = f"{redirect_url}?{urlencode(params)}"
        
        if settings.DEBUG:
            logging.info(f"🔵 [CREATE_JURY_DECISION] Redirection vers: {redirect_url}")
            logging.info("=" * 80)
        return RedirectResponse(url=redirect_url, status_code=303)
    
    except HTTPException as e:
        logging.error(f"❌ [CREATE_JURY_DECISION] HTTPException: {e.status_code} - {e.detail}")
        if settings.DEBUG:
            logging.info("=" * 80)
        
        # Rediriger avec un message d'erreur
        try:
            from urllib.parse import urlencode
            pre_query = text(f"""
                SELECT id
                FROM {schema_name}.preinscription
                WHERE candidat_id = :candidat_id
                LIMIT 1
            """)
            pre_result = session.exec(pre_query.bindparams(candidat_id=candidat_id)).first()
            pre_id = pre_result.id if pre_result and hasattr(pre_result, 'id') else (pre_result[0] if pre_result else '')
            
            redirect_url = request.url_for('form_inscriptions_display')
            params = {
                "programme": programme,
                "pre_id": pre_id,
                "jury_decision_success": "false",
                "message": str(e.detail) if e.detail else f"Erreur HTTP {e.status_code}",
                "error_type": "HTTPException"
            }
            redirect_url = f"{redirect_url}?{urlencode(params)}"
            return RedirectResponse(url=redirect_url, status_code=303)
        except:
            raise
    
    except Exception as e:
        logging.error(f"❌ [CREATE_JURY_DECISION] Erreur inattendue: {type(e).__name__}: {str(e)}")
        logging.error(f"❌ [CREATE_JURY_DECISION] Traceback complet:")
        import traceback
        logging.error(traceback.format_exc())
        if settings.DEBUG:
            logging.info("=" * 80)
        session.rollback()
        
        # Rediriger avec un message d'erreur
        try:
            from urllib.parse import urlencode
            pre_query = text(f"""
                SELECT id
                FROM {schema_name}.preinscription
                WHERE candidat_id = :candidat_id
                LIMIT 1
            """)
            pre_result = session.exec(pre_query.bindparams(candidat_id=candidat_id)).first()
            pre_id = pre_result.id if pre_result and hasattr(pre_result, 'id') else (pre_result[0] if pre_result else '')
            
            redirect_url = request.url_for('form_inscriptions_display')
            params = {
                "programme": programme,
                "pre_id": pre_id,
                "jury_decision_success": "false",
                "message": f"Erreur lors de la création de la décision: {str(e)}",
                "error_type": type(e).__name__
            }
            redirect_url = f"{redirect_url}?{urlencode(params)}"
            return RedirectResponse(url=redirect_url, status_code=303)
        except:
            raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la décision: {str(e)}")


@router.post("/jury/decision/{decision_id}/delete", name="delete_jury_decision_inscription")
def delete_jury_decision(
    request: Request,
    decision_id: int,
    programme: Optional[str] = Form(None),  # Paramètre programme optionnel
    session: Session = Depends(get_shared_session),
    current_user=Depends(get_current_user),
    schema_routing_service = Depends(get_schema_routing_service),
):
    """Supprimer une décision du jury"""
    
    # Récupérer et configurer le schéma (même méthode que seminaire.py)
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    
    # Vérifier que la table decision_jury_candidat existe dans le schéma
    if not table_exists_anywhere("decision_jury_candidat", session, schema_name):
        raise HTTPException(status_code=404, detail="Décision introuvable dans ce programme")
    
    # Récupérer la décision via requête SQL directe
    decision_query = text(f"""
        SELECT id, candidat_id, jury_id, decision, commentaires, date_decision
        FROM {schema_name}.decision_jury_candidat
        WHERE id = :decision_id
    """)
    decision_result = session.exec(decision_query.bindparams(decision_id=decision_id)).first()
    if not decision_result:
        raise HTTPException(status_code=404, detail="Décision introuvable")
    
    candidat_id = decision_result.candidat_id
    decision_value = decision_result.decision if hasattr(decision_result, 'decision') else decision_result[3]
    
    # Désactiver le compte User si le candidat était validé
    if decision_value == DecisionJury.VALIDE.value:
        _deactivate_user_for_candidat(session, candidat_id, schema_name)
        if settings.DEBUG:
            logging.info(f"🔵 [DELETE_JURY_DECISION] Compte User désactivé pour candidat {candidat_id} (décision supprimée)")
    
    # Remettre le candidat en attente via requête SQL directe
    if table_exists_anywhere("candidat", session, schema_name):
        update_candidat_query = text(f"""
            UPDATE {schema_name}.candidat
            SET statut = :statut
            WHERE id = :candidat_id
        """)
        session.exec(update_candidat_query.bindparams(
            statut=DecisionJury.EN_ATTENTE.value,
            candidat_id=candidat_id
        ))
    
    # Supprimer les réorientations associées via requête SQL directe
    if table_exists_anywhere("reorientation_candidat", session, schema_name):
        delete_reorientations_query = text(f"""
            DELETE FROM {schema_name}.reorientation_candidat
            WHERE decision_jury_id = :decision_id
        """)
        session.exec(delete_reorientations_query.bindparams(decision_id=decision_id))
    
    # Supprimer la décision via requête SQL directe
    delete_decision_query = text(f"""
        DELETE FROM {schema_name}.decision_jury_candidat
        WHERE id = :decision_id
    """)
    session.exec(delete_decision_query.bindparams(decision_id=decision_id))
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
    
    # Récupérer le programme pour la redirection
    if programme:
        prog_code = programme
    else:
        # Récupérer depuis la préinscription
        preinscription_query = text(f"""
            SELECT programme_id
            FROM {schema_name}.preinscription
            WHERE candidat_id = :candidat_id
            LIMIT 1
        """)
        pre_result = session.exec(preinscription_query.bindparams(candidat_id=candidat_id)).first()
        if pre_result:
            prog_query = text("SELECT code FROM public.programme WHERE id = :programme_id")
            prog_result = session.exec(prog_query.bindparams(programme_id=pre_result.programme_id)).first()
            prog_code = prog_result.code if prog_result else 'acd'
        else:
            prog_code = 'acd'
    
    # Récupérer la préinscription pour la redirection
    pre_query = text(f"""
        SELECT id
        FROM {schema_name}.preinscription
        WHERE candidat_id = :candidat_id
        LIMIT 1
    """)
    pre_result = session.exec(pre_query.bindparams(candidat_id=candidat_id)).first()
    pre_id = pre_result.id if pre_result else ''
    
    # Préparer les paramètres de succès avec message
    from urllib.parse import urlencode
    redirect_url = request.url_for('form_inscriptions_display')
    params = {
        "programme": prog_code,
        "pre_id": pre_id,
        "jury_decision_deleted": "true",
        "message": "La décision de jury a été supprimée avec succès. Le candidat est maintenant en attente."
    }
    redirect_url = f"{redirect_url}?{urlencode(params)}"
    
    return RedirectResponse(url=redirect_url, status_code=303)


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
    
    # Récupérer et configurer le schéma (même méthode que seminaire.py)
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    
    # Vérifier que les tables existent
    if not table_exists_anywhere("candidat", session, schema_name):
        raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
    
    # Récupérer le candidat via requête SQL directe
    candidat_query = text(f"""
        SELECT id, adresse_personnelle
        FROM {schema_name}.candidat
        WHERE id = :candidat_id
    """)
    candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
    if not candidat_result:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Récupérer les adresses depuis la base si non fournies
    if not adresse_personnelle:
        adresse_personnelle = candidat_result.adresse_personnelle if hasattr(candidat_result, 'adresse_personnelle') else (candidat_result[1] if len(candidat_result) > 1 else None)
    
    if not adresse_entreprise and table_exists_anywhere("entreprise", session, schema_name):
        entreprise_query = text(f"""
            SELECT adresse
            FROM {schema_name}.entreprise
            WHERE candidat_id = :candidat_id
            LIMIT 1
        """)
        entreprise_result = session.exec(entreprise_query.bindparams(candidat_id=candidat_id)).first()
        if entreprise_result:
            adresse_entreprise = entreprise_result.adresse if hasattr(entreprise_result, 'adresse') else (entreprise_result[0] if len(entreprise_result) > 0 else None)
    
    # 🔍 VÉRIFICATION PRÉALABLE : Recherche existante ?
    preinscription_id = None
    if table_exists_anywhere("preinscription", session, schema_name):
        preinscription_query = text(f"""
            SELECT id
            FROM {schema_name}.preinscription
            WHERE candidat_id = :candidat_id
            LIMIT 1
        """)
        preinscription_result = session.exec(preinscription_query.bindparams(candidat_id=candidat_id)).first()
        if preinscription_result:
            preinscription_id = preinscription_result.id if hasattr(preinscription_result, 'id') else preinscription_result[0]
    
    if preinscription_id and table_exists_anywhere("eligibilite", session, schema_name):
        eligibilite_query = text(f"""
            SELECT qpv_ok, details_json
            FROM {schema_name}.eligibilite
            WHERE preinscription_id = :preinscription_id
            LIMIT 1
        """)
        eligibilite_result = session.exec(eligibilite_query.bindparams(preinscription_id=preinscription_id)).first()
        
        # Si une vérification QPV existe déjà et les adresses n'ont pas changé
        if eligibilite_result:
            eligibilite_qpv_ok = eligibilite_result.qpv_ok if hasattr(eligibilite_result, 'qpv_ok') else (eligibilite_result[0] if len(eligibilite_result) > 0 else None)
            eligibilite_details_json = eligibilite_result.details_json if hasattr(eligibilite_result, 'details_json') else (eligibilite_result[1] if len(eligibilite_result) > 1 else None)
            
            if eligibilite_qpv_ok is not None and eligibilite_details_json:
                try:
                    import json
                    import ast
                    
                    print(f"🔍 [QPV] Données existantes trouvées pour candidat {candidat_id}")
                    print(f"🔍 [QPV] QPV OK: {eligibilite_qpv_ok}")
                    
                    # Essayer de parser le JSON
                    try:
                        details_existants = json.loads(eligibilite_details_json)
                        print(f"🔍 [QPV] JSON parsé avec succès")
                    except json.JSONDecodeError:
                        # Si JSON échoue, essayer de parser comme un dict Python (ancien format)
                        try:
                            details_existants = ast.literal_eval(eligibilite_details_json)
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
                                "statut_qpv_final": "QPV" if eligibilite_qpv_ok and eligibilite_qpv_ok.startswith("QPV") else "NON_QPV",
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
            print(f"⚠️ [QPV] Pas de données en cache - eligibilite: {bool(eligibilite_result)}, qpv_ok: {eligibilite_qpv_ok if eligibilite_result else None}")
    
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
            preinscription_id_for_qpv = preinscription_id
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
            preinscription_id_for_qpv = preinscription_id
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
    
    # Mettre à jour l'éligibilité du candidat via requête SQL directe
    if preinscription_id and table_exists_anywhere("eligibilite", session, schema_name):
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
        
        # Vérifier si l'éligibilité existe déjà
        check_eligibilite_query = text(f"""
            SELECT id
            FROM {schema_name}.eligibilite
            WHERE preinscription_id = :preinscription_id
            LIMIT 1
        """)
        eligibilite_existante = session.exec(check_eligibilite_query.bindparams(preinscription_id=preinscription_id)).first()
        
        if eligibilite_existante:
            # Mise à jour
            update_eligibilite_query = text(f"""
                UPDATE {schema_name}.eligibilite
                SET qpv_ok = :qpv_ok,
                    qpv_carte_url = :qpv_carte_url,
                    qpv_image_url = :qpv_image_url,
                    details_json = :details_json,
                    calcule_le = NOW()
                WHERE preinscription_id = :preinscription_id
            """)
            session.exec(update_eligibilite_query.bindparams(
                qpv_ok=qpv_nom_final,
                qpv_carte_url=qpv_carte_url_final,
                qpv_image_url=qpv_image_url_final,
                details_json=json.dumps(results_light),
                preinscription_id=preinscription_id
            ))
        else:
            # Insertion
            insert_eligibilite_query = text(f"""
                INSERT INTO {schema_name}.eligibilite
                (preinscription_id, qpv_ok, qpv_carte_url, qpv_image_url, details_json, calcule_le)
                VALUES (:preinscription_id, :qpv_ok, :qpv_carte_url, :qpv_image_url, :details_json, NOW())
            """)
            session.exec(insert_eligibilite_query.bindparams(
                preinscription_id=preinscription_id,
                qpv_ok=qpv_nom_final,
                qpv_carte_url=qpv_carte_url_final,
                qpv_image_url=qpv_image_url_final,
                details_json=json.dumps(results_light)
            ))
        
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
    
    # Récupérer et configurer le schéma (même méthode que seminaire.py)
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    
    # Vérifier que les tables existent
    if not table_exists_anywhere("candidat", session, schema_name):
        raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
    
    # Vérifier que le candidat existe via requête SQL directe
    candidat_query = text(f"""
        SELECT id
        FROM {schema_name}.candidat
        WHERE id = :candidat_id
    """)
    candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
    if not candidat_result:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    try:
        print(f"🔍 [SIRET] Recherche SIRET: {numero_siret}")
        
        # Valider le format SIRET
        siret_request = SiretRequest(numero_siret=numero_siret)
        
        # Appeler le service SIRET
        siret_info = await get_entreprise_process(siret_request.numero_siret[:9], request)
        
        # Mettre à jour les informations de l'entreprise via requête SQL directe
        if siret_info.get("entreprise_data"):
            data = siret_info["entreprise_data"]
            
            # Vérifier si l'entreprise existe
            entreprise_query = text(f"""
                SELECT id
                FROM {schema_name}.entreprise
                WHERE candidat_id = :candidat_id
                LIMIT 1
            """)
            entreprise_result = session.exec(entreprise_query.bindparams(candidat_id=candidat_id)).first()
            
            siege = data.get("siege", {})
            siret_value = siege.get("siret")
            siren_value = data.get("siren")
            raison_sociale_value = data.get("nom_entreprise")
            code_naf_value = data.get("code_naf")
            date_creation_value = data.get("date_creation")
            adresse_value = siege.get("adresse")
            lat_value = siege.get("latitude")
            lng_value = siege.get("longitude")
            
            if entreprise_result:
                # Mise à jour
                entreprise_id = entreprise_result.id if hasattr(entreprise_result, 'id') else entreprise_result[0]
                update_entreprise_query = text(f"""
                    UPDATE {schema_name}.entreprise
                    SET siret = :siret,
                        siren = :siren,
                        raison_sociale = :raison_sociale,
                        code_naf = :code_naf,
                        date_creation = :date_creation,
                        adresse = :adresse,
                        lat = :lat,
                        lng = :lng
                    WHERE id = :entreprise_id
                """)
                session.exec(update_entreprise_query.bindparams(
                    siret=siret_value,
                    siren=siren_value,
                    raison_sociale=raison_sociale_value,
                    code_naf=code_naf_value,
                    date_creation=date_creation_value,
                    adresse=adresse_value,
                    lat=lat_value,
                    lng=lng_value,
                    entreprise_id=entreprise_id
                ))
            else:
                # Insertion
                insert_entreprise_query = text(f"""
                    INSERT INTO {schema_name}.entreprise
                    (candidat_id, siret, siren, raison_sociale, code_naf, date_creation, adresse, lat, lng)
                    VALUES (:candidat_id, :siret, :siren, :raison_sociale, :code_naf, :date_creation, :adresse, :lat, :lng)
                """)
                session.exec(insert_entreprise_query.bindparams(
                    candidat_id=candidat_id,
                    siret=siret_value,
                    siren=siren_value,
                    raison_sociale=raison_sociale_value,
                    code_naf=code_naf_value,
                    date_creation=date_creation_value,
                    adresse=adresse_value,
                    lat=lat_value,
                    lng=lng_value
                ))
            
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
    
    # Récupérer et configurer le schéma (même méthode que seminaire.py)
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    
    # Vérifier que les tables existent
    if not table_exists_anywhere("candidat", session, schema_name):
        raise HTTPException(status_code=404, detail="Candidat introuvable dans ce programme")
    
    # Vérifier que le candidat existe via requête SQL directe
    candidat_query = text(f"""
        SELECT id
        FROM {schema_name}.candidat
        WHERE id = :candidat_id
    """)
    candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
    if not candidat_result:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    
    # Récupérer la préinscription via requête SQL directe
    preinscription_id = None
    if table_exists_anywhere("preinscription", session, schema_name):
        preinscription_query = text(f"""
            SELECT id
            FROM {schema_name}.preinscription
            WHERE candidat_id = :candidat_id
            LIMIT 1
        """)
        preinscription_result = session.exec(preinscription_query.bindparams(candidat_id=candidat_id)).first()
        if preinscription_result:
            preinscription_id = preinscription_result.id if hasattr(preinscription_result, 'id') else preinscription_result[0]
    
    if not preinscription_id:
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    # Récupérer l'éligibilité via requête SQL directe
    if not table_exists_anywhere("eligibilite", session, schema_name):
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    eligibilite_query = text(f"""
        SELECT qpv_ok, details_json, calcule_le
        FROM {schema_name}.eligibilite
        WHERE preinscription_id = :preinscription_id
        LIMIT 1
    """)
    eligibilite_result = session.exec(eligibilite_query.bindparams(preinscription_id=preinscription_id)).first()
    
    if not eligibilite_result:
        return {"statut_qpv": "NON_DETERMINE", "details": None}
    
    qpv_ok = eligibilite_result.qpv_ok if hasattr(eligibilite_result, 'qpv_ok') else (eligibilite_result[0] if len(eligibilite_result) > 0 else None)
    details_json = eligibilite_result.details_json if hasattr(eligibilite_result, 'details_json') else (eligibilite_result[1] if len(eligibilite_result) > 1 else None)
    calcule_le = eligibilite_result.calcule_le if hasattr(eligibilite_result, 'calcule_le') else (eligibilite_result[2] if len(eligibilite_result) > 2 else None)
    
    # Vérifier si qpv_ok contient "QPV" (peut être "QPV:nom" ou "Aucun QPV")
    qpv_status = "QPV" if qpv_ok and qpv_ok.startswith("QPV") else "NON_QPV"
    
    return {
        "statut_qpv": qpv_status,
        "details": details_json,
        "derniere_verification": calcule_le.isoformat() if calcule_le else None
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
        
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que les tables existent
        if not table_exists_anywhere("candidat", session, schema_name):
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Candidat introuvable dans ce programme"}
            )
        if not table_exists_anywhere("document", session, schema_name):
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Table document introuvable dans ce programme"}
            )
        
        # Vérifier que le token n'est pas vide
        if not token.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Token de téléchargement invalide"}
            )
        
        # Vérifier que le candidat existe via requête SQL directe
        candidat_query = text(f"""
            SELECT id
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        if not candidat_result:
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
        
        # Créer l'enregistrement en base de données via requête SQL directe
        from ..models.enums import TypeDocument
        
        type_doc_value = TypeDocument(type_document).value if type_document in [e.value for e in TypeDocument] else TypeDocument.AUTRE.value
        depose_par_id = current_user.id if current_user else None
        depose_le = datetime.now(timezone.utc)
        
        insert_document_query = text(f"""
            INSERT INTO {schema_name}.document
            (candidat_id, nom_fichier, chemin_fichier, type_document, taille_octets, depose_par_id, depose_le)
            VALUES (:candidat_id, :nom_fichier, :chemin_fichier, :type_document, :taille_octets, :depose_par_id, :depose_le)
            RETURNING id
        """)
        document_result = session.exec(insert_document_query.bindparams(
            candidat_id=candidat_id,
            nom_fichier=nom_fichier,
            chemin_fichier=file_info["relative_path"],
            type_document=type_doc_value,
            taille_octets=file_info["size_bytes"],
            depose_par_id=depose_par_id,
            depose_le=depose_le
        )).first()
        
        document_id = document_result.id if hasattr(document_result, 'id') else document_result[0]
        session.commit()
        
        print(f"✅ [SIRET DOC] Document enregistré en base: ID {document_id}")
        print(f"📋 [SIRET DOC] Détails du document:")
        print(f"   - Candidat ID: {candidat_id}")
        print(f"   - Nom fichier: {nom_fichier}")
        print(f"   - Type document: {type_doc_value}")
        print(f"   - Chemin: {file_info['relative_path']}")
        print(f"   - Taille: {file_info['size_bytes']} bytes")
        
        # Vérification immédiate que le document existe en base
        verification_query = text(f"""
            SELECT id
            FROM {schema_name}.document
            WHERE id = :document_id
        """)
        verification = session.exec(verification_query.bindparams(document_id=document_id)).first()
        if verification:
            print(f"✅ [SIRET DOC] Vérification OK: Document {document_id} trouvé en base")
        else:
            print(f"❌ [SIRET DOC] ERREUR: Document {document_id} non trouvé en base")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True, 
                "message": f"Document '{nom_fichier}' téléchargé et ajouté avec succès",
                "document_id": document_id,
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
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que la table document existe
        if not table_exists_anywhere("document", session, schema_name):
            raise HTTPException(status_code=404, detail="Document introuvable dans ce programme")
        
        # Récupérer le document via requête SQL directe
        doc_query = text(f"""
            SELECT id, nom_fichier, chemin_fichier
            FROM {schema_name}.document
            WHERE id = :document_id
        """)
        doc_result = session.exec(doc_query.bindparams(document_id=document_id)).first()
        if not doc_result:
            raise HTTPException(status_code=404, detail="Document introuvable")
        
        nom_fichier = doc_result.nom_fichier if hasattr(doc_result, 'nom_fichier') else (doc_result[1] if len(doc_result) > 1 else '')
        chemin_fichier = doc_result.chemin_fichier if hasattr(doc_result, 'chemin_fichier') else (doc_result[2] if len(doc_result) > 2 else '')
        
        # Utiliser FileUploadService pour servir le fichier
        try:
            return FileUploadService.serve_file(chemin_fichier)
        except HTTPException:
            # Fallback vers l'ancien système si FileUploadService échoue
            from pathlib import Path
            file_path = path_config.UPLOAD_DIR / chemin_fichier
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
                    "Content-Disposition": f"inline; filename={nom_fichier}",
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
        # Récupérer et configurer le schéma (même méthode que seminaire.py)
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que la table document existe
        if not table_exists_anywhere("document", session, schema_name):
            raise HTTPException(status_code=404, detail="Document introuvable dans ce programme")
        
        # Récupérer le document via requête SQL directe
        doc_query = text(f"""
            SELECT id, nom_fichier, chemin_fichier
            FROM {schema_name}.document
            WHERE id = :document_id
        """)
        doc_result = session.exec(doc_query.bindparams(document_id=document_id)).first()
        if not doc_result:
            raise HTTPException(status_code=404, detail="Document introuvable")
        
        nom_fichier = doc_result.nom_fichier if hasattr(doc_result, 'nom_fichier') else (doc_result[1] if len(doc_result) > 1 else '')
        chemin_fichier = doc_result.chemin_fichier if hasattr(doc_result, 'chemin_fichier') else (doc_result[2] if len(doc_result) > 2 else '')
        
        # Utiliser FileUploadService pour servir le fichier
        try:
            return FileUploadService.serve_file(chemin_fichier)
        except HTTPException:
            # Fallback vers l'ancien système si FileUploadService échoue
            from fastapi.responses import FileResponse
            file_path = path_config.get_physical_path("files", chemin_fichier)
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Fichier introuvable")
            
            return FileResponse(
                path=str(file_path),
                filename=nom_fichier,
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

# ===== PROMOTIONS =====
@router.get("/promotions", response_class=HTMLResponse, name="admin_promotions")
def admin_promotions(
    request: Request, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user), 
    q: Optional[str] = Query(None)):
    
    admin_required(current_user)
    request.state.admin_title = "Gestion des promotions"
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les promotions du schéma du programme avec SQL direct
    promotions_query = text(f"""
        SELECT 
            id,
            libelle,
            programme_id,
            capacite,
            date_debut,
            date_fin,
            actif
        FROM {schema_name}.promotion
        {"WHERE libelle ILIKE :q" if q else ""}
        ORDER BY libelle
    """)
    
    params = {}
    if q:
        params['q'] = f"%{q}%"
    
    promotions_results = session.exec(promotions_query.bindparams(**params) if params else promotions_query).all()
    
    # Convertir en objets simples avec relation programme
    promotions = []
    for row in promotions_results:
        promo_dict = dict(row._mapping)
        # Récupérer le programme depuis public.programme
        programme_query = text("SELECT id, code, nom FROM public.programme WHERE id = :programme_id")
        programme_result = session.exec(programme_query.bindparams(programme_id=promo_dict['programme_id'])).first()
        if programme_result:
            promo_dict['programme'] = type('Programme', (), dict(programme_result._mapping))()
        else:
            promo_dict['programme'] = None
        promotions.append(type('Promotion', (), promo_dict)())
    
    # Récupérer tous les programmes pour les dropdowns (depuis public)
    programmes_query = text("SELECT id, code, nom FROM public.programme WHERE actif = true ORDER BY code")
    programmes_results = session.exec(programmes_query).all()
    programmes = [type('Programme', (), dict(row._mapping))() for row in programmes_results]
    
    # Récupérer le programme actuel correspondant au schéma
    current_programme = None
    programme_code = schema_name.upper()  # Le schéma correspond généralement au code du programme
    current_programme_query = text("SELECT id, code, nom FROM public.programme WHERE LOWER(code) = :schema_name OR code = :programme_code LIMIT 1")
    current_programme_result = session.exec(current_programme_query.bindparams(schema_name=schema_name, programme_code=programme_code)).first()
    if current_programme_result:
        current_programme = type('Programme', (), dict(current_programme_result._mapping))()
    
    return templates.TemplateResponse("pages/programme/promotions.html", {
        "request": request, 
        "settings": settings, 
        "utilisateur": current_user, 
        "promotions": promotions, 
        "programmes": programmes,
        "current_programme": current_programme,
        "q": q or ""
    })

@router.post("/promotions/add")
def admin_promotions_add(
    programme_id: int = Form(...),
    libelle: str = Form(...), 
    capacite: Optional[str] = Form(None),
    date_debut: Optional[str] = Form(None),
    date_fin: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    request: Request = None, 
    session: Session = Depends(get_shared_session), 
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Vérifier que le programme existe dans public.programme
    programme_query = text("SELECT id, code, nom FROM public.programme WHERE id = :programme_id AND actif = true")
    programme_result = session.exec(programme_query.bindparams(programme_id=programme_id)).first()
    if not programme_result:
        raise HTTPException(status_code=400, detail="Programme introuvable")
    
    # Vérifier si une promotion avec ce libellé existe déjà pour ce programme
    existing_query = text(f"""
        SELECT id FROM {schema_name}.promotion 
        WHERE programme_id = :programme_id AND libelle = :libelle
    """)
    existing = session.exec(existing_query.bindparams(
        programme_id=programme_id,
        libelle=libelle.strip()
    )).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une promotion avec ce libellé existe déjà pour ce programme")
    
    # Préparer les valeurs pour l'insertion
    capacite_val = int(capacite) if capacite and capacite.strip().isdigit() else None
    date_debut_val = datetime.fromisoformat(date_debut).date() if date_debut else None
    date_fin_val = datetime.fromisoformat(date_fin).date() if date_fin else None
    actif_val = (actif != "off")
    
    # Insertion SQL directe
    insert_query = text(f"""
        INSERT INTO {schema_name}.promotion 
        (programme_id, libelle, capacite, date_debut, date_fin, actif)
        VALUES (:programme_id, :libelle, :capacite, :date_debut, :date_fin, :actif)
        RETURNING id
    """)
    
    result = session.exec(insert_query.bindparams(
        programme_id=programme_id,
        libelle=libelle.strip(),
        capacite=capacite_val,
        date_debut=date_debut_val,
        date_fin=date_fin_val,
        actif=actif_val
    )).first()
    
    promotion_id = result[0] if result else None
    
    log_activity(session, user=current_user, action="PROMOTION_CREATE", entity="Promotion", entity_id=promotion_id,
                 activity_data={"libelle": libelle.strip(), "programme_id": programme_id}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    programme_param = request.query_params.get('programme', '')
    redirect_url = f"{request.url_for('admin_promotions')}?success=1&action=add&t={timestamp}"
    if programme_param:
        redirect_url += f"&programme={programme_param}"
    return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/promotions/{promotion_id}/update")
def admin_promotions_update(
    promotion_id: int,
    programme_id: int = Form(...),
    libelle: str = Form(...),
    capacite: Optional[str] = Form(None),
    date_debut: Optional[str] = Form(None),
    date_fin: Optional[str] = Form(None),
    actif: Literal["on", "off", ""] = Form("on"),
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la promotion existante avec SQL direct
    promotion_query = text(f"""
        SELECT id, programme_id, libelle, capacite, date_debut, date_fin, actif
        FROM {schema_name}.promotion
        WHERE id = :promotion_id
    """)
    promotion_result = session.exec(promotion_query.bindparams(promotion_id=promotion_id)).first()
    if not promotion_result:
        raise HTTPException(status_code=404, detail="Promotion introuvable")
    
    old_values = dict(promotion_result._mapping)
    
    # Vérifier que le programme existe dans public.programme
    programme_query = text("SELECT id, code, nom FROM public.programme WHERE id = :programme_id AND actif = true")
    programme_result = session.exec(programme_query.bindparams(programme_id=programme_id)).first()
    if not programme_result:
        raise HTTPException(status_code=400, detail="Programme introuvable")
    
    # Vérifier si une autre promotion avec ce libellé existe déjà pour ce programme
    existing_query = text(f"""
        SELECT id FROM {schema_name}.promotion 
        WHERE programme_id = :programme_id AND libelle = :libelle AND id != :promotion_id
    """)
    existing = session.exec(existing_query.bindparams(
        programme_id=programme_id,
        libelle=libelle.strip(),
        promotion_id=promotion_id
    )).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une autre promotion avec ce libellé existe déjà pour ce programme")
    
    # Préparer les nouvelles valeurs
    capacite_val = int(capacite) if capacite and capacite.strip().isdigit() else None
    date_debut_val = datetime.fromisoformat(date_debut).date() if date_debut else None
    date_fin_val = datetime.fromisoformat(date_fin).date() if date_fin else None
    actif_val = (actif != "off")
    
    # Mise à jour SQL directe
    update_query = text(f"""
        UPDATE {schema_name}.promotion
        SET programme_id = :programme_id,
            libelle = :libelle,
            capacite = :capacite,
            date_debut = :date_debut,
            date_fin = :date_fin,
            actif = :actif
        WHERE id = :promotion_id
    """)
    
    session.exec(update_query.bindparams(
        programme_id=programme_id,
        libelle=libelle.strip(),
        capacite=capacite_val,
        date_debut=date_debut_val,
        date_fin=date_fin_val,
        actif=actif_val,
        promotion_id=promotion_id
    ))
    
    new_values = {
        "programme_id": programme_id,
        "libelle": libelle.strip(),
        "capacite": capacite_val,
        "date_debut": date_debut_val,
        "date_fin": date_fin_val,
        "actif": actif_val
    }
    
    log_activity(session, user=current_user, action="PROMOTION_UPDATE", entity="Promotion", entity_id=promotion_id,
                 activity_data={"old": old_values, "new": new_values}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    programme_param = request.query_params.get('programme', '')
    redirect_url = f"{request.url_for('admin_promotions')}?success=1&action=update&t={timestamp}"
    if programme_param:
        redirect_url += f"&programme={programme_param}"
    return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/promotions/{promotion_id}/toggle")
def admin_promotions_toggle(promotion_id: int, request: Request, session: Session = Depends(get_shared_session), current_user: User = Depends(get_current_user)):
    admin_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la promotion existante avec SQL direct
    promotion_query = text(f"""
        SELECT id, libelle, actif
        FROM {schema_name}.promotion
        WHERE id = :promotion_id
    """)
    promotion_result = session.exec(promotion_query.bindparams(promotion_id=promotion_id)).first()
    if not promotion_result:
        raise HTTPException(status_code=404, detail="Promotion introuvable")
    
    promotion_dict = dict(promotion_result._mapping)
    new_actif = not bool(promotion_dict['actif'])
    
    # Mise à jour SQL directe
    update_query = text(f"""
        UPDATE {schema_name}.promotion
        SET actif = :actif
        WHERE id = :promotion_id
    """)
    
    session.exec(update_query.bindparams(
        actif=new_actif,
        promotion_id=promotion_id
    ))
    
    log_activity(session, user=current_user, action="PROMOTION_TOGGLE", entity="Promotion", entity_id=promotion_id,
                activity_data={"libelle": promotion_dict['libelle'], "actif": new_actif}, request=request)
    session.commit()
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    programme_param = request.query_params.get('programme', '')
    redirect_url = f"{request.url_for('admin_promotions')}?success=1&action=toggle&t={timestamp}"
    if programme_param:
        redirect_url += f"&programme={programme_param}"
    return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/promotions/{promotion_id}/delete")
def admin_promotions_delete(
    promotion_id: int,
    request: Request = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    admin_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la promotion existante avec SQL direct
    promotion_query = text(f"""
        SELECT id, libelle, programme_id
        FROM {schema_name}.promotion
        WHERE id = :promotion_id
    """)
    promotion_result = session.exec(promotion_query.bindparams(promotion_id=promotion_id)).first()
    if not promotion_result:
        raise HTTPException(status_code=404, detail="Promotion introuvable")
    
    promotion_dict = dict(promotion_result._mapping)
    promotion_libelle = promotion_dict['libelle']
    promotion_programme_id = promotion_dict['programme_id']
    
    # Vérifier si la promotion est utilisée dans des jurys (dans public.jury)
    try:
        jurys_query = text("SELECT COUNT(*) as count FROM public.jury WHERE promotion_id = :promotion_id")
        jurys_result = session.exec(jurys_query.bindparams(promotion_id=promotion_id)).first()
        jurys_count = jurys_result[0] if jurys_result else 0
    except Exception as e:
        logger.warning(f"Erreur lors de la vérification des jurys: {e}")
        jurys_count = 0
    
    if jurys_count > 0:
        timestamp = int(datetime.now(timezone.utc).timestamp())
        programme_param = request.query_params.get('programme', '')
        redirect_url = f"{request.url_for('admin_promotions')}?error=1&message=Impossible de supprimer la promotion '{promotion_libelle}' car elle est utilisée dans {jurys_count} jury(s). Veuillez d'abord réassigner ces jurys.&t={timestamp}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    
    # Suppression SQL directe
    try:
        delete_query = text(f"DELETE FROM {schema_name}.promotion WHERE id = :promotion_id")
        session.exec(delete_query.bindparams(promotion_id=promotion_id))
        session.commit()
        
        log_activity(session, user=current_user, action="PROMOTION_DELETE", entity="Promotion", entity_id=promotion_id,
                     activity_data={"deleted_promotion_libelle": promotion_libelle, "deleted_promotion_programme_id": promotion_programme_id}, request=request)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression de la promotion")
    
    timestamp = int(datetime.now(timezone.utc).timestamp())
    programme_param = request.query_params.get('programme', '')
    redirect_url = f"{request.url_for('admin_promotions')}?success=1&action=delete&t={timestamp}"
    if programme_param:
        redirect_url += f"&programme={programme_param}"
    return RedirectResponse(url=redirect_url, status_code=303)
