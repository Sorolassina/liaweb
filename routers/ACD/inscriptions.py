# app/routers/inscriptions.py
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
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
    DecisionJuryTable, Jury
)
from ...services.ACD.eligibilite import evaluate_eligibilite, entreprise_age_annees

router = APIRouter()

def _prog_by_code(session: Session, code: str) -> Programme | None:
    return session.exec(select(Programme).where(Programme.code == code)).first()

@router.get("/inscriptions", response_class=HTMLResponse)
def inscriptions_redirect(
    programme: str = Query("ACD"),
    pre_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
):
    """Redirige vers la route /inscriptions/form avec les mêmes paramètres"""
    from fastapi.responses import RedirectResponse
    url = f"/ACD/inscriptions/form?programme={programme}"
    if pre_id:
        url += f"&pre_id={pre_id}"
    if q:
        url += f"&q={q}"
    return RedirectResponse(url=url, status_code=302)

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
            "kpi": {
                "total_pre": int(total_pre),
                "total_insc": int(total_insc),
                "taux_conv": taux_conv,
                "objectif_qpv_atteint": objectif_qpv_atteint,
            },
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
        return RedirectResponse(url=f"ACD/inscriptions?programme={prog.code}&pre_id={pre.id}", status_code=303)

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
    return RedirectResponse(url=f"ACD/inscriptions?programme={prog.code}&pre_id={pre.id}", status_code=303)


# Mise à jour infos candidat/entreprise
@router.post("/inscriptions/update-infos")
def update_infos(
    pre_id: int = Form(...),
    telephone: Optional[str] = Form(None),
    adresse_personnelle: Optional[str] = Form(None),
    adresse_entreprise: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    date_creation: Optional[str] = Form(None),
    chiffre_affaires: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    pre = session.get(Preinscription, pre_id)
    if not pre:
        raise HTTPException(status_code=404, detail="Préinscription introuvable")
    cand = session.get(Candidat, pre.candidat_id)
    ent = session.exec(select(Entreprise).where(Entreprise.candidat_id==cand.id)).first()
    if not ent:
        ent = Entreprise(candidat_id=cand.id)
        session.add(ent); session.flush()

    cand.telephone = telephone or cand.telephone
    cand.adresse_personnelle = adresse_personnelle or cand.adresse_personnelle

    ent.adresse = adresse_entreprise or ent.adresse
    ent.siret = siret or ent.siret
    if date_creation:
        try:
            ent.date_creation = _date.fromisoformat(date_creation)
        except Exception:
            pass
    if chiffre_affaires:
        try:
            ent.chiffre_affaires = float(str(chiffre_affaires).replace(" ","").replace(",", "."))
        except Exception:
            pass

    session.commit()
    prog = session.get(Programme, pre.programme_id)
    return RedirectResponse(url=f"ACD/inscriptions?programme={prog.code}&pre_id={pre.id}", status_code=303)


# Recalcul eligibilité
@router.post("/inscriptions/eligibilite/recalc")
def elig_recalc(
    pre_id: int = Form(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    pre = session.get(Preinscription, pre_id)
    if not pre:
        raise HTTPException(status_code=404, detail="Préinscription introuvable")
    prog = session.get(Programme, pre.programme_id)
    cand = session.get(Candidat, pre.candidat_id)
    ent = session.exec(select(Entreprise).where(Entreprise.candidat_id==cand.id)).first()

    ca = ent.chiffre_affaires
    anc = entreprise_age_annees(ent.date_creation)
    verdict, details = evaluate_eligibilite(
        adresse_perso=cand.adresse_personnelle,
        adresse_entreprise=ent.adresse,
        chiffre_affaires=ca,
        anciennete_annees=anc,
        ca_min=prog.ca_seuil_min,
        ca_max=prog.ca_seuil_max,
        anciennete_min_annees=prog.anciennete_min_annees
    )
    elig = session.exec(select(Eligibilite).where(Eligibilite.preinscription_id==pre.id)).first()
    if not elig:
        elig = Eligibilite(preinscription_id=pre.id)
        session.add(elig)
    elig.ca_seuil_ok = details.get("ca_ok")
    elig.ca_score = ca
    elig.qpv_ok = details.get("qpv_ok")
    elig.anciennete_ok = details.get("anciennete_ok")
    elig.anciennete_annees = details.get("anciennete_annees")
    elig.verdict = verdict
    session.commit()

    return RedirectResponse(url=f"ACD/inscriptions?programme={prog.code}&pre_id={pre.id}", status_code=303)


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
