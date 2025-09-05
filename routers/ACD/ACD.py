# app/routers/programmes.py
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from sqlalchemy import func, case
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...core.database import get_session
from ...core.config import settings
from ...models.base import (
    Programme, Preinscription, Inscription, Candidat, Entreprise,
    RendezVous, SessionProgramme, SessionParticipant,
    SuiviMensuel, TypeSession, StatutPresence
)
from ...models.enums import TypeSession, StatutPresence
from ...templates import templates
from ...core.security import get_current_user
from ...models.base import User

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

@router.get("/dashboard", response_class=HTMLResponse)
def programme_acd_dashboard(request: Request, 
                            session: Session = Depends(get_session), 
                            current_user = Depends(get_current_user)
                            ):
    try:
        tz = ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    now = datetime.now(tz)

    # --- Récup programme ACD ---
    acd: Optional[Programme] = session.exec(select(Programme).where(Programme.code == "ACD")).first()
    
    # Si le programme ACD n'existe pas, on utilise des valeurs par défaut
    if not acd:
        # Créer un objet programme factice avec des valeurs par défaut
        class ProgrammeFactice:
            def __init__(self):
                self.code = "ACD"
                self.nom = "Programme ACD"
                self.objectif_total = None
                self.cible_qpv_pct = None
                self.cible_femmes_pct = None
                self.id = None
        
        acd = ProgrammeFactice()

    # --- KPIs ACD ---
    if acd.id:
        preins = session.exec(
            select(func.count(Preinscription.id)).where(Preinscription.programme_id == acd.id)
        ).one() or 0

        insc = session.exec(
            select(func.count(Inscription.id)).where(Inscription.programme_id == acd.id)
        ).one() or 0

        qpv = session.exec(
            select(func.count(Entreprise.id))
            .join(Candidat, Candidat.id == Entreprise.candidat_id)
            .join(Inscription, Inscription.candidat_id == Candidat.id)
            .where(Inscription.programme_id == acd.id, Entreprise.qpv.is_(True))
        ).one() or 0

        femmes = session.exec(
            select(func.count(Candidat.id))
            .join(Inscription, Inscription.candidat_id == Candidat.id)
            .where(Inscription.programme_id == acd.id)
            .where(func.lower(func.coalesce(Candidat.civilite,""))
                   .in_(["f","mme","madame","mlle","mademoiselle","madam"]))
        ).one() or 0

        hommes = session.exec(
            select(func.count(Candidat.id))
            .join(Inscription, Inscription.candidat_id == Candidat.id)
            .where(Inscription.programme_id == acd.id)
            .where(func.lower(func.coalesce(Candidat.civilite,""))
                   .in_(["m","mr","monsieur","monsier"]))
        ).one() or 0
    else:
        preins = insc = qpv = femmes = hommes = 0

    kpi = {"preinscriptions": int(preins), "inscriptions": int(insc),
           "qpv": int(qpv), "femmes": int(femmes), "hommes": int(hommes)}

    # --- Entonnoir ---
    funnel_labels = ["Préinscrits", "Inscriptions"]
    funnel_values = [kpi["preinscriptions"], kpi["inscriptions"]]

    # --- Pyramide des âges (inscrits ACD) ---
    if acd.id:
        civ_dob = session.exec(
            select(Candidat.civilite, Candidat.date_naissance)
            .join(Inscription, Inscription.candidat_id == Candidat.id)
            .where(Inscription.programme_id == acd.id)
        ).all()
    else:
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

    # --- Carte (inscrits ACD avec lat/lng) ---
    if acd.id:
        rows_geo = session.exec(
            select(Candidat.prenom, Candidat.nom, Candidat.civilite,
                   Entreprise.lat, Entreprise.lng, Entreprise.qpv, Entreprise.adresse, Entreprise.territoire)
            .join(Inscription, Inscription.candidat_id == Candidat.id)
            .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
            .where(Inscription.programme_id == acd.id)
            .where(Entreprise.lat.is_not(None), Entreprise.lng.is_not(None))
        ).all()
    else:
        rows_geo = []
    
    pins = [{
        "prenom": p, "nom": n,
        "sexe": ("F" if _is_f(c) else ("H" if _is_h(c) else "")),
        "lat": float(lat), "lng": float(lng),
        "qpv": bool(qpvf), "adresse": adr or ter or ""
    } for p,n,c,lat,lng,qpvf,adr,ter in rows_geo]

    # --- Sessions à venir (séminaire, codev, webinaire) ---
    def next_sessions(t: TypeSession, limit=4):
        if not acd.id:
            return []
        return session.exec(
            select(SessionProgramme)
            .where(SessionProgramme.programme_id == acd.id, SessionProgramme.type_session == t)
            .where(SessionProgramme.debut >= now)
            .order_by(SessionProgramme.debut.asc()).limit(limit)
        ).all()

    sems = next_sessions(TypeSession.SEMINAIRE)
    codevs = next_sessions(TypeSession.CODEV)
    webs = next_sessions(TypeSession.WEBINAIRE)

    # --- Présence moyenne par type (sur tout l'historique ACD) ---
    def avg_presence(t: TypeSession) -> Optional[float]:
        if not acd.id:
            return None
        rows = session.exec(
            select(
                func.sum(case((SessionParticipant.presence == StatutPresence.PRESENT, 1), else_=0)),
                func.count(SessionParticipant.id)
            )
            .join(SessionProgramme, SessionProgramme.id == SessionParticipant.session_id)
            .where(SessionProgramme.programme_id == acd.id, SessionProgramme.type_session == t)
        ).first()
        if not rows or not rows[1]:
            return None
        return round((rows[0] or 0) * 100.0 / rows[1], 1)

    presence_avg = {
        "seminaire": avg_presence(TypeSession.SEMINAIRE),
        "codev": avg_presence(TypeSession.CODEV),
        "webinaire": avg_presence(TypeSession.WEBINAIRE),
    }

    # --- RDV à venir (ACD) ---
    if acd.id:
        rdvs = session.exec(
            select(RendezVous, Inscription, Candidat)
            .join(Inscription, Inscription.id == RendezVous.inscription_id)
            .join(Candidat, Candidat.id == Inscription.candidat_id)
            .where(Inscription.programme_id == acd.id)
            .where(RendezVous.debut >= now)
            .order_by(RendezVous.debut.asc())
            .limit(8)
        ).all()
    else:
        rdvs = []
    
    rdv_list = [{
        "when": r.debut.astimezone(tz),
        "fin": (r.fin.astimezone(tz) if r.fin else None),
        "type": r.type_rdv.value,
        "candidat": f"{c.prenom} {c.nom}"
    } for r, ins, c in rdvs]

    # --- Atteinte des objectifs ACD ---
    # n / objectif_total, %QPV, %Femmes
    if acd.id:
        agg = session.exec(
            select(
                func.count(Inscription.id).label("n"),
                func.sum(case((Entreprise.qpv.is_(True),1), else_=0)).label("n_qpv"),
                func.sum(case((func.lower(func.coalesce(Candidat.civilite,""))
                    .in_(["f","mme","madame","mlle","mademoiselle","madam"]),1), else_=0)).label("n_f")
            )
            .join(Candidat, Candidat.id == Inscription.candidat_id)
            .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
            .where(Inscription.programme_id == acd.id)
        ).first()

        n = int((agg and agg[0]) or 0)
        n_qpv = int((agg and agg[1]) or 0)
        n_f = int((agg and agg[2]) or 0)
        qpv_pct = round((n_qpv/n*100) if n else 0.0, 1)
        f_pct   = round((n_f/n*100) if n else 0.0, 1)
    else:
        n = n_qpv = n_f = 0
        qpv_pct = f_pct = 0.0

    objectifs = {
        "objectif_total": acd.objectif_total,
        "cible_qpv_pct": acd.cible_qpv_pct,
        "cible_femmes_pct": acd.cible_femmes_pct,
        "n": n,
        "qpv_pct": qpv_pct,
        "f_pct": f_pct,
        "total_pct": (round(n/acd.objectif_total*100,1) if acd.objectif_total else None)
    }

    # --- Suivi mensuel (5 derniers enregistrements) ---
    if acd.id:
        suivis = session.exec(
            select(SuiviMensuel, Candidat)
            .join(Inscription, Inscription.id == SuiviMensuel.inscription_id)
            .join(Candidat, Candidat.id == Inscription.candidat_id)
            .where(Inscription.programme_id == acd.id)
            .order_by(SuiviMensuel.mois.desc(), SuiviMensuel.cree_le.desc())
            .limit(5)
        ).all()
    else:
        suivis = []
    
    suivis_list = [{
        "mois": s.mois, "score": s.score_objectifs, "candidat": f"{c.prenom} {c.nom}",
        "commentaire": s.commentaire
    } for s, c in suivis]

    # --- Rendu ---
    return templates.TemplateResponse(
        "ACD/programme_acd_dashboard.html",
        {
            "request": request,
            "settings": settings,
            "utilisateur": current_user,
            "programme": acd,
            "kpi": kpi,
            "funnel_labels": funnel_labels,
            "funnel_values": funnel_values,
            "pyramid_labels": pyramid_labels,
            "pyramid_male": pyramid_male,
            "pyramid_female": pyramid_female,
            "pins": pins,
            "sessions": {
                "seminaires": sems,
                "codevs": codevs,
                "webinaires": webs
            },
            "presence_avg": presence_avg,
            "rdvs": rdv_list,
            "objectifs": objectifs,
            "suivis": suivis_list
        }
    )
