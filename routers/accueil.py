# app/routers/accueil.py
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from sqlalchemy import func, case
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.config import settings
from ..core.database import get_session
from ..core.security import get_current_user
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

@router.get("/", response_class=HTMLResponse)
def accueil(request: Request, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    try:
        tz = ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        # Fallback pour Windows si les données de fuseau horaire ne sont pas disponibles
        tz = timezone.utc
    now = datetime.now(tz)

    # KPIs
    # --- KPIs enrichis ---
    total_candidats = session.exec(select(func.count(Candidat.id))).one() or 0
    total_preinscrits = session.exec(select(func.count(Preinscription.id))).one() or 0
    
    # Candidats validés, reorientés, rejetés
    candidats_valides = session.exec(
        select(func.count(Candidat.id))
        .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
        .where(DecisionJuryCandidat.decision == "VALIDE")
    ).one() or 0
    
    candidats_reorientes = session.exec(
        select(func.count(Candidat.id))
        .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
        .where(DecisionJuryCandidat.decision == "REORIENTE")
    ).one() or 0
    
    candidats_rejetes = session.exec(
        select(func.count(Candidat.id))
        .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
        .where(DecisionJuryCandidat.decision == "REJETE")
    ).one() or 0
    
    # QPV et QPV Limite (basé sur candidats validés)
    qpv_valides = session.exec(
        select(func.count(Candidat.id))
        .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
        .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
        .where(DecisionJuryCandidat.decision == "VALIDE", Entreprise.qpv.is_(True))
    ).one() or 0
    
    qpv_limite_valides = session.exec(
        select(func.count(Candidat.id))
        .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id)
        .join(Preinscription, Preinscription.candidat_id == Candidat.id)
        .join(Eligibilite, Eligibilite.preinscription_id == Preinscription.id)
        .where(DecisionJuryCandidat.decision == "VALIDE", 
               Eligibilite.details_json.like('%"distance_m":%'))
        .where(~Eligibilite.details_json.like('%"distance_m": 0%'))
    ).one() or 0
    
    # Candidats en attente (sans décision du jury)
    candidats_en_attente = session.exec(
        select(func.count(Candidat.id))
        .join(Inscription, Inscription.candidat_id == Candidat.id)
        .where(~Candidat.id.in_(
            select(DecisionJuryCandidat.candidat_id)
            .where(DecisionJuryCandidat.candidat_id.is_not(None))
        ))
    ).one() or 0

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

    # Répartition par programme (sur inscriptions)
    rows_prog = session.exec(
        select(Programme.code, func.count(Inscription.id))
        .join(Inscription, Inscription.programme_id == Programme.id, isouter=True)
        .group_by(Programme.code).order_by(Programme.code.asc())
    ).all()
    prog_labels = [r[0] or "—" for r in rows_prog]
    prog_values = [int(r[1] or 0) for r in rows_prog]

    # Pyramide des âges
    civ_dob = session.exec(select(Candidat.civilite, Candidat.date_naissance)).all()
    bins = ["<15"] + [f"{s}-{s+4}" for s in range(15,65,5)] + ["65+","Inconnu"]
    male = {b:0 for b in bins}; female = {b:0 for b in bins}
    for civ, dob in civ_dob:
        a = _age(dob); b = _bucket(a)
        if _is_f(civ): female[b] += 1
        elif _is_h(civ): male[b] += 1
    pyramid_labels = bins
    pyramid_male = [-male[b] for b in bins]
    pyramid_female = [female[b] for b in bins]

    # Pins : candidats avec Entreprise.lat/lng (géocodées au préalable)
    rows_geo = session.exec(
        select(
            Candidat.prenom, Candidat.nom, Candidat.civilite,
            Entreprise.lat, Entreprise.lng, Entreprise.qpv, Entreprise.adresse, Entreprise.territoire,
            Eligibilite.details_json
        ).join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
        .join(Preinscription, Preinscription.candidat_id == Candidat.id, isouter=True)
        .join(Eligibilite, Eligibilite.preinscription_id == Preinscription.id, isouter=True)
        .where(Entreprise.lat.is_not(None), Entreprise.lng.is_not(None))
    ).all()
    
    pins = []
    for p,n,c,lat,lng,qpv,adr,ter,elig_json in rows_geo:
        # Analyser le JSON d'éligibilité pour déterminer QPV limite
        qpv_limite = False
        if elig_json:
            try:
                import json
                elig_data = json.loads(elig_json)
                
                # Nouvelle structure : adresses_analysees avec tableau
                if 'adresses_analysees' in elig_data and elig_data['adresses_analysees']:
                    for adresse_info in elig_data['adresses_analysees']:
                        if adresse_info.get('type') == 'personnelle' and 'resultat' in adresse_info:
                            resultat = adresse_info['resultat']
                            if 'distance_m' in resultat:
                                distance = resultat['distance_m']
                                qpv_limite = distance > 0  # Distance > 0 = QPV limite
                                break
                # Ancienne structure : personnelle directe (fallback)
                elif 'personnelle' in elig_data and 'distance_m' in elig_data['personnelle']:
                    distance = elig_data['personnelle']['distance_m']
                    qpv_limite = distance > 0  # Distance > 0 = QPV limite
            except Exception as e:
                pass
        
        pins.append({
            "prenom": p, "nom": n,
            "sexe": ("F" if _is_f(c) else ("H" if _is_h(c) else "")),
            "lat": float(lat), "lng": float(lng),
            "qpv": bool(qpv), "qpv_limite": qpv_limite,
            "adresse": adr or ter or ""
        })

    # Événements = Jury à venir
    jurys = session.exec(
        select(Jury).where(Jury.session_le >= now).order_by(Jury.session_le.asc()).limit(6)
    ).all()

    # RDV = AvancementEtape qui démarrent
    rdvs = session.exec(
        select(AvancementEtape, EtapePipeline, Inscription, Candidat, Programme)
        .join(EtapePipeline, EtapePipeline.id == AvancementEtape.etape_id)
        .join(Inscription, Inscription.id == AvancementEtape.inscription_id)
        .join(Candidat, Candidat.id == Inscription.candidat_id)
        .join(Programme, Programme.id == Inscription.programme_id)
        .where(AvancementEtape.debut_le.is_not(None))
        .where(AvancementEtape.debut_le >= now)
        .order_by(AvancementEtape.debut_le.asc()).limit(8)
    ).all()
    rdv_list = [{
        "when": a.debut_le.astimezone(tz),
        "etape": e.libelle,
        "candidat": f"{c.prenom} {c.nom}",
        "programme": pg.code
    } for a,e,i,c,pg in rdvs]

    # Objectifs : tous les programmes avec leurs objectifs basés sur candidats validés
    # D'abord récupérer tous les programmes
    programmes = session.exec(select(Programme)).all()
    
    objectifs = []
    for programme in programmes:
        # Pour chaque programme, calculer les candidats validés
        agg = session.exec(
            select(
                func.count(Candidat.id).label("n"),
                func.sum(case((Entreprise.qpv.is_(True),1), else_=0)).label("n_qpv"),
                func.sum(case((func.lower(func.coalesce(Candidat.civilite,""))
                    .in_(["f","mme","madame","mlle","mademoiselle","madam"]),1), else_=0)).label("n_f")
            )
            .select_from(Inscription)
            .join(Candidat, Candidat.id == Inscription.candidat_id, isouter=True)
            .join(DecisionJuryCandidat, DecisionJuryCandidat.candidat_id == Candidat.id, isouter=True)
            .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
            .where(Inscription.programme_id == programme.id)
            .where(DecisionJuryCandidat.decision == "VALIDE")  # Seulement les candidats validés
        ).first()
        
        n = int((agg and agg[0]) or 0)
        n_qpv = int((agg and agg[1]) or 0)
        n_f = int((agg and agg[2]) or 0)
        
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
