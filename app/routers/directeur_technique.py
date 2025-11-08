# app_lia_web/app/routers/directeur_technique.py

from __future__ import annotations

import json
import re
from calendar import monthrange
from contextlib import contextmanager
from datetime import datetime, timezone, date, timedelta
from typing import Any, Dict, List, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, and_, func, select, text

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere
import logging
from ..models.base import (
    User,
    Programme,
    Candidat,
    Inscription,
    Preinscription,
    Entreprise,
    Eligibilite,
)
from ..models.enums import UserRole, StatutDossier
from ..core.security import get_current_user
from ..core.config import settings
from ..templates import templates


# ============ Utils sécurité & SQL ============

SAFE_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_safe_schema(name: str) -> bool:
    return bool(SAFE_SCHEMA_RE.match(name))


def assert_schema_whitelisted(name: str, whitelist: Set[str]):
    if name not in whitelist or not is_safe_schema(name):
        raise HTTPException(status_code=400, detail=f"Schéma invalide: {name}")


@contextmanager
def transactional(session: Session):
    """
    Ouvre une transaction si aucune n'est active, sinon ouvre un SAVEPOINT.
    Évite: sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session.
    """
    if session.in_transaction():
        with session.begin_nested():   # SAVEPOINT
            yield
    else:
        with session.begin():          # BEGIN
            yield


def exec_text(session: Session, sql: str, params: Dict[str, Any] | None = None):
    """
    Wrapper compatible SQLModel: passe les paramètres via bindparams.
    """
    stmt = text(sql)
    if params:
        stmt = stmt.bindparams(**params)
    return session.exec(stmt)


def schema_exists(session: Session, schema: str) -> bool:
    return bool(
        exec_text(
            session,
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema)",
            {"schema": schema},
        ).first()[0]
    )


def table_exists(session: Session, schema: str, table: str) -> bool:
    return bool(
        exec_text(
            session,
            """
            SELECT EXISTS(
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = :schema AND table_name = :table
            )
            """,
            {"schema": schema, "table": table},
        ).first()[0]
    )


def column_exists(session: Session, schema: str, table: str, column: str) -> bool:
    return bool(
        exec_text(
            session,
            """
            SELECT EXISTS(
              SELECT 1 FROM information_schema.columns
              WHERE table_schema = :schema AND table_name = :table AND column_name = :column
            )
            """,
            {"schema": schema, "table": table, "column": column},
        ).first()[0]
    )


def resolve_status_ref(session: Session, schema: str) -> str | None:
    """
    Retourne une référence SQL sûre vers la colonne statut utilisable dans les requêtes.
    On utilise toujours i.statut (inscription) car c'est là que sont les statuts de dossier.
    """
    if column_exists(session, schema, "inscription", "statut"):
        return "i.statut"
    if column_exists(session, schema, "inscription", "statut_dossier"):
        return "i.statut_dossier"
    # On ne retourne pas c.statut car les statuts de dossier sont dans inscription
    return None


def resolve_decision_date_col(session: Session, schema: str) -> str:
    """
    Colonne de date à utiliser pour dater une 'validation'.
    """
    for col in ("date_decision", "date_validation", "date_statut", "cree_le"):
        if column_exists(session, schema, "inscription", col):
            return col
    # repli ultime
    return "cree_le"


def has_core_tables(session: Session, schema: str) -> bool:
    """
    Vérifie l'existence des tables cœur dans le schéma programme.
    On ne SET LOCAL le search_path que si c'est OK.
    (Les tables dans les schémas programme sont au singulier.)
    """
    core = ("candidat", "preinscription", "inscription", "entreprise")
    for t in core:
        if not table_exists(session, schema, t):
            return False
    return True


def get_schema_info(session: Session) -> Dict[str, Any]:
    """
    Récupère toutes les informations sur les schémas et leurs tables.
    """
    with transactional(session):
        schemas_result = exec_text(
            session,
            """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schema_name
            """,
        )
        schemas = [row[0] for row in schemas_result.all()]
        
        schema_info: Dict[str, Any] = {}
        
        for schema in schemas:
            tables_result = exec_text(
                session,
                """
                SELECT table_name, table_type
                FROM information_schema.tables 
                WHERE table_schema = :schema
                ORDER BY table_name
                """,
                {"schema": schema},
            )
            
            tables: List[Dict[str, Any]] = []
            for table_name, table_type in tables_result.all():
                try:
                    count_result = exec_text(session, f'SELECT COUNT(*) FROM "{schema}"."{table_name}"')
                    first = count_result.first()
                    row_count = first[0] if first else 0
                except Exception:
                    row_count = "N/A"
                
                tables.append({"name": table_name, "type": table_type, "rows": row_count})
            
            schema_info[schema] = {
                "tables": tables,
                "table_count": len(tables),
                "has_core_tables": has_core_tables(session, schema) if schema != "public" else True,
            }
        
        return schema_info


def print_schema_info(session: Session):
    """
    Affiche les informations sur les schémas et leurs tables dans le terminal.
    """
    info = get_schema_info(session)
    
    print("\n" + "="*80)
    print("📊 INFORMATIONS SUR LES SCHÉMAS ET TABLES")
    print("="*80)
    
    for schema_name, schema_data in info.items():
        print(f"\n🗂️  SCHÉMA: {schema_name}")
        print(f"   📋 Nombre de tables: {schema_data['table_count']}")
        print(f"   ✅ Tables cœur présentes: {schema_data['has_core_tables']}")
        
        if schema_data['tables']:
            print("   📝 Tables:")
            for table in schema_data['tables']:
                rows_info = f" ({table['rows']} lignes)" if isinstance(table['rows'], int) else f" ({table['rows']})"
                print(f"      • {table['name']} ({table['type']}){rows_info}")
        else:
            print("   ⚠️  Aucune table trouvée")
    
    print("\n" + "="*80)
    
    core_schemas = [name for name, data in info.items() if data['has_core_tables']]
    print(f"\n✅ Schémas avec tables cœur: {', '.join(core_schemas)}")
    
    no_core_schemas = [name for name, data in info.items() if not data['has_core_tables'] and name != 'public']
    if no_core_schemas:
        print(f"⚠️  Schémas sans tables cœur: {', '.join(no_core_schemas)}")
    
    return info


@contextmanager
def schema_search_path(session: Session, schema: str):
    """
    Applique SET LOCAL search_path au schéma cible + public.
    Doit être appelé *à l'intérieur* d'un bloc transactionnel (transactional).
    """
    exec_text(session, 'SET LOCAL search_path TO :schema, public', {"schema": schema})
    try:
        yield
    finally:
        # SET LOCAL est réinitialisé à la fin de la transaction (ou du savepoint parent).
        pass


def scalar(session: Session, sql: str, params: Dict[str, Any] | None = None) -> int:
    try:
        result = exec_text(session, sql, params).first()
        if result is None:
            return 0
        # Extraire la valeur du tuple ou de l'objet Row
        if hasattr(result, '__getitem__'):
            value = result[0]
        else:
            value = result
        # S'assurer que c'est un entier
        return int(value) if value is not None else 0
    except Exception:
        return 0


# ============ Dates (UTC & bornes mensuelles) ============

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    end = start.replace(day=monthrange(start.year, start.month)[1])
    return start, end


def add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


# ============ Router & guards ============

router = APIRouter()


def directeur_technique_required(current_user: User):
    if current_user.role not in ["administrateur", "directeur_technique"]:
        raise HTTPException(status_code=403, detail="Accès refusé - Droits directeur technique requis")


# ============ Collecte factorisée pour un schéma ============

def gather_schema_metrics(
    session: Session,
    schema_name: str,
    months: List[Tuple[date, date]],
    week_start_utc: datetime,
    pending_threshold_utc: datetime,
) -> Dict[str, Any]:
    """
    Calcule toutes les métriques nécessaires pour UN schéma.
    Renvoie un dict avec des clés standardisées.
    """
    out: Dict[str, Any] = {
        "total_candidats": 0,
        "total_preinscriptions": 0,
        "valides_qpv": 0,
        "valides_qpv_limite": 0,
        "valides_non_qpv": 0,
        "reorientes": 0,
        "rejetes": 0,
        "hommes": 0,
        "femmes": 0,
        "regions": {},  # dict[str, int]
        "regions_sans": 0,
        "pins": [],  # list[dict]
        "pyramide_male": [0, 0, 0, 0, 0, 0],
        "pyramide_female": [0, 0, 0, 0, 0, 0],
        "evol_preinscrits": [0] * len(months),
        "evol_valides": [0] * len(months),
        "conversion_valides": [0.0] * len(months),
        "nouveaux_qpv_semaine": 0,
        "qpv_en_attente": 0,
        "recent_qpv_30j": 0,
        "recent_non_qpv_30j": 0,
        "par_programme": {"total": 0, "qpv": 0, "qpv_limite": 0, "valides": 0},
        "conseillers": {},
    }

    with transactional(session):
        # 0) Vérifs structure avant tout SET LOCAL
        if not schema_exists(session, schema_name):
            return out
        if not has_core_tables(session, schema_name):
            return out

        # Résolution dynamique des colonnes
        status_ref = resolve_status_ref(session, schema_name)  # ex: "i.statut" ou "c.statut"
        decision_col = resolve_decision_date_col(session, schema_name)

        # Génère des conditions prêtes à injecter
        def cond_eq(value: str) -> str:
            return f"{status_ref} = '{value}'" if status_ref else "TRUE"

        with schema_search_path(session, schema_name):
            # Totaux simples
            out["total_candidats"] = scalar(session, "SELECT COUNT(*) FROM candidat")
            out["total_preinscriptions"] = scalar(session, "SELECT COUNT(*) FROM preinscription")

            # Valides par QPV flag (en une requête) — tolérant au manque de i.statut
            row = session.exec(
                text(
                    f"""
                    SELECT
                      SUM((e.qpv IS TRUE  AND {cond_eq('valide')})::int)  AS qpv,
                      SUM((e.qpv IS NULL AND {cond_eq('valide')})::int)  AS qpv_limite,
                      SUM((e.qpv IS FALSE AND {cond_eq('valide')})::int) AS non_qpv
                    FROM inscription i
                    JOIN candidat c   ON i.candidat_id = c.id
                    JOIN entreprise e ON c.id = e.candidat_id
                    """
                )
            ).first() or (0, 0, 0)
            out["valides_qpv"], out["valides_qpv_limite"], out["valides_non_qpv"] = (
                int(row[0] or 0),
                int(row[1] or 0),
                int(row[2] or 0),
            )

            # Statuts (rejetés / réorientés)
            out["reorientes"] = scalar(
                session,
                f"SELECT COUNT(*) FROM inscription i JOIN candidat c ON i.candidat_id = c.id WHERE {cond_eq('reoriente')}",
            )
            out["rejetes"] = scalar(
                session,
                f"SELECT COUNT(*) FROM inscription i JOIN candidat c ON i.candidat_id = c.id WHERE {cond_eq('refuse')}",
            )

            # Sexe
            sex_row = session.exec(
                text(
                    """
                    SELECT
                      SUM((civilite = 'M')::int)  AS hommes,
                      SUM((civilite = 'Mme')::int) AS femmes
                    FROM candidat
                    """
                )
            ).first() or (0, 0)
            out["hommes"], out["femmes"] = (int(sex_row[0] or 0), int(sex_row[1] or 0))

            # Répartition géo des validés
            for reg_row in session.exec(
                text(
                    f"""
                    SELECT e.territoire, COUNT(*)
                    FROM inscription i
                    JOIN candidat c   ON i.candidat_id = c.id
                    JOIN entreprise e ON c.id = e.candidat_id
                    WHERE {cond_eq('valide')}
                    GROUP BY e.territoire
                    """
                )
            ).all():
                region, count = reg_row
                if region and str(region).strip():
                    out["regions"][region] = out["regions"].get(region, 0) + int(count or 0)
                else:
                    out["regions_sans"] += int(count or 0)

            # Pins géo validés
            rows_geo = session.exec(
                text(
                    f"""
                    SELECT c.prenom, c.nom, c.civilite,
                           e.lat, e.lng, e.qpv,
                           COALESCE(e.adresse, e.territoire, '') AS adr,
                           el.details_json
                    FROM inscription i
                    JOIN candidat c        ON i.candidat_id = c.id
                    LEFT JOIN entreprise e ON e.candidat_id = c.id
                    LEFT JOIN preinscription p ON p.candidat_id = c.id
                    LEFT JOIN eligibilite el   ON el.preinscription_id = p.id
                    WHERE {cond_eq('valide')} AND e.lat IS NOT NULL AND e.lng IS NOT NULL
                    """
                )
            ).all()

            for prenom, nom, civilite, lat, lng, qpv_flag, adr, elig_json in rows_geo:
                qpv_limite = False
                if elig_json:
                    try:
                        data = json.loads(elig_json)
                        if isinstance(data, dict):
                            if data.get('adresses_analysees'):
                                for adr_info in data['adresses_analysees']:
                                    if adr_info.get('type') == 'personnelle' and 'resultat' in adr_info:
                                        dist = adr_info['resultat'].get('distance_m')
                                        if isinstance(dist, (int, float)):
                                            qpv_limite = dist > 0
                                            break
                            elif isinstance(data.get('personnelle'), dict):
                                dist = data['personnelle'].get('distance_m')
                                if isinstance(dist, (int, float)):
                                    qpv_limite = dist > 0
                    except Exception:
                        pass

                out["pins"].append({
                    "prenom": prenom,
                    "nom": nom,
                    "sexe": ("F" if civilite == "Mme" else ("H" if civilite == "M" else "")),
                    "lat": float(lat),
                    "lng": float(lng),
                    "qpv": bool(qpv_flag),
                    "qpv_limite": bool(qpv_limite),
                    "adresse": adr or ""
                })

            # Pyramide des âges (validés)
            ages_rows = session.exec(
                text(
                    f"""
                    SELECT c.civilite, c.date_naissance
                    FROM inscription i
                    JOIN candidat c ON i.candidat_id = c.id
                    WHERE {cond_eq('valide')}
                    """
                )
            ).all()
            today_d = now_utc().date()
            for civ, dn in ages_rows:
                if not dn:
                    continue
                age = today_d.year - dn.year - ((today_d.month, today_d.day) < (dn.month, dn.day))
                if   18 <= age <= 25: idx = 0
                elif 26 <= age <= 35: idx = 1
                elif 36 <= age <= 45: idx = 2
                elif 46 <= age <= 55: idx = 3
                elif 56 <= age <= 65: idx = 4
                elif age > 65:        idx = 5
                else:                 continue
                if civ == "M":
                    out["pyramide_male"][idx] += 1
                elif civ == "Mme":
                    out["pyramide_female"][idx] += 1

            # Évolution mensuelle (préinscrits & validés)
            for k, (d1, d2) in enumerate(months):
                out["evol_preinscrits"][k] = scalar(
                    session,
                    "SELECT COUNT(*) FROM preinscription WHERE cree_le >= :d1 AND cree_le <= :d2",
                    {"d1": d1, "d2": d2},
                )
                out["evol_valides"][k] = scalar(
                    session,
                    f"""
                    SELECT COUNT(*)
                    FROM inscription i
                    JOIN candidat c ON i.candidat_id = c.id
                    WHERE {cond_eq('valide')}
                      AND i.{decision_col} >= :d1 AND i.{decision_col} <= :d2
                    """,
                    {"d1": d1, "d2": d2},
                )

            # Alertes - nouveaux QPV semaine & QPV en attente > 15j
            out["nouveaux_qpv_semaine"] = scalar(session, """
                SELECT COUNT(DISTINCT c.id)
                FROM candidat c
                JOIN entreprise e ON c.id = e.candidat_id
                JOIN inscription i ON c.id = i.candidat_id
                WHERE e.qpv IS TRUE
                  AND i.cree_le >= :debut
            """, {"debut": week_start_utc})

            out["qpv_en_attente"] = scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM inscription i
                JOIN candidat c ON i.candidat_id = c.id
                JOIN entreprise e ON c.id = e.candidat_id
                WHERE e.qpv IS TRUE
                  AND {cond_eq('en_examen')}
                  AND i.cree_le <= :seuil
                """,
                {"seuil": pending_threshold_utc},
            )

            # Activité récente 30j (pour temps sessions / usage)
            out["recent_qpv_30j"] = scalar(
                session,
                """
                SELECT COUNT(*)
                FROM inscription i
                JOIN candidat c ON i.candidat_id = c.id
                JOIN entreprise e ON c.id = e.candidat_id
                WHERE e.qpv IS TRUE AND i.cree_le >= :d
                """,
                {"d": now_utc() - timedelta(days=30)},
            )

            out["recent_non_qpv_30j"] = scalar(
                session,
                """
                SELECT COUNT(*)
                FROM inscription i
                JOIN candidat c ON i.candidat_id = c.id
                JOIN entreprise e ON c.id = e.candidat_id
                WHERE e.qpv IS FALSE AND i.cree_le >= :d
                """,
                {"d": now_utc() - timedelta(days=30)},
            )

            # Par programme (pour l’encart programmes_data)
            out["par_programme"]["total"] = scalar(session, "SELECT COUNT(*) FROM inscription")
            out["par_programme"]["qpv"] = scalar(
                session,
                """
                SELECT COUNT(*)
                FROM inscription i
                JOIN candidat c ON i.candidat_id = c.id
                JOIN entreprise e ON c.id = e.candidat_id
                WHERE e.qpv IS TRUE
                """,
            )
            out["par_programme"]["qpv_limite"] = scalar(
                session,
                """
                SELECT COUNT(*)
                FROM inscription i
                JOIN candidat c ON i.candidat_id = c.id
                JOIN entreprise e ON c.id = e.candidat_id
                WHERE e.qpv IS NULL
                """,
            )
            out["par_programme"]["valides"] = scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM inscription i
                JOIN candidat c ON i.candidat_id = c.id
                WHERE {cond_eq('VALIDE')}
                """,
            )

    return out


# ============ Endpoints ============

@router.get("/", response_class=HTMLResponse, name="directeur_technique_dashboard")
async def directeur_technique_dashboard(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    """Dashboard principal du directeur technique avec KPIs QPV"""
    directeur_technique_required(current_user)

    # Programmes actifs -> whitelist de schémas
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    raw_schemas: Set[str] = {
        (p.code or "").lower()
        for p in programmes
        if p.code and is_safe_schema((p.code or "").lower())
    }

    # Filtrer: schémas réellement présents (évite de boucler inutilement)
    schemas: Set[str] = set()
    with transactional(session):
        for s in raw_schemas:
            if schema_exists(session, s):
                schemas.add(s)

    # Préparer les 6 mois (du plus ancien au plus récent)
    today = now_utc().date()
    months: List[Tuple[date, date]] = []
    labels_mois: List[str] = []
    labels_conversion: List[str] = []
    for i in range(5, -1, -1):
        anchor = add_months(today.replace(day=15), -i)
        d1, d2 = month_bounds(anchor)
        months.append((d1, d2))
        labels_mois.append(d1.strftime('%b'))
        labels_conversion.append(d1.strftime("%b %Y"))

    # Seuils alertes
    week_start_utc = now_utc() - timedelta(days=7)
    pending_threshold_utc = now_utc() - timedelta(days=15)

    # Agrégats globaux
    total_candidats = 0
    total_preinscriptions = 0
    candidats_valides_qpv = 0
    candidats_valides_qpv_limite = 0
    candidats_valides_non_qpv = 0
    candidats_reorientes = 0
    candidats_rejetes = 0
    candidats_hommes = 0
    candidats_femmes = 0

    regions_aggregated: Dict[str, int] = {}
    regions_sans_region = 0
    regions_colors = ['#ff6b6b', '#feca57', '#48dbfb', '#0abde3', '#a55eea', '#26de81', '#fd79a8', '#fdcb6e']

    pins_valides: List[Dict[str, Any]] = []

    tranches_ages = ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
    pyramide_male = [0, 0, 0, 0, 0, 0]
    pyramide_female = [0, 0, 0, 0, 0, 0]

    evolution_preinscrits = [0] * len(months)
    evolution_valides = [0] * len(months)
    taux_conversion_mensuel = [0.0] * len(months)

    nouveaux_qpv_total = 0
    candidats_qpv_en_attente_total = 0
    inscriptions_recentes_qpv_total = 0
    inscriptions_recentes_non_qpv_total = 0

    # Programmes_data (par programme ORM + mesures par schéma)
    programmes_data: List[Dict[str, Any]] = []

    # Collecte factorisée par schéma
    per_schema_cache: Dict[str, Dict[str, Any]] = {}

    for p in programmes:
        schema_name = (p.code or "").lower()
        if schema_name not in schemas:
            # Schéma inactif/inexistant → ignore
            programmes_data.append({
                "programme": p,
                "total": 0,
                "qpv": 0,
                "qpv_limite": 0,
                "taux_validation": 0.0,
                "taux_qpv": 0.0,
            })
            continue

        metrics = gather_schema_metrics(
            session=session,
            schema_name=schema_name,
            months=months,
            week_start_utc=week_start_utc,
            pending_threshold_utc=pending_threshold_utc,
        )
        per_schema_cache[schema_name] = metrics

        # Agrégats globaux
        total_candidats += metrics["total_candidats"]
        total_preinscriptions += metrics["total_preinscriptions"]
        candidats_valides_qpv += metrics["valides_qpv"]
        candidats_valides_qpv_limite += metrics["valides_qpv_limite"]
        candidats_valides_non_qpv += metrics["valides_non_qpv"]
        candidats_reorientes += metrics["reorientes"]
        candidats_rejetes += metrics["rejetes"]
        candidats_hommes += metrics["hommes"]
        candidats_femmes += metrics["femmes"]

        for i in range(len(months)):
            evolution_preinscrits[i] += metrics["evol_preinscrits"][i]
            evolution_valides[i] += metrics["evol_valides"][i]

        for r, c in metrics["regions"].items():
            regions_aggregated[r] = regions_aggregated.get(r, 0) + c
        regions_sans_region += metrics["regions_sans"]

        pins_valides.extend(metrics["pins"])

        # Encarts par programme (mesures propres au schéma)
        total_prog = metrics["par_programme"]["total"]
        qpv_prog = metrics["par_programme"]["qpv"]
        qpv_limite_prog = metrics["par_programme"]["qpv_limite"]
        valides_prog = metrics["par_programme"]["valides"]
        taux_validation = (valides_prog / total_prog * 100) if total_prog > 0 else 0.0
        taux_qpv_prog = (qpv_prog / total_prog * 100) if total_prog > 0 else 0.0

        programmes_data.append({
            "programme": p,
            "total": total_prog,
            "qpv": qpv_prog,
            "qpv_limite": qpv_limite_prog,
            "taux_validation": taux_validation,
            "taux_qpv": taux_qpv_prog,
        })

        # Agréger la pyramide des âges
        for idx in range(6):
            pyramide_male[idx] += metrics["pyramide_male"][idx]
            pyramide_female[idx] += metrics["pyramide_female"][idx]

        # Alertes agrégées
        nouveaux_qpv_total += metrics["nouveaux_qpv_semaine"]
        candidats_qpv_en_attente_total += metrics["qpv_en_attente"]
        inscriptions_recentes_qpv_total += metrics["recent_qpv_30j"]
        inscriptions_recentes_non_qpv_total += metrics["recent_non_qpv_30j"]

    # Taux de conversion global (recalcul propre plutôt que somme des taux)
    for i in range(len(months)):
        prei = evolution_preinscrits[i]
        vali = evolution_valides[i]
        taux_conversion_mensuel[i] = (vali / prei * 100) if prei > 0 else 0.0

    # 8 Nombre de programmes (public)
    nombre_programmes = len(programmes)

    # 3 Jury & 9 Coachs (public)
    total_jury = session.exec(select(func.count(User.id)).where(User.role == "jury")).first() or 0
    nombre_coachs = session.exec(select(func.count(User.id)).where(User.role == "coach")).first() or 0

    # 12 RDV (public) - avec gestion d'erreur pour colonnes manquantes
    from ..models.rendez_vous import RendezVous
    from ..models.enums import StatutRDV
    try:
        rdv_planifies = session.exec(
            select(func.count(RendezVous.id)).where(RendezVous.statut == "planifie")
        ).first() or 0
        rdv_realises = session.exec(
            select(func.count(RendezVous.id)).where(RendezVous.statut == "termine")
        ).first() or 0
        rdv_annules = session.exec(
            select(func.count(RendezVous.id)).where(RendezVous.statut == "annule")
        ).first() or 0
    except Exception:
        # Si la colonne statut n'existe pas ou autre erreur
        rdv_planifies = rdv_realises = rdv_annules = 0

    # 13 Événements (public) - avec gestion d'erreur
    from ..models.event import Event, StatutEvent
    date_limite = today + timedelta(days=30)
    try:
        evenements_en_approche = session.exec(
            select(Event).where(
                and_(
                    Event.date_debut >= today,
                    Event.date_debut <= date_limite,
                    Event.statut == "planifie",
                )
            ).order_by(Event.date_debut)
        ).all()
    except Exception:
        # Si la table ou colonnes n'existent pas
        evenements_en_approche = []

    # CONSEILLERS : agrégation groupée par schéma (tolérante au nom de colonne)
    conseillers_data: List[Dict[str, Any]] = []
    conseillers = session.exec(
        select(User).where(User.role.in_(["conseiller", "coordinateur"]))
    ).all()
    for conseiller in conseillers:
        total_suivis = qpv_suivis = qpv_limite_suivis = valides_qpv = 0
        for schema_name in schemas:
            with transactional(session):
                if not has_core_tables(session, schema_name):
                    continue
                status_ref = resolve_status_ref(session, schema_name)
                def cond_eq(value: str) -> str:
                    return f"{status_ref} = '{value}'" if status_ref else "TRUE"
                with schema_search_path(session, schema_name):
                    row = exec_text(
                        session,
                        f"""
                        SELECT
                          COUNT(*) FILTER (WHERE i.conseiller_id = :uid)                                                   AS total_suivis,
                          COUNT(*) FILTER (WHERE i.conseiller_id = :uid AND e.qpv IS TRUE)                                  AS qpv_suivis,
                          COUNT(*) FILTER (WHERE i.conseiller_id = :uid AND e.qpv IS NULL)                                  AS qpv_limite_suivis,
                          COUNT(*) FILTER (WHERE i.conseiller_id = :uid AND e.qpv IS TRUE AND {cond_eq('valide')})         AS valides_qpv
                        FROM inscription i
                        JOIN candidat c ON i.candidat_id = c.id
                        JOIN entreprise e ON c.id = e.candidat_id
                        """,
                        {"uid": conseiller.id},
                    ).first() or (0, 0, 0, 0)
                    total_suivis     += int(row[0] or 0)
                    qpv_suivis       += int(row[1] or 0)
                    qpv_limite_suivis+= int(row[2] or 0)
                    valides_qpv      += int(row[3] or 0)

        taux_validation_qpv = (valides_qpv / qpv_suivis * 100) if qpv_suivis > 0 else 0.0
        charge = "Normale"
        if qpv_suivis > 20:
            charge = "Élevée"
        elif qpv_suivis < 10:
            charge = "Faible"
        conseillers_data.append({
            "conseiller": conseiller,
            "total": total_suivis,
            "qpv": qpv_suivis,
            "qpv_limite": qpv_limite_suivis,
            "taux_validation_qpv": taux_validation_qpv,
            "charge": charge,
        })

    # ALERTES
    alertes_critiques: List[Dict[str, Any]] = []
    alertes_importantes: List[Dict[str, Any]] = []
    alertes_info: List[Dict[str, Any]] = []

    # Objectif QPV 40% par programme
    for pdata in programmes_data:
        if pdata["taux_qpv"] < 40.0:
            alertes_critiques.append({
                "type": "objectif_qpv",
                "programme": pdata["programme"].nom,
                "taux_actuel": pdata["taux_qpv"],
                "objectif": 40.0,
                "message": f"Le programme {pdata['programme'].nom} n'a atteint que {pdata['taux_qpv']:.1f}% de son objectif QPV (cible: 40%)",
            })

    if candidats_qpv_en_attente_total > 0:
        alertes_importantes.append({
            "type": "delais_qpv",
            "nombre": candidats_qpv_en_attente_total,
            "message": f"{candidats_qpv_en_attente_total} candidats QPV en attente depuis plus de 15 jours",
        })
    if nouveaux_qpv_total > 0:
        alertes_info.append({
            "type": "nouveaux_qpv",
            "nombre": nouveaux_qpv_total,
            "message": f"{nouveaux_qpv_total} nouveaux candidats QPV cette semaine",
        })

    total_candidats_valides = candidats_valides_qpv + candidats_valides_qpv_limite + candidats_valides_non_qpv
    taux_usage_base = (total_candidats_valides / total_candidats * 100) if total_candidats > 0 else 0.0

    temps_session_qpv = min(60, max(20, int(inscriptions_recentes_qpv_total * 2)))
    temps_session_non_qpv = min(50, max(15, int(inscriptions_recentes_non_qpv_total * 1.5)))

    usage_qpv = {
        "elearning":   min(100, max(50, taux_usage_base + 10)),
        "rendez_vous": min(100, max(60, taux_usage_base + 15)),
        "seminaires":  min(100, max(40, taux_usage_base + 5)),
        "codev":       min(100, max(30, taux_usage_base - 5)),
        "evenements":  min(100, max(70, taux_usage_base + 20)),
    }
    usage_non_qpv = {
        "elearning":   min(100, max(40, taux_usage_base)),
        "rendez_vous": min(100, max(50, taux_usage_base + 10)),
        "seminaires":  min(100, max(35, taux_usage_base - 5)),
        "codev":       min(100, max(25, taux_usage_base - 10)),
        "evenements":  min(100, max(60, taux_usage_base + 15)),
    }

    # Répartition géographique (format final)
    regions_valides_labels: List[str] = []
    regions_valides_data: List[int] = []
    for region, count in regions_aggregated.items():
        regions_valides_labels.append(region)
        regions_valides_data.append(int(count))
    if regions_sans_region > 0:
        regions_valides_labels.append("Non défini")
        regions_valides_data.append(int(regions_sans_region))

    return templates.TemplateResponse(
        "pages/directeur_technique/dashboard.html",
        {
            "request": request,
            "utilisateur": current_user,
            "settings": settings,
            # Vue d'ensemble
            "total_candidats": total_candidats,
            "total_preinscriptions": total_preinscriptions,
            "total_jury": total_jury,
            "candidats_valides_qpv": candidats_valides_qpv,
            "candidats_valides_qpv_limite": candidats_valides_qpv_limite,
            "candidats_valides_non_qpv": candidats_valides_non_qpv,
            "total_candidats_valides": total_candidats_valides,
            "candidats_reorientes": candidats_reorientes,
            "candidats_rejetes": candidats_rejetes,
            "candidats_hommes": candidats_hommes,
            "candidats_femmes": candidats_femmes,
            "nombre_programmes": nombre_programmes,
            "nombre_coachs": nombre_coachs,
            # Évolution (6 mois)
            "evolution_preinscrits": evolution_preinscrits,
            "evolution_valides": evolution_valides,
            "labels_mois": labels_mois,
            # Répartition géographique
            "regions_valides_labels": regions_valides_labels,
            "regions_valides_data": regions_valides_data,
            "pins_valides": pins_valides,
            "regions_colors": regions_colors,
            # Pyramide des âges
            "pyramide_labels": tranches_ages,
            "pyramide_male": pyramide_male,
            "pyramide_female": pyramide_female,
            # Conversion mensuelle
            "taux_conversion_mensuel": taux_conversion_mensuel,
            "labels_conversion": labels_conversion,
            # RDV & Événements
            "rdv_planifies": rdv_planifies,
            "rdv_realises": rdv_realises,
            "rdv_annules": rdv_annules,
            "evenements_en_approche": evenements_en_approche,
            # Par programme
            "programmes_data": programmes_data,
            # Conseillers
            "conseillers_data": conseillers_data,
            # Alertes
            "alertes_critiques": alertes_critiques,
            "alertes_importantes": alertes_importantes,
            "alertes_info": alertes_info,
            # Stats techniques
            "temps_session_qpv": temps_session_qpv,
            "temps_session_non_qpv": temps_session_non_qpv,
            "usage_qpv": usage_qpv,
            "usage_non_qpv": usage_non_qpv,
            # Meta
            "now": now_utc(),
        },
    )


@router.get("/api/kpis", name="directeur_technique_api_kpis")
async def api_kpis_directeur_technique(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    """API pour récupérer des KPIs globaux (public)."""
    directeur_technique_required(current_user)

    total_candidats = 0
    if table_exists_anywhere("candidat", session):
        total_candidats = safe_count_query(session, Candidat)

    entreprises_qpv = 0
    if table_exists_anywhere("entreprise", session):
        entreprises_qpv = safe_count_query(session, Entreprise, qpv=True)
    candidats_qpv = entreprises_qpv

    entreprises_sans_qpv = 0
    if table_exists_anywhere("entreprise", session):
        try:
            entreprises_sans_qpv = session.exec(
                select(func.count(Entreprise.id)).where(Entreprise.qpv.is_(None))
            ).first() or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des entreprises sans QPV: {e}")
            entreprises_sans_qpv = 0
    candidats_qpv_limite = entreprises_sans_qpv

    taux_qpv_global = (candidats_qpv / total_candidats * 100) if total_candidats > 0 else 0.0

    inscriptions_en_cours = 0
    if table_exists_anywhere("inscription", session):
        try:
            inscriptions_en_cours = session.exec(
                select(func.count(Inscription.id)).where(Inscription.statut == "en_examen")
            ).first() or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des inscriptions en cours: {e}")
            inscriptions_en_cours = 0

    candidats_valides = 0
    if table_exists_anywhere("inscription", session):
        try:
            candidats_valides = session.exec(
                select(func.count(Inscription.id)).where(Inscription.statut == "valide")
            ).first() or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des candidats validés: {e}")
            candidats_valides = 0

    return {
        "status": "success",
        "data": {
            "total_candidats": total_candidats,
            "candidats_qpv": candidats_qpv,
            "candidats_qpv_limite": candidats_qpv_limite,
            "taux_qpv_global": round(taux_qpv_global, 1),
            "inscriptions_en_cours": inscriptions_en_cours,
            "candidats_valides": candidats_valides,
        },
    }


@router.get("/api/schemas-info", name="directeur_technique_api_schemas")
async def api_schemas_info_directeur_technique(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    """API pour récupérer les informations sur tous les schémas et leurs tables."""
    directeur_technique_required(current_user)
    return {"status": "success", "data": get_schema_info(session)}


@router.get("/api/alertes", name="directeur_technique_api_alertes")
async def api_alertes_directeur_technique(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
):
    """API pour récupérer les alertes globales (public)."""
    directeur_technique_required(current_user)

    alertes_critiques: List[Dict[str, Any]] = []
    alertes_importantes: List[Dict[str, Any]] = []
    alertes_info: List[Dict[str, Any]] = []

    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    for programme in programmes:
        total_prog = session.exec(
            select(func.count(Inscription.id)).where(Inscription.programme_id == programme.id)
        ).first() or 0

        qpv_prog = session.exec(
            select(func.count(Inscription.id))
            .join(Candidat, Inscription.candidat_id == Candidat.id)
            .join(Entreprise, Candidat.id == Entreprise.candidat_id)
            .where(and_(Inscription.programme_id == programme.id, Entreprise.qpv == True))
        ).first() or 0

        taux_qpv_prog = (qpv_prog / total_prog * 100) if total_prog > 0 else 0.0
        objectif_qpv = 40.0
        if taux_qpv_prog < objectif_qpv:
            alertes_critiques.append({
                "type": "objectif_qpv",
                "programme": programme.nom,
                "taux_actuel": taux_qpv_prog,
                "objectif": objectif_qpv,
                "message": f"Le programme {programme.nom} n'a atteint que {taux_qpv_prog:.1f}% de son objectif QPV (cible: {objectif_qpv}%)",
            })

    # Délais QPV dépassés (public)
    seuil = now_utc() - timedelta(days=15)
    candidats_qpv_en_attente = session.exec(
        select(func.count(Inscription.id))
        .join(Candidat, Inscription.candidat_id == Candidat.id)
        .join(Entreprise, Candidat.id == Entreprise.candidat_id)
        .where(and_(Entreprise.qpv == True, Inscription.statut == "en_examen", Inscription.cree_le <= seuil))
    ).first() or 0
    if candidats_qpv_en_attente > 0:
        alertes_importantes.append({
            "type": "delais_qpv",
            "nombre": candidats_qpv_en_attente,
            "message": f"{candidats_qpv_en_attente} candidats QPV en attente depuis plus de 15 jours",
        })

    # Nouveaux QPV cette semaine (public)
    debut_semaine = now_utc() - timedelta(days=7)
    nouveaux_qpv = session.exec(
        select(func.count(func.distinct(Candidat.id)))
        .join(Entreprise, Candidat.id == Entreprise.candidat_id)
        .join(Inscription, Candidat.id == Inscription.candidat_id)
        .where(and_(Entreprise.qpv == True, Inscription.cree_le >= debut_semaine))
    ).first() or 0
    if nouveaux_qpv > 0:
        alertes_info.append({
            "type": "nouveaux_qpv",
            "nombre": nouveaux_qpv,
            "message": f"{nouveaux_qpv} nouveaux candidats QPV cette semaine",
        })

    return {
        "status": "success",
        "data": {"critiques": alertes_critiques, "importantes": alertes_importantes, "info": alertes_info},
    }
