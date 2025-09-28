"""
Router pour la gestion des programmes - API REST + Dashboard
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from sqlalchemy import func, case
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app_lia_web.core.database import get_session
from app_lia_web.core.middleware import get_shared_session
from app_lia_web.core.config import settings
from app_lia_web.core.security import get_current_user
from app_lia_web.core.program_schema_integration import safe_count_query, table_exists_anywhere
import logging
from app_lia_web.app.models.base import (
    User, Programme, Candidat, Entreprise,
    RendezVous, SessionProgramme, SessionParticipant,
    SuiviMensuel, DecisionJuryCandidat
)
from app_lia_web.app.models.preinscription import Preinscription, Eligibilite
from app_lia_web.app.models.inscription import Inscription
from app_lia_web.app.models.jury import Jury
from app_lia_web.app.models.enums import UserRole, TypeSession, StatutPresence
from app_lia_web.app.schemas import ProgrammeCreate, ProgrammeUpdate, ProgrammeResponse
from app_lia_web.app.services import ProgrammeService
from app_lia_web.app.templates import templates

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
        return templates.TemplateResponse("error.html", {
            "request": request,
            "utilisateur": current_user,
            "error_message": "Aucun programme trouvé"
        })

    # --- Statistiques générales ---
    # Préinscriptions
    preinscriptions_count = 0
    if table_exists_anywhere("preinscription", session):
        try:
            preinscriptions_count = safe_count_query(session, Preinscription, Preinscription.programme_id == programme.id)
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des préinscriptions: {e}")
            preinscriptions_count = 0
    
    # Inscriptions
    inscriptions_count = 0
    if table_exists_anywhere("inscription", session):
        try:
            inscriptions_count = safe_count_query(session, Inscription, Inscription.programme_id == programme.id)
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des inscriptions: {e}")
            inscriptions_count = 0
    
    # Candidats validés (avec décision jury VALIDE)
    candidats_valides_count = 0
    if (table_exists_anywhere("candidat", session) and 
        table_exists_anywhere("inscription", session) and 
        table_exists_anywhere("decision_jury_candidat", session)):
        try:
            candidats_valides_count = session.exec(
                select(Candidat)
                .join(Inscription, Inscription.candidat_id == Candidat.id)
                .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
                .where(Inscription.programme_id == programme.id, DecisionJuryCandidat.decision == "VALIDE")
            ).count()
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des candidats validés: {e}")
            candidats_valides_count = 0

    # --- Pyramide des âges (candidats validés) ---
    civ_dob = []
    if (programme.id and 
        table_exists_anywhere("candidat", session) and 
        table_exists_anywhere("inscription", session) and 
        table_exists_anywhere("decision_jury_candidat", session)):
        try:
            civ_dob = session.exec(
                select(Candidat.civilite, Candidat.date_naissance)
                .join(Inscription, Inscription.candidat_id == Candidat.id)
                .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
                .where(Inscription.programme_id == programme.id, DecisionJuryCandidat.decision == "VALIDE")
            ).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des données de pyramide des âges: {e}")
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
    if (programme.id and 
        table_exists_anywhere("candidat", session) and 
        table_exists_anywhere("inscription", session) and 
        table_exists_anywhere("decision_jury_candidat", session) and
        table_exists_anywhere("entreprise", session) and
        table_exists_anywhere("eligibilite", session)):
        try:
            # Priorité : adresse QPV/QPV limite, sinon adresse personnelle
            rows_geo = session.exec(
                select(Candidat.prenom, Candidat.nom, Candidat.civilite,
                       # Coordonnées : priorité entreprise, sinon candidat
                       func.coalesce(Entreprise.lat, Candidat.lat).label('lat'),
                       func.coalesce(Entreprise.lng, Candidat.lng).label('lng'),
                       # QPV depuis Entreprise
                       func.coalesce(Entreprise.qpv, False).label('qpv'),
                       # QPV limite depuis Eligibilite.details_json
                       Eligibilite.details_json.label('eligibilite_json'),
                       # Adresse : priorité entreprise, sinon candidat
                       func.coalesce(Entreprise.adresse, Entreprise.territoire, Candidat.adresse_personnelle).label('adresse'))
                .join(Inscription, Inscription.candidat_id == Candidat.id)
                .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
                .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
                .join(Preinscription, Preinscription.candidat_id == Candidat.id)
                .join(Eligibilite, Eligibilite.preinscription_id == Preinscription.id, isouter=True)
                .where(Inscription.programme_id == programme.id, DecisionJuryCandidat.decision == "VALIDE")
                .where(func.coalesce(Entreprise.lat, Candidat.lat).is_not(None), 
                       func.coalesce(Entreprise.lng, Candidat.lng).is_not(None))
            ).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des données géographiques: {e}")
            rows_geo = []
    
    pins = []
    for p,n,c,lat,lng,qpv,elig_json,adr in rows_geo:
        # Analyser le JSON d'éligibilité pour déterminer QPV limite
        qpv_limite = False
        if elig_json:
            try:
                import json
                elig_data = json.loads(elig_json)
                
                # Nouvelle structure : adresses_analysees avec tableau
                if 'adresses_analysees' in elig_data and elig_data['adresses_analysees']:
                    for adresse_info in elig_data['adresses_analysees']:
                        if adresse_info.get('qpv_limite', False):
                            qpv_limite = True
                            break
                
                # Ancienne structure : qpv_limite direct
                elif elig_data.get('qpv_limite', False):
                    qpv_limite = True
                    
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        
        # Déterminer la couleur du pin
        if qpv or qpv_limite:
            color = "red"  # QPV
        else:
            color = "blue"  # Non-QPV
        
        pins.append({
            "lat": float(lat),
            "lng": float(lng),
            "nom": f"{p} {n}",
            "prenom": p,
            "civilite": c,
            "adresse": adr or "Adresse non renseignée",
            "qpv": qpv,
            "qpv_limite": qpv_limite,
            "color": color
        })

    # --- Sessions et présences ---
    sessions_data = []
    if (programme.id and 
        table_exists_anywhere("session_programme", session) and 
        table_exists_anywhere("session_participant", session)):
        try:
            sessions_data = session.exec(
                select(SessionProgramme.nom, SessionProgramme.date_debut, SessionProgramme.date_fin,
                       func.count(SessionParticipant.id).label('participants_count'),
                       func.sum(case((SessionParticipant.statut_presence == StatutPresence.PRESENT, 1), else_=0)).label('presents_count'))
                .join(SessionParticipant, SessionParticipant.session_id == SessionProgramme.id, isouter=True)
                .where(SessionProgramme.programme_id == programme.id)
                .group_by(SessionProgramme.id, SessionProgramme.nom, SessionProgramme.date_debut, SessionProgramme.date_fin)
                .order_by(SessionProgramme.date_debut.desc())
                .limit(10)
            ).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des sessions: {e}")
            sessions_data = []

    # --- Suivi mensuel ---
    suivi_data = []
    if (programme.id and table_exists_anywhere("suivi_mensuel", session)):
        try:
            suivi_data = session.exec(
                select(SuiviMensuel.mois, SuiviMensuel.annee, SuiviMensuel.statut,
                       func.count(SuiviMensuel.id).label('count'))
                .where(SuiviMensuel.programme_id == programme.id)
                .group_by(SuiviMensuel.mois, SuiviMensuel.annee, SuiviMensuel.statut)
                .order_by(SuiviMensuel.annee.desc(), SuiviMensuel.mois.desc())
                .limit(12)
            ).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du suivi mensuel: {e}")
            suivi_data = []

    # --- Rendez-vous récents ---
    rdv_data = []
    if (programme.id and 
        table_exists_anywhere("rendez_vous", session) and 
        table_exists_anywhere("inscription", session)):
        try:
            rdv_data = session.exec(
                select(RendezVous.type_rdv, RendezVous.statut, RendezVous.debut,
                       func.count(RendezVous.id).label('count'))
                .join(Inscription, Inscription.id == RendezVous.inscription_id)
                .where(Inscription.programme_id == programme.id)
                .group_by(RendezVous.type_rdv, RendezVous.statut, RendezVous.debut)
                .order_by(RendezVous.debut.desc())
                .limit(10)
            ).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des rendez-vous: {e}")
            rdv_data = []

    # --- Calcul des KPIs pour le template ---
    # Calculer les statistiques QPV et genre
    qpv_count = 0
    qpv_limite_count = 0
    femmes_count = 0
    hommes_count = 0
    
    for pin in pins:
        if pin.get("qpv"):
            qpv_count += 1
        if pin.get("qpv_limite"):
            qpv_limite_count += 1
        if pin.get("civilite") and _is_f(pin["civilite"]):
            femmes_count += 1
        elif pin.get("civilite") and _is_h(pin["civilite"]):
            hommes_count += 1
    
    # Données pour l'entonnoir
    funnel_labels = ["Préinscriptions", "Inscriptions", "Candidats validés", "QPV", "Femmes"]
    funnel_values = [preinscriptions_count, inscriptions_count, candidats_valides_count, qpv_count, femmes_count]
    
    # Données pour les objectifs (simulées pour l'instant)
    objectifs = {
        "objectif_total": programme.objectif_total,
        "total_pct": (candidats_valides_count / programme.objectif_total * 100) if programme.objectif_total else 0,
        "cible_qpv_pct": programme.cible_qpv_pct,
        "qpv_pct": (qpv_count / candidats_valides_count * 100) if candidats_valides_count > 0 else 0,
        "qpv_objectif_atteint": (qpv_count / candidats_valides_count * 100) if candidats_valides_count > 0 else 0,
        "cible_femmes_pct": programme.cible_femmes_pct,
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
    
    # --- Contexte pour le template ---
    print(f"🔍 [DEBUG] Construction du contexte pour le template")
    print(f"🔍 [DEBUG] Programme: {programme}")
    print(f"🔍 [DEBUG] Preinscriptions: {preinscriptions_count}")
    print(f"🔍 [DEBUG] Inscriptions: {inscriptions_count}")
    
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
        "kpi": {
            "qpv": qpv_count,
            "qpv_limite": qpv_limite_count,
            "femmes": femmes_count,
            "hommes": hommes_count
        },
        "funnel_labels": funnel_labels,
        "funnel_values": funnel_values,
        "objectifs": objectifs,
        "sessions": sessions,
        "presence_avg": presence_avg,
        "rdvs": rdvs,
        "suivis": suivis
    }

    print(f"🔍 [DEBUG] Rendu du template programme_dashboard.html avec programme: {programme}")
    print(f"🔍 [DEBUG] Contexte: {list(context.keys())}")
    
    # Test temporaire avec un template simple
    simple_context = {
        "request": request,
        "current_user": current_user,
        "programme": programme,
        "settings": settings
    }
    
    try:
        return templates.TemplateResponse("programme/programme_dashboard.html", context)
    except Exception as e:
        print(f"❌ [ERROR] Erreur lors du rendu du template: {e}")
        # Fallback vers un template simple
        return templates.TemplateResponse("error.html", {
            "request": request,
            "utilisateur": current_user,
            "error_message": f"Erreur lors du rendu du dashboard: {str(e)}"
        })