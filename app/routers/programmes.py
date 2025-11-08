"""
Router pour la gestion des programmes - API REST + Dashboard
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from sqlalchemy import func, case, text
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.config import settings
from ..core.security import get_current_user
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere
import logging
from ..models.base import (
    User, Programme, Candidat, Entreprise,
    RendezVous, SessionProgramme, SessionParticipant,
    SuiviMensuel, DecisionJuryCandidat
)
from ..models.preinscription import Preinscription, Eligibilite
from ..models.inscription import Inscription
from ..models.jury import Jury
from ..models.enums import UserRole, TypeSession, StatutPresence
from ..schemas import ProgrammeCreate, ProgrammeUpdate, ProgrammeResponse
from ..services import ProgrammeService
from ..templates import templates

router = APIRouter()

# ============================================================================
# FONCTIONS UTILITAIRES POUR LE DASHBOARD
# ============================================================================

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

# ============================================================================
# API REST - GESTION DES PROGRAMMES
# ============================================================================

@router.post("/programmes", response_model=ProgrammeResponse, name="create_programme")
async def create_programme(
    programme_data: ProgrammeCreate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Crée un nouveau programme (directeur technique seulement)"""
    if current_user.role != UserRole.DIRECTEUR_TECHNIQUE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le directeur technique peut créer des programmes"
        )
    
    # Vérifier si le code existe déjà
    existing_programme = ProgrammeService.get_programme_by_code(session, programme_data.code)
    if existing_programme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un programme avec ce code existe déjà"
        )
    
    programme = ProgrammeService.create_programme(session, programme_data)
    return ProgrammeResponse.from_orm(programme)


@router.get("/programmes", response_model=List[ProgrammeResponse], name="get_programmes")
async def get_programmes(
    actif: bool = None,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des programmes"""
    if actif is not None:
        programmes = session.exec(select(Programme).where(Programme.actif == actif)).all()
    else:
        programmes = session.exec(select(Programme)).all()
    
    return [ProgrammeResponse.from_orm(programme) for programme in programmes]


@router.get("/programmes/{programme_id}", response_model=ProgrammeResponse, name="get_programme")
async def get_programme(
    programme_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère un programme par ID"""
    programme = session.get(Programme, programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    return ProgrammeResponse.from_orm(programme)


@router.put("/programmes/{programme_id}", response_model=ProgrammeResponse, name="update_programme")
async def update_programme(
    programme_id: int,
    programme_data: ProgrammeUpdate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour un programme (directeur technique seulement)"""
    if current_user.role != UserRole.DIRECTEUR_TECHNIQUE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le directeur technique peut modifier les programmes"
        )
    
    programme = ProgrammeService.update_programme(session, programme_id, programme_data)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    return ProgrammeResponse.from_orm(programme)


@router.get("/programmes/{programme_id}/statistiques", name="get_programme_stats")
async def get_programme_stats(
    programme_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les statistiques d'un programme"""
    programme = session.get(Programme, programme_id)
    if not programme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme non trouvé"
        )
    
    # Compter les préinscriptions - Version sécurisée
    preinscriptions_count = 0
    if table_exists_anywhere("preinscription", session):
        preinscriptions_count = safe_count_query(session, Preinscription, programme_id=programme_id)
    
    # Compter les inscriptions - Version sécurisée
    inscriptions_count = 0
    if table_exists_anywhere("inscription", session):
        inscriptions_count = safe_count_query(session, Inscription, programme_id=programme_id)
    
    # Compter les jurys - Version sécurisée
    jurys_count = 0
    if table_exists_anywhere("jury", session):
        try:
            jurys_count = session.exec(
                select(Jury).where(Jury.programme_id == programme_id)
            ).count()
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des jurys: {e}")
            jurys_count = 0
    
    return {
        "programme": programme.nom,
        "preinscriptions": preinscriptions_count,
        "inscriptions": inscriptions_count,
        "jurys": jurys_count
    }

# ============================================================================
# DASHBOARD - INTERFACE WEB
# ============================================================================

@router.get("/dashboard", name="programme_dashboard", response_class=HTMLResponse)
def programme_dashboard(request: Request, 
                       session: Session = Depends(get_shared_session), 
                       current_user = Depends(get_current_user),
                       programme: Optional[str] = Query(None)
                       ):
    """Dashboard des programmes avec statistiques visuelles"""
    try:
        tz = ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    now = datetime.now(tz)
    
    try:
        # --- Récupération programme dynamique ---
        if programme:
            programme_obj: Optional[Programme] = session.exec(select(Programme).where(Programme.code == programme)).first()
            print(f"🔍 [DEBUG] Programme trouvé par code {programme}: {programme_obj}")
        else:
            # Récupérer le premier programme actif par défaut
            programme_obj = session.exec(select(Programme).where(Programme.actif == True)).first()
            print(f"🔍 [DEBUG] Programme par défaut: {programme_obj}")
        
        programme = programme_obj

        if not programme:
            return templates.TemplateResponse("500.html", {
                "request": request,
                "utilisateur": current_user,
                "error_message": "Aucun programme trouvé"
            })

        # Extraire le schéma du programme
        schema = programme.code.lower()
        
        # Configurer le search_path pour utiliser le schéma du programme
        try:
            session.execute(text(f"SET search_path TO {schema}, public"))
        except Exception as e:
            logging.warning(f"Erreur lors de la configuration du search_path: {e}")
            session.rollback()

        # --- Statistiques générales ---
        # Préinscriptions
        preinscriptions_count = 0
        try:
            preinscriptions_query = text(f"""
                SELECT COUNT(*) 
                FROM {schema}.preinscription 
                WHERE programme_id = :programme_id
            """)
            result = session.execute(preinscriptions_query.bindparams(programme_id=programme.id))
            preinscriptions_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des préinscriptions: {e}")
            session.rollback()
            preinscriptions_count = 0
        
        # Inscriptions
        inscriptions_count = 0
        try:
            inscriptions_query = text(f"""
                SELECT COUNT(*) 
                FROM {schema}.inscription 
                WHERE programme_id = :programme_id
            """)
            result = session.execute(inscriptions_query.bindparams(programme_id=programme.id))
            inscriptions_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des inscriptions: {e}")
            session.rollback()
            inscriptions_count = 0
        
        # Candidats validés (avec décision jury VALIDE)
        candidats_valides_count = 0
        try:
            candidats_valides_query = text(f"""
                SELECT COUNT(DISTINCT c.id)
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
            """)
            result = session.execute(candidats_valides_query.bindparams(programme_id=programme.id))
            candidats_valides_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des candidats validés: {e}")
            session.rollback()
            candidats_valides_count = 0

        # --- Pyramide des âges (candidats validés) ---
        civ_dob = []
        try:
            civ_dob_query = text(f"""
                SELECT c.civilite, c.date_naissance
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
            """)
            result = session.execute(civ_dob_query.bindparams(programme_id=programme.id))
            civ_dob = result.fetchall()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des données de pyramide des âges: {e}")
            session.rollback()
            civ_dob = []
        
        bins = ["<15"] + [f"{s}-{s+4}" for s in range(15,65,5)] + ["65+","Inconnu"]
        male = {b:0 for b in bins}; female = {b:0 for b in bins}
        for civ, dob in civ_dob:
            a = _age(dob); b = _bucket(a)
            if _is_f(civ): female[b]+=1
            elif _is_h(civ): male[b]+=1
        pyramid_labels = bins
        pyramid_male = [-male[b] for b in bins]
        pyramid_female = [female[b] for b in bins]

        # --- Carte (candidats validés avec lat/lng) ---
        rows_geo = []
        try:
            geo_query = text(f"""
                SELECT DISTINCT
                    c.prenom, c.nom, c.civilite,
                    COALESCE(e.lat, c.lat) as lat,
                    COALESCE(e.lng, c.lng) as lng,
                    COALESCE(e.qpv, false) as qpv,
                    COALESCE(e.adresse, e.territoire, c.adresse_personnelle, '') as adresse,
                    el.qpv_ok
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                LEFT JOIN {schema}.entreprise e ON e.candidat_id = c.id
                LEFT JOIN {schema}.preinscription p ON p.candidat_id = c.id
                LEFT JOIN {schema}.eligibilite el ON el.preinscription_id = p.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
                AND (COALESCE(e.lat, c.lat) IS NOT NULL 
                    AND COALESCE(e.lng, c.lng) IS NOT NULL
                    AND COALESCE(e.lat, c.lat) != 0 
                    AND COALESCE(e.lng, c.lng) != 0)
            """)
            result = session.execute(geo_query.bindparams(programme_id=programme.id))
            rows_geo = result.fetchall()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des données géographiques: {e}")
            session.rollback()
            rows_geo = []
    
        pins = []
        for row in rows_geo:
            try:
                p, n, c, lat, lng, qpv, adr, qpv_ok = row
                
                # Convertir les coordonnées
                try:
                    lat_float = float(lat)
                    lng_float = float(lng)
                    
                    if lat_float == 0.0 and lng_float == 0.0:
                        continue
                    if not (-90 <= lat_float <= 90) or not (-180 <= lng_float <= 180):
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Déterminer le statut QPV depuis qpv_ok (prioritaire sur entreprise.qpv)
                qpv_status = False
                qpv_limite = False
                
                # Convertir qpv_ok en string si c'est un booléen (pour compatibilité)
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
                        qpv_status = False
                    elif qpv_ok_str.startswith("QPV:"):
                        qpv_status = True
                        qpv_limite = False
                    elif qpv_ok_str == "Aucun QPV":
                        qpv_status = False
                        qpv_limite = False
                else:
                    # Fallback sur entreprise.qpv si qpv_ok n'est pas disponible
                    qpv_status = bool(qpv) if qpv is not None else False
                
                # Déterminer la couleur du pin
                if qpv_status:
                    color = "gold"  # Jaune pour QPV
                elif qpv_limite:
                    color = "orange"  # Orange pour QPV limite
                else:
                    color = "blue"  # Bleu pour Non-QPV
                
                pins.append({
                    "lat": lat_float,
                    "lng": lng_float,
                    "nom": f"{p or ''} {n or ''}".strip(),
                    "prenom": p or "",
                    "civilite": c or "",
                    "adresse": adr or "Adresse non renseignée",
                    "qpv": qpv_status,
                    "qpv_limite": qpv_limite,
                    "color": color
                })
            except Exception as e:
                logging.warning(f"Erreur lors du traitement d'une ligne géographique: {e}")
                continue

        # --- Sessions et présences ---
        sessions_data = []
        try:
            sessions_query = text(f"""
                SELECT 
                    sp.titre, sp.debut, sp.fin,
                    COUNT(DISTINCT spart.id) as participants_count,
                    SUM(CASE WHEN spart.presence = 'present' THEN 1 ELSE 0 END) as presents_count
                FROM public.session_programme sp
                LEFT JOIN public.session_participant spart ON spart.session_id = sp.id
                WHERE sp.programme_id = :programme_id
                GROUP BY sp.id, sp.titre, sp.debut, sp.fin
                ORDER BY sp.debut DESC
                LIMIT 10
            """)
            result = session.execute(sessions_query.bindparams(programme_id=programme.id))
            rows = result.fetchall()
            # Convertir les tuples en dictionnaires
            sessions_data = [
                {
                    "titre": row[0],
                    "debut": row[1],
                    "fin": row[2],
                    "participants_count": row[3] or 0,
                    "presents_count": row[4] or 0
                }
                for row in rows
            ]
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des sessions: {e}")
            session.rollback()
            sessions_data = []

        # --- Suivi mensuel ---
        suivi_data = []
        try:
            suivi_query = text(f"""
                SELECT mois, EXTRACT(YEAR FROM mois) as annee, situation_socioprofessionnelle as statut, COUNT(*) as count
                FROM {schema}.suivi_mensuel
                WHERE inscription_id IN (
                    SELECT id FROM {schema}.inscription WHERE programme_id = :programme_id
                )
                GROUP BY mois, situation_socioprofessionnelle
                ORDER BY mois DESC
                LIMIT 12
            """)
            result = session.execute(suivi_query.bindparams(programme_id=programme.id))
            rows = result.fetchall()
            # Convertir les tuples en dictionnaires
            suivi_data = [
                {
                    "mois": row[0],
                    "annee": int(row[1]) if row[1] else None,
                    "statut": row[2],
                    "count": row[3] or 0
                }
                for row in rows
            ]
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du suivi mensuel: {e}")
            session.rollback()
            suivi_data = []

        # --- Rendez-vous récents ---
        rdv_data = []
        try:
            rdv_query = text(f"""
                SELECT 
                    rv.type_rdv, rv.statut, rv.debut,
                    COUNT(*) as count
                FROM {schema}.rendez_vous rv
                INNER JOIN {schema}.inscription i ON i.id = rv.inscription_id
                WHERE i.programme_id = :programme_id
                GROUP BY rv.type_rdv, rv.statut, rv.debut
                ORDER BY rv.debut DESC
                LIMIT 10
            """)
            result = session.execute(rdv_query.bindparams(programme_id=programme.id))
            rows = result.fetchall()
            # Convertir les tuples en dictionnaires
            rdv_data = [
                {
                    "type_rdv": row[0],
                    "statut": row[1],
                    "debut": row[2],
                    "count": row[3] or 0
                }
                for row in rows
            ]
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des rendez-vous: {e}")
            session.rollback()
            rdv_data = []

        # --- Calcul des KPIs pour le template ---
        # Calculer les statistiques QPV et genre directement depuis la base de données
        # (pas seulement depuis les pins qui ne contiennent que ceux avec coordonnées)
        
        # QPV validés
        qpv_count = 0
        try:
            qpv_query = text(f"""
                SELECT COUNT(DISTINCT c.id)
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                LEFT JOIN {schema}.preinscription p ON p.candidat_id = c.id
                LEFT JOIN {schema}.eligibilite e ON e.preinscription_id = p.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
                AND e.qpv_ok IS NOT NULL
                AND CAST(e.qpv_ok AS TEXT) LIKE 'QPV:%'
                AND CAST(e.qpv_ok AS TEXT) NOT LIKE 'QPV limit:%'
            """)
            result = session.execute(qpv_query.bindparams(programme_id=programme.id))
            qpv_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des QPV validés: {e}")
            session.rollback()
            qpv_count = 0
        
        # QPV limite validés
        qpv_limite_count = 0
        try:
            qpv_limite_query = text(f"""
                SELECT COUNT(DISTINCT c.id)
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                LEFT JOIN {schema}.preinscription p ON p.candidat_id = c.id
                LEFT JOIN {schema}.eligibilite e ON e.preinscription_id = p.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
                AND e.qpv_ok IS NOT NULL
                AND CAST(e.qpv_ok AS TEXT) LIKE 'QPV limit:%'
            """)
            result = session.execute(qpv_limite_query.bindparams(programme_id=programme.id))
            qpv_limite_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des QPV limite validés: {e}")
            session.rollback()
            qpv_limite_count = 0
        
        # Femmes validées
        femmes_count = 0
        try:
            femmes_query = text(f"""
                SELECT COUNT(DISTINCT c.id)
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
                AND LOWER(COALESCE(c.civilite, '')) IN ('f','mme','madame','mlle','mademoiselle','madam')
            """)
            result = session.execute(femmes_query.bindparams(programme_id=programme.id))
            femmes_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des femmes validées: {e}")
            session.rollback()
            femmes_count = 0
        
        # Hommes validés
        hommes_count = 0
        try:
            hommes_query = text(f"""
                SELECT COUNT(DISTINCT c.id)
                FROM {schema}.candidat c
                INNER JOIN {schema}.inscription i ON i.candidat_id = c.id
                INNER JOIN {schema}.decision_jury_candidat djc ON djc.candidat_id = c.id
                WHERE i.programme_id = :programme_id
                AND djc.decision = 'VALIDE'
                AND LOWER(COALESCE(c.civilite, '')) IN ('m','mr','monsieur','monsier')
            """)
            result = session.execute(hommes_query.bindparams(programme_id=programme.id))
            hommes_count = result.fetchone()[0] or 0
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des hommes validés: {e}")
            session.rollback()
            hommes_count = 0
        
        # Données pour l'entonnoir
        funnel_labels = ["Préinscriptions", "Inscriptions", "Candidats validés", "QPV", "Femmes"]
        funnel_values = [preinscriptions_count, inscriptions_count, candidats_valides_count, qpv_count, femmes_count]
        
        # Données pour les objectifs (simulées pour l'instant)
        objectif_total = getattr(programme, 'objectif_total', None) or 0
        cible_qpv_pct = getattr(programme, 'cible_qpv_pct', None)
        cible_femmes_pct = getattr(programme, 'cible_femmes_pct', None)
        
        objectifs = {
            "objectif_total": objectif_total,
            "total_pct": (candidats_valides_count / objectif_total * 100) if objectif_total > 0 else 0,
            "cible_qpv_pct": cible_qpv_pct,
            "qpv_pct": (qpv_count / candidats_valides_count * 100) if candidats_valides_count > 0 else 0,
            "qpv_objectif_atteint": (qpv_count / candidats_valides_count * 100) if candidats_valides_count > 0 else 0,
            "cible_femmes_pct": cible_femmes_pct,
            "f_pct": (femmes_count / candidats_valides_count * 100) if candidats_valides_count > 0 else 0,
            "f_objectif_atteint": (femmes_count / candidats_valides_count * 100) if candidats_valides_count > 0 else 0
        }
        
        # Données pour les sessions (simulées pour l'instant)
        sessions = {
            "seminaires": [],
            "codevs": [],
            "webinaires": []
        }
        
        presence_avg = {
            "seminaire": 85.5,
            "codev": 78.2,
            "webinaire": 92.1
        }
        
        # Données pour les RDVs (simulées pour l'instant)
        rdvs = []
        
        # Données pour le suivi (simulées pour l'instant)
        suivis = []
        
        # Créer le dictionnaire kpi avant les logs
        kpi = {
            "qpv": qpv_count,
            "qpv_limite": qpv_limite_count,
            "femmes": femmes_count,
            "hommes": hommes_count
        }
        
        # --- Contexte pour le template ---
        logging.info(f"🔍 [DASHBOARD] Construction du contexte pour le template")
        logging.info(f"🔍 [DASHBOARD] Programme: {programme.code} - {programme.nom}")
        logging.info(f"🔍 [DASHBOARD] Schéma utilisé: {schema}")
        logging.info(f"🔍 [DASHBOARD] Préinscriptions: {preinscriptions_count}")
        logging.info(f"🔍 [DASHBOARD] Inscriptions: {inscriptions_count}")
        logging.info(f"🔍 [DASHBOARD] Candidats validés: {candidats_valides_count}")
        logging.info(f"🔍 [DASHBOARD] QPV: {qpv_count}, QPV limite: {qpv_limite_count}")
        logging.info(f"🔍 [DASHBOARD] Femmes: {femmes_count}, Hommes: {hommes_count}")
        logging.info(f"🔍 [DASHBOARD] Pins géographiques: {len(pins)}")
        if len(pins) > 0:
            logging.info(f"🔍 [DASHBOARD] Exemple de pin: {pins[0]}")
        logging.info(f"🔍 [DASHBOARD] Sessions: {len(sessions_data)}")
        logging.info(f"🔍 [DASHBOARD] Suivi mensuel: {len(suivi_data)}")
        logging.info(f"🔍 [DASHBOARD] Rendez-vous: {len(rdv_data)}")
        logging.info(f"🔍 [DASHBOARD] Pyramide des âges - Labels: {pyramid_labels}")
        logging.info(f"🔍 [DASHBOARD] Pyramide des âges - Hommes: {pyramid_male}")
        logging.info(f"🔍 [DASHBOARD] Pyramide des âges - Femmes: {pyramid_female}")
        logging.info(f"🔍 [DASHBOARD] Funnel labels: {funnel_labels}")
        logging.info(f"🔍 [DASHBOARD] Funnel values: {funnel_values}")
        logging.info(f"🔍 [DASHBOARD] Objectifs: {objectifs}")
        
        context = {
            "request": request,
            "utilisateur": current_user,  # Variable utilisée par base.html
            "programme": programme,
            "now": now,
            "preinscriptions_count": preinscriptions_count,
            "inscriptions_count": inscriptions_count,
            "candidats_valides_count": candidats_valides_count,
            "pyramid_labels": pyramid_labels,
            "pyramid_male": pyramid_male,
            "pyramid_female": pyramid_female,
            "pins": pins,
            "sessions_data": sessions_data,
            "suivi_data": suivi_data,
            "rdv_data": rdv_data,
            "settings": settings,
            # Nouvelles variables pour le template
            "kpi": kpi,
            "funnel_labels": funnel_labels,
            "funnel_values": funnel_values,
            "objectifs": objectifs,
            "sessions": sessions,
            "presence_avg": presence_avg,
            "rdvs": rdvs,
            "suivis": suivis
        }

        logging.info(f"🔍 [DASHBOARD] Rendu du template programme_dashboard.html")
        logging.info(f"🔍 [DASHBOARD] Clés du contexte: {list(context.keys())}")
        
        # Log détaillé des données envoyées au frontend
        import json
        logging.info(f"🔍 [DASHBOARD] === DONNÉES ENVOYÉES AU FRONTEND ===")
        logging.info(f"🔍 [DASHBOARD] Pins (premiers 3): {json.dumps([p for p in pins[:3]], default=str, ensure_ascii=False)}")
        logging.info(f"🔍 [DASHBOARD] Funnel labels: {funnel_labels}")
        logging.info(f"🔍 [DASHBOARD] Funnel values: {funnel_values}")
        logging.info(f"🔍 [DASHBOARD] Pyramid labels: {pyramid_labels}")
        logging.info(f"🔍 [DASHBOARD] Pyramid male (premiers 5): {pyramid_male[:5]}")
        logging.info(f"🔍 [DASHBOARD] Pyramid female (premiers 5): {pyramid_female[:5]}")
        logging.info(f"🔍 [DASHBOARD] KPI: {json.dumps(kpi, default=str, ensure_ascii=False)}")
        logging.info(f"🔍 [DASHBOARD] Objectifs: {json.dumps(objectifs, default=str, ensure_ascii=False)}")
        logging.info(f"🔍 [DASHBOARD] Sessions data (premiers 2): {json.dumps([s for s in sessions_data[:2]], default=str, ensure_ascii=False)}")
        logging.info(f"🔍 [DASHBOARD] Suivi data (premiers 2): {json.dumps([s for s in suivi_data[:2]], default=str, ensure_ascii=False)}")
        logging.info(f"🔍 [DASHBOARD] RDV data (premiers 2): {json.dumps([r for r in rdv_data[:2]], default=str, ensure_ascii=False)}")
        
        try:
            return templates.TemplateResponse("pages/programme/programme_dashboard.html", context)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ [ERROR] Erreur lors du rendu du template: {e}")
            print(f"❌ [ERROR] Traceback complet:\n{error_trace}")
            # Fallback vers un template simple
            return templates.TemplateResponse("500.html", {
                "request": request,
                "utilisateur": current_user,
                "error_message": f"Erreur lors du rendu du dashboard: {str(e)}"
            }, status_code=500)
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [ERROR] Erreur globale dans programme_dashboard: {e}")
        print(f"❌ [ERROR] Traceback complet:\n{error_trace}")
        return templates.TemplateResponse("500.html", {
            "request": request,
            "utilisateur": current_user,
            "error_message": f"Erreur lors du chargement du dashboard: {str(e)}"
        }, status_code=500)