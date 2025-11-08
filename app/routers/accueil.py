# app/routers/accueil.py
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from sqlalchemy import func, case, text
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.config import settings
from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.program_schema_integration import safe_count_query
import logging

logger = logging.getLogger(__name__)
from ..models.base import (
    Candidat, Entreprise, Programme, Preinscription, Inscription,
    Jury, AvancementEtape, EtapePipeline, Eligibilite, DecisionJuryCandidat
)
from ..templates import templates

router = APIRouter()

def _age(d: Optional[date]) -> Optional[int]:
    if not d: return None
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))

def _bucket(a: Optional[int]) -> str:
    if a is None: return "Inconnu"
    if a < 15: return "<15"
    for s in range(15, 65, 5):
        if s <= a <= s+4: return f"{s}-{s+4}"
    return "65+"

def _is_f(civ: Optional[str]) -> bool:
    return (civ or "").strip().lower() in {"f","mme","madame","mlle","mademoiselle","madam"}

def _is_h(civ: Optional[str]) -> bool:
    return (civ or "").strip().lower() in {"m","mr","monsieur","monsier"}

def _get_program_schemas(session: Session) -> List[str]:
    """Récupère la liste des schémas de programme actifs"""
    try:
        # Récupérer les codes de programme actifs
        programmes_query = text("SELECT code FROM public.programme WHERE actif = true")
        result = session.execute(programmes_query)
        programme_codes = [row[0].lower() for row in result.fetchall()]
        return programme_codes
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des schémas de programme: {e}")
        return []

def _table_exists_in_program_schemas(table_name: str, session: Session, program_schemas: List[str]) -> bool:
    """Vérifie si une table existe dans au moins un des schémas de programme"""
    if not program_schemas:
        return False
    try:
        # Construire une requête avec OR pour chaque schéma de programme
        schema_conditions = " OR ".join([f"table_schema = '{schema}'" for schema in program_schemas])
        result = session.execute(text(f"""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = :table_name 
                AND ({schema_conditions})
            )
        """).bindparams(table_name=table_name))
        return result.fetchone()[0]
    except Exception as e:
        logger.warning(f"Erreur lors de la vérification de l'existence de la table {table_name} dans les schémas de programme: {e}")
        return False

def _count_across_schemas(session: Session, table_name: str, schemas: List[str], where_clause: str = "") -> int:
    """Compte les enregistrements d'une table dans tous les schémas de programme"""
    if not schemas:
        return 0
    
    try:
        # Construire une requête UNION pour compter dans tous les schémas
        union_parts = []
        for schema in schemas:
            union_parts.append(f"SELECT COUNT(*) FROM {schema}.{table_name} {where_clause}")
        
        query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
        result = session.execute(text(query))
        total = result.fetchone()[0] or 0
        return int(total)
    except Exception as e:
        logger.warning(f"Erreur lors du comptage dans {table_name} sur tous les schémas: {e}")
        return 0

@router.get("/", response_class=HTMLResponse, name="accueil")
def accueil(request: Request, session: Session = Depends(get_shared_session), current_user = Depends(get_current_user)):
    try:
        tz = ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        # Fallback pour Windows si les données de fuseau horaire ne sont pas disponibles
        tz = timezone.utc
    now = datetime.now(tz)

    # Récupérer les schémas de programme actifs
    program_schemas = _get_program_schemas(session)
    
    # KPIs - Version sécurisée avec agrégation multi-schémas
    # --- KPIs enrichis ---
    total_candidats = 0
    if program_schemas:
        total_candidats = _count_across_schemas(session, "candidat", program_schemas)
    
    total_preinscrits = 0
    if program_schemas:
        total_preinscrits = _count_across_schemas(session, "preinscription", program_schemas)
    
    # Candidats validés - Agrégation multi-schémas
    candidats_valides = 0
    if program_schemas:
        try:
            # Compter les candidats validés dans tous les schémas
            union_parts = []
            for schema in program_schemas:
                union_parts.append(f"""
                    SELECT COUNT(DISTINCT c.id) 
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    WHERE djc.decision = 'VALIDE'
                """)
            query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
            result = session.execute(text(query))
            candidats_valides = result.fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des candidats validés: {e}")
            session.rollback()  # Réinitialiser la transaction
            candidats_valides = 0
    
    # Candidats reorientés - Agrégation multi-schémas
    candidats_reorientes = 0
    if program_schemas:
        try:
            union_parts = []
            for schema in program_schemas:
                union_parts.append(f"""
                    SELECT COUNT(DISTINCT c.id) 
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    WHERE djc.decision = 'REORIENTE'
                """)
            query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
            result = session.execute(text(query))
            candidats_reorientes = result.fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des candidats reorientés: {e}")
            session.rollback()  # Réinitialiser la transaction
            candidats_reorientes = 0
    
    # Candidats rejetés - Agrégation multi-schémas
    candidats_rejetes = 0
    if program_schemas:
        try:
            union_parts = []
            for schema in program_schemas:
                union_parts.append(f"""
                    SELECT COUNT(DISTINCT c.id) 
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    WHERE djc.decision = 'REJETE'
                """)
            query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
            result = session.execute(text(query))
            candidats_rejetes = result.fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des candidats rejetés: {e}")
            session.rollback()  # Réinitialiser la transaction
            candidats_rejetes = 0
    
    # QPV validés - Agrégation multi-schémas
    # Un QPV valide est un candidat validé dont l'éligibilité indique un QPV (commence par "QPV:" mais pas "QPV limit:")
    qpv_valides = 0
    if program_schemas:
        try:
            union_parts = []
            for schema in program_schemas:
                union_parts.append(f"""
                    SELECT COUNT(DISTINCT c.id) 
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    LEFT JOIN {schema}.preinscription p ON p.candidat_id = c.id
                    LEFT JOIN {schema}.eligibilite e ON e.preinscription_id = p.id
                    WHERE djc.decision = 'VALIDE' 
                    AND e.qpv_ok IS NOT NULL
                    AND CAST(e.qpv_ok AS TEXT) LIKE 'QPV:%'
                    AND CAST(e.qpv_ok AS TEXT) NOT LIKE 'QPV limit:%'
                """)
            query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
            result = session.execute(text(query))
            qpv_valides = result.fetchone()[0] or 0
            
            # Log de débogage pour vérifier les éligibilités QPV
            for schema in program_schemas:
                debug_query = text(f"""
                    SELECT COUNT(*) 
                    FROM {schema}.eligibilite 
                    WHERE qpv_ok IS NOT NULL 
                    AND CAST(qpv_ok AS TEXT) LIKE 'QPV:%'
                    AND CAST(qpv_ok AS TEXT) NOT LIKE 'QPV limit:%'
                """)
                debug_result = session.execute(debug_query)
                debug_count = debug_result.fetchone()[0] or 0
                if debug_count > 0:
                    logger.info(f"🔍 [QPV] Schéma {schema}: {debug_count} éligibilités avec QPV (sans limite)")
                
                # Vérifier aussi les candidats validés avec éligibilité
                debug_query2 = text(f"""
                    SELECT COUNT(DISTINCT c.id)
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    LEFT JOIN {schema}.preinscription p ON p.candidat_id = c.id
                    LEFT JOIN {schema}.eligibilite e ON e.preinscription_id = p.id
                    WHERE djc.decision = 'VALIDE'
                    AND e.qpv_ok IS NOT NULL
                    AND CAST(e.qpv_ok AS TEXT) != 'Aucun QPV'
                """)
                debug_result2 = session.execute(debug_query2)
                debug_count2 = debug_result2.fetchone()[0] or 0
                logger.info(f"🔍 [QPV] Schéma {schema}: {debug_count2} candidats validés avec éligibilité")
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des QPV validés: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session.rollback()  # Réinitialiser la transaction
            qpv_valides = 0
    
    # QPV limite validés - Agrégation multi-schémas
    qpv_limite_valides = 0
    if program_schemas:
        try:
            union_parts = []
            for schema in program_schemas:
                union_parts.append(f"""
                    SELECT COUNT(DISTINCT c.id) 
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    LEFT JOIN {schema}.preinscription p ON p.candidat_id = c.id
                    LEFT JOIN {schema}.eligibilite e ON e.preinscription_id = p.id
                    WHERE djc.decision = 'VALIDE' 
                    AND e.qpv_ok IS NOT NULL
                    AND CAST(e.qpv_ok AS TEXT) LIKE 'QPV limit:%'
                """)
            query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
            result = session.execute(text(query))
            qpv_limite_valides = result.fetchone()[0] or 0
            
            # Log de débogage pour vérifier les éligibilités QPV limite
            for schema in program_schemas:
                debug_query = text(f"""
                    SELECT COUNT(*) 
                    FROM {schema}.eligibilite 
                    WHERE qpv_ok IS NOT NULL 
                    AND CAST(qpv_ok AS TEXT) LIKE 'QPV limit:%'
                """)
                debug_result = session.execute(debug_query)
                debug_count = debug_result.fetchone()[0] or 0
                if debug_count > 0:
                    logger.info(f"🔍 [QPV LIMITE] Schéma {schema}: {debug_count} éligibilités avec QPV limite")
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des QPV limite validés: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session.rollback()  # Réinitialiser la transaction
            qpv_limite_valides = 0
    
    # Candidats en attente - Agrégation multi-schémas
    candidats_en_attente = 0
    if program_schemas:
        try:
            union_parts = []
            for schema in program_schemas:
                union_parts.append(f"""
                    SELECT COUNT(DISTINCT c.id) 
                    FROM {schema}.candidat c
                    INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                    LEFT JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    WHERE djc.id IS NULL
                """)
            query = "SELECT SUM(count) FROM (" + " UNION ALL ".join(union_parts) + ") AS counts"
            result = session.execute(text(query))
            candidats_en_attente = result.fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des candidats en attente: {e}")
            session.rollback()  # Réinitialiser la transaction
            candidats_en_attente = 0

    kpi = {
        "candidats": int(total_candidats), 
        "preinscrits": int(total_preinscrits),
        "valides": int(candidats_valides),
        "reorientes": int(candidats_reorientes),
        "rejetes": int(candidats_rejetes),
        "en_attente": int(candidats_en_attente),
        "qpv": int(qpv_valides), 
        "qpv_limite": int(qpv_limite_valides)
    }

    # Répartition par programme (sur inscriptions) - Agrégation multi-schémas
    prog_labels = []
    prog_values = []
    if program_schemas:
        try:
            # Pour chaque programme, compter les inscriptions dans son schéma
            programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
            for prog in programmes:
                schema = prog.code.lower()
                if schema in program_schemas:
                    try:
                        count_query = text(f"SELECT COUNT(*) FROM {schema}.inscription")
                        count_result = session.execute(count_query)
                        count = count_result.fetchone()[0] or 0
                        prog_labels.append(prog.code or "—")
                        prog_values.append(int(count))
                    except Exception as e:
                        logger.warning(f"Erreur lors du comptage des inscriptions pour {prog.code}: {e}")
                        session.rollback()  # Réinitialiser la transaction
                        prog_labels.append(prog.code or "—")
                        prog_values.append(0)
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération de la répartition par programme: {e}")
            session.rollback()  # Réinitialiser la transaction
            prog_labels = []
            prog_values = []

    # Pyramide des âges - Agrégation multi-schémas
    pyramid_labels = ["<15"] + [f"{s}-{s+4}" for s in range(15,65,5)] + ["65+","Inconnu"]
    pyramid_male = [0] * len(pyramid_labels)
    pyramid_female = [0] * len(pyramid_labels)
    
    if program_schemas:
        try:
            bins = pyramid_labels
            male = {b:0 for b in bins}
            female = {b:0 for b in bins}
            
            # Récupérer les données de tous les schémas
            for schema in program_schemas:
                try:
                    civ_dob_query = text(f"SELECT civilite, date_naissance FROM {schema}.candidat")
                    civ_dob_result = session.execute(civ_dob_query)
                    for civ, dob in civ_dob_result.fetchall():
                        a = _age(dob)
                        b = _bucket(a)
                        if _is_f(civ):
                            female[b] += 1
                        elif _is_h(civ):
                            male[b] += 1
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération de la pyramide pour {schema}: {e}")
                    session.rollback()  # Réinitialiser la transaction
            
            pyramid_male = [-male[b] for b in bins]
            pyramid_female = [female[b] for b in bins]
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération de la pyramide des âges: {e}")
            session.rollback()  # Réinitialiser la transaction
            pyramid_male = [0] * len(pyramid_labels)
            pyramid_female = [0] * len(pyramid_labels)

    # Pins : candidats avec coordonnées (entreprise ou candidat) - Agrégation multi-schémas
    rows_geo = []
    if program_schemas:
        try:
            all_rows = []
            for schema in program_schemas:
                try:
                    # Récupérer les coordonnées de l'entreprise en priorité, sinon celles du candidat
                    # Il suffit d'avoir une préinscription pour afficher sur la carte
                    geo_query = text(f"""
                        SELECT DISTINCT
                            c.prenom, c.nom, c.civilite,
                            COALESCE(e.lat, c.lat) as lat,
                            COALESCE(e.lng, c.lng) as lng,
                            COALESCE(e.qpv, false) as qpv,
                            COALESCE(e.adresse, c.adresse_personnelle, '') as adresse,
                            COALESCE(e.territoire, '') as territoire,
                            el.qpv_ok
                        FROM {schema}.candidat c
                        INNER JOIN {schema}.preinscription p ON p.candidat_id = c.id
                        LEFT JOIN {schema}.entreprise e ON e.candidat_id = c.id
                        LEFT JOIN {schema}.eligibilite el ON el.preinscription_id = p.id
                        WHERE (COALESCE(e.lat, c.lat) IS NOT NULL 
                           AND COALESCE(e.lng, c.lng) IS NOT NULL
                           AND COALESCE(e.lat, c.lat) != 0 
                           AND COALESCE(e.lng, c.lng) != 0)
                    """)
                    geo_result = session.execute(geo_query)
                    schema_rows = geo_result.fetchall()
                    all_rows.extend(schema_rows)
                    logger.info(f"📍 [ACCUEIL] Récupéré {len(schema_rows)} pins pour le schéma {schema}")
                    if len(schema_rows) > 0:
                        logger.info(f"📍 [ACCUEIL] Exemple de pin pour {schema}: {schema_rows[0]}")
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération des données géographiques pour {schema}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    session.rollback()  # Réinitialiser la transaction
            rows_geo = all_rows
            logger.info(f"📍 [ACCUEIL] Total rows_geo récupérées: {len(rows_geo)}")
            if len(rows_geo) > 0:
                logger.info(f"📍 [ACCUEIL] Exemple de row_geo: {rows_geo[0]}")
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des données géographiques: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session.rollback()  # Réinitialiser la transaction
            rows_geo = []
    
    pins = []
    for idx, row in enumerate(rows_geo):
        try:
            p, n, c, lat, lng, qpv, adr, ter, qpv_ok = row
            logger.debug(f"📍 [ACCUEIL] Traitement row {idx}: prenom={p}, nom={n}, lat={lat}, lng={lng}")
            
            # Vérifier que les coordonnées sont valides
            if lat is None or lng is None:
                logger.debug(f"📍 [ACCUEIL] Row {idx} ignoré: coordonnées None")
                continue
            
            try:
                lat_float = float(lat)
                lng_float = float(lng)
                
                # Vérifier que les coordonnées ne sont pas zéro
                if lat_float == 0.0 and lng_float == 0.0:
                    logger.debug(f"📍 [ACCUEIL] Row {idx} ignoré: coordonnées à zéro")
                    continue
                
                # Vérifier que les coordonnées sont dans des plages valides
                if not (-90 <= lat_float <= 90) or not (-180 <= lng_float <= 180):
                    logger.warning(f"📍 [ACCUEIL] Coordonnées invalides pour {p} {n}: lat={lat_float}, lng={lng_float}")
                    continue
            except (ValueError, TypeError) as e:
                logger.warning(f"📍 [ACCUEIL] Erreur de conversion des coordonnées pour {p} {n}: {e}, lat={lat}, lng={lng}")
                continue
            
            # Déterminer le statut QPV depuis qpv_ok (prioritaire sur entreprise.qpv)
            qpv_status = False
            qpv_limite = False
            
            # Convertir qpv_ok en string si c'est un booléen (pour compatibilité avec anciennes données)
            qpv_ok_str = None
            if qpv_ok is not None:
                if isinstance(qpv_ok, bool):
                    qpv_ok_str = "QPV" if qpv_ok else "Aucun QPV"
                elif isinstance(qpv_ok, str):
                    qpv_ok_str = qpv_ok
                else:
                    qpv_ok_str = str(qpv_ok)
            
            # Déterminer le statut QPV depuis qpv_ok
            if qpv_ok_str:
                if qpv_ok_str.startswith("QPV limit:"):
                    qpv_limite = True
                    qpv_status = False  # QPV limite n'est pas un QPV complet
                elif qpv_ok_str.startswith("QPV:"):
                    qpv_status = True
                    qpv_limite = False
                elif qpv_ok_str == "Aucun QPV":
                    qpv_status = False
                    qpv_limite = False
            else:
                # Fallback sur entreprise.qpv si qpv_ok n'est pas disponible
                qpv_status = bool(qpv) if qpv is not None else False
            
            pin_data = {
                "prenom": p or "",
                "nom": n or "",
                "sexe": ("F" if _is_f(c) else ("H" if _is_h(c) else "")),
                "lat": lat_float,
                "lng": lng_float,
                "qpv": qpv_status,
                "qpv_limite": qpv_limite,
                "adresse": adr or ter or ""
            }
            pins.append(pin_data)
            logger.debug(f"📍 [ACCUEIL] Pin {idx} créé: {pin_data}")
        except Exception as e:
            logger.warning(f"📍 [ACCUEIL] Erreur lors du traitement d'une ligne géographique (row {idx}): {e}")
            logger.warning(f"📍 [ACCUEIL] Row data: {row}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    logger.info(f"📍 [ACCUEIL] Total pins créés: {len(pins)}")
    if len(pins) > 0:
        logger.info(f"📍 [ACCUEIL] Exemple de pin créé: {pins[0]}")

    # Événements = Jury à venir - Version sécurisée
    jurys = []
    if program_schemas and _table_exists_in_program_schemas("jury", session, program_schemas):
        try:
            # Les jurys sont dans les schémas de programme, on doit agréger depuis tous les schémas
            all_jurys = []
            for schema in program_schemas:
                try:
                    jury_query = text(f"""
                        SELECT id, session_le, programme_id
                        FROM {schema}.jury
                        WHERE session_le >= :now
                        ORDER BY session_le ASC
                        LIMIT 6
                    """)
                    jury_result = session.execute(jury_query.bindparams(now=now))
                    all_jurys.extend(jury_result.fetchall())
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération des jurys pour {schema}: {e}")
                    session.rollback()
            
            # Trier et limiter à 6
            all_jurys.sort(key=lambda x: x[1] if x[1] else datetime.max.replace(tzinfo=timezone.utc))
            # Convertir en objets Jury si nécessaire, ou simplement utiliser les données brutes
            jurys = all_jurys[:6]
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des jurys: {e}")
            session.rollback()  # Réinitialiser la transaction
            jurys = []

    # RDV = AvancementEtape qui démarrent - Agrégation multi-schémas
    rdv_list = []
    if program_schemas:
        try:
            all_rdvs = []
            for schema in program_schemas:
                try:
                    rdv_query = text(f"""
                        SELECT 
                            ae.debut_le,
                            ep.libelle,
                            c.prenom, c.nom,
                            p.code as programme_code
                        FROM {schema}.avancement_etape ae
                        INNER JOIN public.etape_pipeline ep ON ep.id = ae.etape_id
                        INNER JOIN {schema}.inscription i ON i.id = ae.inscription_id
                        INNER JOIN {schema}.candidat c ON c.id = i.candidat_id
                        INNER JOIN public.programme p ON p.id = i.programme_id
                        WHERE ae.debut_le IS NOT NULL 
                        AND ae.debut_le >= :now
                        ORDER BY ae.debut_le ASC
                        LIMIT 8
                    """)
                    rdv_result = session.execute(rdv_query.bindparams(now=now))
                    all_rdvs.extend(rdv_result.fetchall())
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération des RDV pour {schema}: {e}")
            
            # Trier et limiter à 8
            all_rdvs.sort(key=lambda x: x[0] if x[0] else datetime.max.replace(tzinfo=timezone.utc))
            rdv_list = [{
                "when": r[0].astimezone(tz) if r[0] else None,
                "etape": r[1] or "",
                "candidat": f"{r[2] or ''} {r[3] or ''}".strip(),
                "programme": r[4] or ""
            } for r in all_rdvs[:8]]
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des RDV: {e}")
            session.rollback()  # Réinitialiser la transaction
            rdv_list = []

    # Objectifs : tous les programmes avec leurs objectifs basés sur candidats validés - Agrégation multi-schémas
    programmes = []
    # La table programme est dans le schéma public, pas besoin de vérifier dans les schémas de programme
    try:
        programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des programmes: {e}")
        session.rollback()  # Réinitialiser la transaction
        programmes = []
    
    objectifs = []
    if program_schemas and programmes:
        for programme in programmes:
            try:
                schema = programme.code.lower()
                if schema not in program_schemas:
                    continue
                
                # Compter les candidats validés dans le schéma du programme
                agg_query = text(f"""
                    SELECT 
                        COUNT(DISTINCT c.id) as n,
                        SUM(CASE WHEN e.qpv = true THEN 1 ELSE 0 END) as n_qpv,
                        SUM(CASE WHEN LOWER(COALESCE(c.civilite, '')) IN ('f','mme','madame','mlle','mademoiselle','madam') THEN 1 ELSE 0 END) as n_f
                    FROM {schema}.inscription i
                    INNER JOIN {schema}.candidat c ON c.id = i.candidat_id
                    INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                    LEFT JOIN {schema}.entreprise e ON e.candidat_id = c.id
                    WHERE i.programme_id = :programme_id
                    AND djc.decision = 'VALIDE'
                """)
                agg_result = session.execute(agg_query.bindparams(programme_id=programme.id))
                agg_row = agg_result.fetchone()
                
                n = int(agg_row[0] or 0) if agg_row else 0
                n_qpv = int(agg_row[1] or 0) if agg_row else 0
                n_f = int(agg_row[2] or 0) if agg_row else 0
                
                qpv_pct = round((n_qpv / n * 100.0) if n else 0.0, 1)
                f_pct = round((n_f / n * 100.0) if n else 0.0, 1)
                
                # Calculer l'atteinte des objectifs (pour les jauges)
                qpv_objectif_atteint = round((qpv_pct / programme.cible_qpv_pct * 100.0) if programme.cible_qpv_pct and programme.cible_qpv_pct > 0 else 0.0, 1)
                f_objectif_atteint = round((f_pct / programme.cible_femmes_pct * 100.0) if programme.cible_femmes_pct and programme.cible_femmes_pct > 0 else 0.0, 1)
                
                total_pct = round((n / programme.objectif_total * 100.0), 1) if (programme.objectif_total and programme.objectif_total > 0) else None
                
                objectifs.append({
                    "programme": programme.code or "—",
                    "n": n,
                    "qpv_pct": qpv_pct,
                    "f_pct": f_pct,
                    "qpv_objectif_atteint": qpv_objectif_atteint,
                    "f_objectif_atteint": f_objectif_atteint,
                    "target_qpv": programme.cible_qpv_pct,
                    "target_f": programme.cible_femmes_pct,
                    "target_total": programme.objectif_total,
                    "total_pct": total_pct
                })
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des objectifs pour {programme.code}: {e}")
                session.rollback()  # Réinitialiser la transaction
                # Ajouter des valeurs par défaut
                objectifs.append({
                    "programme": programme.code or "—",
                    "n": 0,
                    "qpv_pct": 0.0,
                    "f_pct": 0.0,
                    "qpv_objectif_atteint": 0.0,
                    "f_objectif_atteint": 0.0,
                    "target_qpv": programme.cible_qpv_pct,
                    "target_f": programme.cible_femmes_pct,
                    "target_total": programme.objectif_total,
                    "total_pct": None
                })

    # Logs de débogage pour vérifier les données
    logger.info(f"📊 [ACCUEIL] Schémas de programme: {program_schemas}")
    logger.info(f"📊 [ACCUEIL] KPIs: {kpi}")
    logger.info(f"📊 [ACCUEIL] Programmes labels: {prog_labels}, values: {prog_values}")
    logger.info(f"📊 [ACCUEIL] Pyramide - labels: {len(pyramid_labels)}, male: {sum(pyramid_male)}, female: {sum(pyramid_female)}")
    logger.info(f"📊 [ACCUEIL] Pins: {len(pins)}")
    logger.info(f"📊 [ACCUEIL] Jurys: {len(jurys)}")
    logger.info(f"📊 [ACCUEIL] RDVs: {len(rdv_list)}")
    logger.info(f"📊 [ACCUEIL] Objectifs: {len(objectifs)}")

    # S'assurer que la transaction est valide avant le rendu du template
    # SQLAlchemy peut essayer de charger des attributs lazy lors du rendu
    try:
        session.commit()
    except Exception:
        session.rollback()

    return templates.TemplateResponse(
        "accueil.html",
        {
            "request": request,
            "settings": settings,
            "kpi": kpi,
            "prog_labels": prog_labels,
            "prog_values": prog_values,
            "pyramid_labels": pyramid_labels,
            "pyramid_male": pyramid_male,
            "pyramid_female": pyramid_female,
            "utilisateur": current_user,
            "pins": pins,
            "jurys": jurys,
            "rdvs": rdv_list,
            "objectifs": objectifs,
        },
    )
