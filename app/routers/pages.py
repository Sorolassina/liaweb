# app/routers/pages.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import select, func
from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user, require_permission
from ..models.base import Programme, User, Candidat, Document
from ..models.inscription import Inscription
from ..models.jury import Jury
from ..models.enums import UserRole
from ..templates import templates
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere
import logging

router = APIRouter()

@router.get("/directeur", response_class=HTMLResponse, name="page_directeur")
def page_directeur(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    # Vérifier les permissions
    require_permission(u, [UserRole.DIRECTEUR_TECHNIQUE.value, UserRole.ADMINISTRATEUR.value])
    
    # KPIs - Version sécurisée
    kpi = {
        "programmes": 0,
        "utilisateurs": 0,
        "inscriptions_en_attente": 0,  # Version sécurisée
        "jurys_a_venir": 0,  # Version sécurisée
    }
    
    # Inscriptions en attente - Version sécurisée
    if table_exists_anywhere("inscription", session):
        try:
            kpi["inscriptions_en_attente"] = session.exec(
                select(func.count()).select_from(Inscription).where(Inscription.statut == "en_attente")
            ).one()
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des inscriptions en attente: {e}")
    
    # Jurys à venir - Version sécurisée
    if table_exists_anywhere("jury", session):
        try:
            kpi["jurys_a_venir"] = session.exec(
                select(func.count()).select_from(Jury).where(Jury.session_le != None)
            ).one()
        except Exception as e:
            logging.warning(f"Erreur lors du comptage des jurys à venir: {e}")

    # Listes pour formulaires & widgets
    programmes = session.exec(select(Programme)).all()
    responsables = session.exec(
        select(User).where(User.role == UserRole.RESPONSABLE_PROGRAMME.value)
    ).all()

    dossiers_en_attente = session.exec(
        select(Inscription.id, Inscription.programme_id, Inscription.candidat_id, Inscription.cree_le)
        .where(Inscription.statut == "en_attente")
        .limit(10)
    ).all()
    # Adapter pour enrichir le nom programme/candidat côté template/contexte
    dossiers_ctx = [{
        "id": d.id,
        "programme_nom": f"Programme #{d.programme_id}",
        "candidat_nom": f"Candidat #{d.candidat_id}",
        "recue_le": d.cree_le.strftime("%d/%m/%Y") if d.cree_le else "—",
    } for d in dossiers_en_attente]

    jurys = session.exec(select(Jury).order_by(Jury.session_le).limit(6)).all()

    # "Santé" (exemple : lecture depuis config/env)
    from ..core.config import settings
    health = {
        "smtp_ok": bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD),
        "pappers_ok": bool(settings.PAPPERS_API_KEY),
    }

    # Activité & invitations (exemples : à remplacer par audit réel)
    activites = [
        {"texte": "Programme ACT attribué à RP-ACT", "quand": "il y a 2 h"},
        {"texte": "2 inscriptions passées en 'validé'", "quand": "hier"},
    ]
    invitations = [
        {"email": "coach.ext@lia.app", "role": "COACH_EXTERNE", "expire": "dans 5 jours"},
    ]

    # Rôles utilisateur (affichage)
    roles = [u.role]

    return templates.TemplateResponse(
        "pages/directeur_technique/dashboard.html",
        {
            "request": request,
            "kpi": kpi,
            "programmes": programmes,
            "responsables": responsables,
            "dossiers_en_attente": dossiers_ctx,
            "jurys_a_venir": jurys,
            "health": health,
            "activites": activites,
            "invitations": invitations,
            "roles": roles,
        },
    )

# A) Responsable Structure
@router.get("/responsable-structure", response_class=HTMLResponse, name="page_responsable_structure")
def page_rs(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.RESPONSABLE_STRUCTURE.value, UserRole.ADMINISTRATEUR.value])
    
    kpi = {
        "programmes": 0,
        "promotions": 0,  # à brancher si modèle Promotion
        "groupes": 0,  # à brancher si modèle Groupe
        "conseillers": 0,
    }
    
    if table_exists_anywhere("programme", session):
        kpi["programmes"] = safe_count_query(session, Programme)
    
    if table_exists_anywhere("user", session):
        kpi["conseillers"] = safe_count_query(session, User, role=UserRole.CONSEILLER.value)
    programmes = session.exec(select(Programme)).all()
    # Groupes enrichis (exemple simple)
    groupes = [{"nom": "Groupe ACD-G1", "programme_nom": "ACD"}]
    dossiers = []  # à remplir avec vos requêtes
    return templates.TemplateResponse("pages/espaces/responsable_programme.html", {
        "request": request, "kpi": kpi, "programmes": programmes, "groupes": groupes, "dossiers": dossiers
    })

# B) Responsable Programme
@router.get("/responsable-programme/{programme_id}", response_class=HTMLResponse, name="page_responsable_programme")
def page_rp(programme_id: int, request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.RESPONSABLE_PROGRAMME.value, UserRole.ADMINISTRATEUR.value])
    
    programme = session.get(Programme, programme_id)
    kpi = {"inscriptions_en_attente": 0, "validees": 0, "documents_manquants": 0, "progres_pipeline": 0}
    dossiers = []  # injecter vos dossiers + eligibilite
    etapes = []    # injecter etapes actives du pipeline
    return templates.TemplateResponse("pages/espaces/responsable_programme.html", {
        "request": request, "programme": programme, "kpi": kpi, "dossiers": dossiers, "etapes": etapes
    })

# C) Conseiller
@router.get("/conseiller", response_class=HTMLResponse, name="page_conseiller")
def page_conseiller(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.CONSEILLER.value, UserRole.ADMINISTRATEUR.value])
    
    a_completer = []  # id, candidat_nom, pieces_manquantes
    return templates.TemplateResponse("pages/espaces/conseiller.html", {
        "request": request, "a_completer": a_completer
    })

# D) Jury externe
@router.get("/jury-espace", response_class=HTMLResponse, name="page_jury")
def page_jury(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.JURY_EXTERNE.value, UserRole.RESPONSABLE_PROGRAMME.value, UserRole.ADMINISTRATEUR.value])
    
    jurys = session.exec(select(Jury).order_by(Jury.session_le)).all()
    dossiers = []  # peupler les dossiers soumis au jury
    return templates.TemplateResponse("jury_externe.html", {
        "request": request, "jurys": jurys, "dossiers": dossiers
    })

# E) Coach externe
@router.get("/coach", response_class=HTMLResponse, name="page_coach")
def page_coach(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.COACH_EXTERNE.value, UserRole.CONSEILLER.value, UserRole.ADMINISTRATEUR.value])
    
    seances = []  # agenda coaching
    groupes = []  # groupes suivis
    return templates.TemplateResponse("pages/espaces/coach.html", {
        "request": request, "seances": seances, "groupes": groupes
    })

# F) Candidat (self-service)
@router.get("/espace-candidat", response_class=HTMLResponse, name="page_candidat")
def page_candidat(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.CANDIDAT.value, UserRole.ADMINISTRATEUR.value])
    
    # Ici u est un utilisateur; mappez-le à son Candidat si vous avez la relation - Version sécurisée
    candidat = None
    docs = []
    if table_exists_anywhere("candidat", session):
        try:
            candidat = session.exec(select(Candidat).where(Candidat.email == u.email)).first()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération du candidat: {e}")
    
    if candidat and table_exists_anywhere("document", session):
        try:
            docs = session.exec(select(Document).where(Document.candidat_id == candidat.id)).all()
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des documents: {e}")
            docs = []
    kpi = {"statut": "en_attente", "progression": 0, "docs": len(docs)}
    return templates.TemplateResponse("pages/espaces/candidat.html", {
        "request": request, "candidat": candidat, "documents": docs, "kpi": kpi
    })

@router.get("/drh-daf", response_class=HTMLResponse, name="page_drh_daf")
def page_drh_daf(request: Request, session=Depends(get_shared_session), u=Depends(get_current_user)):
    require_permission(u, [UserRole.DRH_DAF.value, UserRole.DRH.value, UserRole.DAF.value, UserRole.ADMINISTRATEUR.value])
    
    # KPIs (exemples à adapter) - Version sécurisée
    kpi = {
        "effectif_total": 0,
        "effectif_internes": 0,  # filtrer par type interne
        "effectif_externes": 0,  # filtrer par type externe/coach/jury
        "masse_salariale_mois": 0,
        "delta_masse_salariale": "+0%",
        "budget_formation_utilise": 0,
        "budget_formation_engage": 0,
        "taux_turnover": 0,
        "recrutements_en_cours": 0,
    }
    
    if table_exists_anywhere("user", session):
        kpi["effectif_total"] = safe_count_query(session, User)

    # Listes (placeholder, à brancher sur vos tables RH/Finance)
    recrutements = []   # poste, type_contrat, programme_nom, statut
    contrats = []       # nom, type_contrat, fin_contrat, docs_complets
    factures = []       # numero, fournisseur, montant, programme_nom, echeance, statut
    paie = {"brut": 0, "charges": 0, "net": 0}

    couts_programmes = []  # id, nom, budget, depense, engage, reste

    # Rôles pour la nav
    roles = [u.role]

    return templates.TemplateResponse(
        "pages/espaces/drh_daf.html",
        {
            "request": request,
            "kpi": kpi,
            "recrutements": recrutements,
            "contrats": contrats,
            "factures": factures,
            "paie": paie,
            "couts_programmes": couts_programmes,
            "roles": roles,
        },
    )
