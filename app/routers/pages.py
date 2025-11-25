"""
Router pour les pages générales de l'application
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session, select
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, date, timedelta
import logging
import base64
import json
from pathlib import Path

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.program_schema_integration import (
    get_schema_from_request, 
    get_schema_routing_service, 
    SchemaRoutingService,
    table_exists_anywhere
)
from ..core.config import settings
from ..core.path_config import path_config
from ..models.base import User, Candidat
from ..templates import templates

router = APIRouter()
logger = logging.getLogger(__name__)


def get_candidat_from_user(session: Session, user: User, schema_name: str) -> Optional[Any]:
    """Récupère le candidat associé à un utilisateur via son email"""
    try:
        # Vérifier que la table candidat existe
        if not table_exists_anywhere("candidat", session, schema_name):
            return None
        
        # Récupérer le candidat par email
        candidat_query = text(f"""
            SELECT * FROM {schema_name}.candidat 
            WHERE email = :email
            LIMIT 1
        """)
        candidat_result = session.exec(candidat_query.bindparams(email=user.email)).first()
        
        if candidat_result:
            # Convertir le résultat en objet simple
            if hasattr(candidat_result, '_mapping'):
                candidat_dict = dict(candidat_result._mapping)
            else:
                candidat_dict = dict(candidat_result)
            
            candidat = type('Candidat', (), candidat_dict)()
            return candidat
        
        return None
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération du candidat: {e}")
        return None


def get_all_program_schemas(session: Session) -> List[str]:
    """Récupère la liste de tous les schémas de programmes"""
    try:
        result = session.exec(text("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
            ORDER BY schema_name
        """))
        schemas = [row[0] for row in result]
        return schemas
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des schémas: {e}")
        return []


def build_union_query_for_schemas(schemas: List[str], table_name: str, select_clause: str, where_clause: str = "", group_by_clause: str = "") -> str:
    """Construit une requête UNION ALL pour agréger les données sur plusieurs schémas"""
    if not schemas:
        return ""
    
    union_parts = []
    for schema in schemas:
        union_parts.append(f"""
            SELECT {select_clause}
            FROM {schema}.{table_name}
            {where_clause}
        """)
    
    query = " UNION ALL ".join(union_parts)
    if group_by_clause:
        query = f"""
            SELECT * FROM (
                {query}
            ) AS combined_data
            {group_by_clause}
        """
    return query


@router.get("/espace-candidat", name="espace_candidat", response_class=HTMLResponse)
async def espace_candidat(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme: Optional[str] = None,
    candidat_id: Optional[int] = None
):
    """Espace candidat avec onglets pour consulter ses données"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request, programme=programme) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        # Vérifier si l'utilisateur est admin
        is_admin = current_user.role == "administrateur" or current_user.role == "directeur_general"
        
        # Récupérer le candidat
        candidat = None
        if is_admin and candidat_id:
            # Si admin et candidat_id fourni, récupérer ce candidat spécifique
            if table_exists_anywhere("candidat", session, schema_name):
                try:
                    candidat_query = text(f"""
                        SELECT * FROM {schema_name}.candidat 
                        WHERE id = :candidat_id
                        LIMIT 1
                    """)
                    candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
                    if candidat_result:
                        if hasattr(candidat_result, '_mapping'):
                            candidat_dict = dict(candidat_result._mapping)
                        else:
                            candidat_dict = dict(candidat_result)
                        candidat = type('Candidat', (), candidat_dict)()
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération du candidat par ID: {e}")
        
        # Si pas de candidat trouvé et pas admin, essayer de récupérer via email
        if not candidat:
            candidat = get_candidat_from_user(session, current_user, schema_name)
        
        if not candidat:
            # Si pas de candidat trouvé
            if is_admin:
                # Pour les admins, récupérer la liste des candidats
                candidats_list = []
                if table_exists_anywhere("candidat", session, schema_name):
                    try:
                        candidats_query = text(f"""
                            SELECT id, nom, prenom, email 
                            FROM {schema_name}.candidat 
                            ORDER BY nom, prenom
                        """)
                        candidats_results = session.exec(candidats_query).all()
                        for result in candidats_results:
                            candidat_dict = dict(result._mapping) if hasattr(result, '_mapping') else dict(result)
                            candidats_list.append(candidat_dict)
                    except Exception as e:
                        logger.warning(f"Erreur lors de la récupération de la liste des candidats: {e}")
                
                # Pour les admins, afficher un message différent avec sélecteur
                return templates.TemplateResponse(
                    "pages/espace_candidat.html",
                    {
                        "request": request,
                        "utilisateur": current_user,
                        "candidat": None,
                        "rendez_vous": [],
                        "seminaires": [],
                        "events": [],
                        "codev_data": [],
                        "elearning_data": [],
                        "rdv_stats": {"total": 0, "planifies": 0, "termines": 0, "annules": 0, "emarges": 0},
                        "rdv_alertes": 0,
                        "sem_stats": {"total": 0, "planifies": 0, "termines": 0, "annules": 0},
                        "sem_alertes": 0,
                        "event_stats": {"total": 0, "planifies": 0, "termines": 0, "annules": 0},
                        "event_alertes": 0,
                        "codev_stats": {"total": 0, "actifs": 0, "termines": 0},
                        "codev_alertes": 0,
                        "elearning_stats": {"total": 0, "en_cours": 0, "termines": 0, "non_commences": 0},
                        "elearning_alertes": 0,
                        "schema_name": schema_name,
                        "is_admin": True,
                        "candidats_list": candidats_list,
                        "error_message": "Veuillez sélectionner un candidat pour voir son espace."
                    }
                )
            else:
                # Pour les non-admins, message d'erreur
                return templates.TemplateResponse(
                    "pages/espace_candidat.html",
                    {
                        "request": request,
                        "utilisateur": current_user,
                        "candidat": None,
                        "rendez_vous": [],
                        "seminaires": [],
                        "events": [],
                        "codev_data": [],
                        "elearning_data": [],
                        "schema_name": schema_name,
                        "is_admin": False,
                        "error_message": "Aucun candidat associé à votre compte."
                    }
                )
        
        # Récupérer les rendez-vous du candidat avec données d'émargement
        rendez_vous = []
        rdv_stats = {
            "total": 0,
            "planifies": 0,
            "termines": 0,
            "annules": 0,
            "emarges": 0
        }
        if table_exists_anywhere("rendez_vous", session, schema_name):
            try:
                # Récupérer les rendez-vous avec émargement
                rdv_query_str = f"""
                    SELECT 
                        rv.id,
                        rv.candidat_id,
                        rv.conseiller_id,
                        rv.type_rdv,
                        rv.statut,
                        rv.debut,
                        rv.fin,
                        rv.lieu,
                        rv.notes,
                        rv.meet_link,
                        u.nom_complet as conseiller_nom,
                        e.id as emargement_id,
                        e.signature_candidat,
                        e.date_signature_candidat,
                        e.signature_conseiller,
                        e.date_signature_conseiller
                    FROM {schema_name}.rendez_vous rv
                    LEFT JOIN public."user" u ON rv.conseiller_id = u.id
                    LEFT JOIN {schema_name}.emargement_rdv e ON rv.id = e.rdv_id
                    INNER JOIN {schema_name}.candidat c ON rv.candidat_id = c.id
                    WHERE rv.candidat_id = :candidat_id
                """
                where_conditions_rdv = []
                params_rdv = {"candidat_id": candidat.id}
                
                # Ajouter le filtre partenaire_bpi si nécessaire
                from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
                add_partenaire_bpi_filter(current_user, where_conditions_rdv, params_rdv, "c.")
                
                if where_conditions_rdv:
                    rdv_query_str = rdv_query_str.replace("WHERE rv.candidat_id = :candidat_id", 
                                                          "WHERE rv.candidat_id = :candidat_id AND " + " AND ".join(where_conditions_rdv))
                
                rdv_query_str += " ORDER BY rv.debut DESC"
                rdv_query = text(rdv_query_str)
                rdv_results = session.exec(rdv_query.bindparams(**params_rdv)).all()
                
                # Récupérer les avis séparément (si les colonnes existent)
                avis_dict = {}
                try:
                    avis_query = text(f"""
                        SELECT id, note_conseiller, avis_candidat
                        FROM {schema_name}.rendez_vous
                        WHERE candidat_id = :candidat_id
                    """)
                    avis_results = session.exec(avis_query.bindparams(candidat_id=candidat.id)).all()
                    for avis_row in avis_results:
                        if hasattr(avis_row, '_mapping'):
                            avis_data = dict(avis_row._mapping)
                        else:
                            avis_data = dict(avis_row)
                        if 'id' in avis_data:
                            avis_dict[avis_data['id']] = {
                                "note": avis_data.get('note_conseiller'),
                                "avis": avis_data.get('avis_candidat')
                            }
                except Exception as e:
                    # Si les colonnes n'existent pas, on crée un dict vide
                    logger.debug(f"Colonnes d'avis non disponibles: {e}")
                    avis_dict = {}
                
                for row in rdv_results:
                    rdv_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                    
                    # Ajouter les données d'avis si disponibles
                    rdv_id = rdv_dict.get("id")
                    if rdv_id and rdv_id in avis_dict:
                        rdv_dict["note_conseiller"] = avis_dict[rdv_id]["note"]
                        rdv_dict["avis_candidat"] = avis_dict[rdv_id]["avis"]
                    else:
                        rdv_dict["note_conseiller"] = None
                        rdv_dict["avis_candidat"] = None
                    
                    # Calculer les statistiques
                    rdv_stats["total"] += 1
                    statut = rdv_dict.get("statut", "").lower() if rdv_dict.get("statut") else ""
                    if statut == "termine":
                        rdv_stats["termines"] += 1
                    elif statut == "planifie":
                        rdv_stats["planifies"] += 1
                    elif statut == "annule":
                        rdv_stats["annules"] += 1
                    
                    # Vérifier si é margé
                    if rdv_dict.get("signature_candidat"):
                        rdv_stats["emarges"] += 1
                        rdv_dict["est_emarge"] = True
                    else:
                        rdv_dict["est_emarge"] = False
                    
                    rendez_vous.append(rdv_dict)
                
                # Calculer le nombre de RDV proches (passés dans les 7 derniers jours) et non signés
                from datetime import datetime, timedelta
                now = datetime.now()
                seven_days_ago = now - timedelta(days=7)
                rdv_alertes = 0
                
                for rdv_dict in rendez_vous:
                    # Vérifier si le RDV est terminé et non signé
                    if (rdv_dict.get("statut", "").lower() == "termine" and 
                        not rdv_dict.get("est_emarge", False) and
                        rdv_dict.get("debut")):
                        try:
                            if isinstance(rdv_dict["debut"], str):
                                rdv_date = datetime.fromisoformat(rdv_dict["debut"].replace('Z', '+00:00'))
                            else:
                                rdv_date = rdv_dict["debut"]
                            
                            # Convertir en datetime naive si nécessaire
                            if hasattr(rdv_date, 'tzinfo') and rdv_date.tzinfo:
                                rdv_date = rdv_date.replace(tzinfo=None)
                            
                            # Vérifier si le RDV est passé dans les 7 derniers jours
                            if seven_days_ago <= rdv_date <= now:
                                rdv_alertes += 1
                        except Exception as e:
                            logger.debug(f"Erreur lors du traitement de la date du RDV: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des rendez-vous: {e}")
                rdv_alertes = 0
        
        # Récupérer les séminaires du candidat (via invitations individuelles uniquement)
        seminaires = []
        sem_stats = {
            "total": 0,
            "planifies": 0,
            "termines": 0,
            "annules": 0
        }
        if table_exists_anywhere("invitation_seminaire", session, schema_name):
            try:
                sem_query_str = f"""
                    SELECT DISTINCT
                        s.id,
                        s.titre,
                        s.description,
                        s.date_debut,
                        s.date_fin,
                        s.lieu,
                        s.statut,
                        s.meet_link,
                        i.statut as invitation_statut,
                        i.date_reponse,
                        p.nom as programme_nom
                    FROM {schema_name}.seminaire s
                    INNER JOIN {schema_name}.invitation_seminaire i ON s.id = i.seminaire_id
                    INNER JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                    LEFT JOIN public.programme p ON s.programme_id = p.id
                    WHERE i.candidat_id = :candidat_id
                    AND i.candidat_id IS NOT NULL
                """
                where_conditions_sem = []
                params_sem = {"candidat_id": candidat.id}
                
                # Ajouter le filtre partenaire_bpi si nécessaire
                from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
                add_partenaire_bpi_filter(current_user, where_conditions_sem, params_sem, "c.")
                
                if where_conditions_sem:
                    sem_query_str = sem_query_str.replace("WHERE i.candidat_id = :candidat_id", 
                                                          "WHERE i.candidat_id = :candidat_id AND " + " AND ".join(where_conditions_sem))
                
                sem_query_str += " ORDER BY s.date_debut DESC"
                sem_query = text(sem_query_str)
                sem_results = session.exec(sem_query.bindparams(**params_sem)).all()
                for row in sem_results:
                    sem_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                    
                    # Calculer les statistiques
                    sem_stats["total"] += 1
                    statut = sem_dict.get("statut", "").lower() if sem_dict.get("statut") else ""
                    if statut == "termine":
                        sem_stats["termines"] += 1
                    elif statut == "planifie":
                        sem_stats["planifies"] += 1
                    elif statut == "annule":
                        sem_stats["annules"] += 1
                    
                    seminaires.append(sem_dict)
                
                # Calculer le nombre de séminaires proches (passés dans les 7 derniers jours) nécessitant une action
                from datetime import datetime, timedelta
                now = datetime.now()
                seven_days_ago = now - timedelta(days=7)
                sem_alertes = 0
                
                for sem_dict in seminaires:
                    # Vérifier si le séminaire est terminé et nécessite une action (par exemple, émargement)
                    if (sem_dict.get("statut", "").lower() == "termine" and 
                        sem_dict.get("date_fin")):
                        try:
                            if isinstance(sem_dict["date_fin"], str):
                                sem_date = datetime.fromisoformat(sem_dict["date_fin"].replace('Z', '+00:00'))
                            else:
                                sem_date = sem_dict["date_fin"]
                            
                            # Convertir en datetime naive si nécessaire
                            if hasattr(sem_date, 'tzinfo') and sem_date.tzinfo:
                                sem_date = sem_date.replace(tzinfo=None)
                            
                            # Vérifier si le séminaire est passé dans les 7 derniers jours
                            if seven_days_ago <= sem_date <= now:
                                sem_alertes += 1
                        except Exception as e:
                            logger.debug(f"Erreur lors du traitement de la date du séminaire: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des séminaires: {e}")
                sem_alertes = 0
        else:
            sem_alertes = 0
        
        # Récupérer les événements du candidat (via invitations individuelles uniquement)
        events = []
        event_stats = {
            "total": 0,
            "planifies": 0,
            "termines": 0,
            "annules": 0
        }
        if table_exists_anywhere("invitation_event", session, schema_name):
            try:
                event_query_str = f"""
                    SELECT DISTINCT
                        e.id,
                        e.titre,
                        e.description,
                        e.date_debut,
                        e.date_fin,
                        e.heure_debut,
                        e.heure_fin,
                        e.lieu,
                        e.statut,
                        e.meet_link,
                        i.statut as invitation_statut,
                        i.date_reponse,
                        p.nom as programme_nom
                    FROM {schema_name}.event e
                    INNER JOIN {schema_name}.invitation_event i ON e.id = i.event_id
                    INNER JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                    LEFT JOIN public.programme p ON e.programme_id = p.id
                    WHERE i.candidat_id = :candidat_id
                """
                where_conditions_event = []
                params_event = {"candidat_id": candidat.id}
                
                # Ajouter le filtre partenaire_bpi si nécessaire
                from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
                add_partenaire_bpi_filter(current_user, where_conditions_event, params_event, "c.")
                
                if where_conditions_event:
                    event_query_str = event_query_str.replace("WHERE i.candidat_id = :candidat_id", 
                                                              "WHERE i.candidat_id = :candidat_id AND " + " AND ".join(where_conditions_event))
                
                event_query_str += " ORDER BY e.date_debut DESC"
                event_query = text(event_query_str)
                event_results = session.exec(event_query.bindparams(**params_event)).all()
                for row in event_results:
                    event_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                    
                    # Calculer les statistiques
                    event_stats["total"] += 1
                    statut = event_dict.get("statut", "").lower() if event_dict.get("statut") else ""
                    if statut == "termine":
                        event_stats["termines"] += 1
                    elif statut == "planifie":
                        event_stats["planifies"] += 1
                    elif statut == "annule":
                        event_stats["annules"] += 1
                    
                    events.append(event_dict)
                
                # Calculer le nombre d'événements proches (passés dans les 7 derniers jours) nécessitant une action
                from datetime import datetime, timedelta
                now = datetime.now()
                seven_days_ago = now - timedelta(days=7)
                event_alertes = 0
                
                for event_dict in events:
                    # Vérifier si l'événement est terminé et nécessite une action
                    if (event_dict.get("statut", "").lower() == "termine" and 
                        event_dict.get("date_fin")):
                        try:
                            if isinstance(event_dict["date_fin"], str):
                                event_date = datetime.fromisoformat(event_dict["date_fin"].replace('Z', '+00:00'))
                            else:
                                event_date = event_dict["date_fin"]
                            
                            # Convertir en datetime naive si nécessaire
                            if hasattr(event_date, 'tzinfo') and event_date.tzinfo:
                                event_date = event_date.replace(tzinfo=None)
                            
                            # Vérifier si l'événement est passé dans les 7 derniers jours
                            if seven_days_ago <= event_date <= now:
                                event_alertes += 1
                        except Exception as e:
                            logger.debug(f"Erreur lors du traitement de la date de l'événement: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des événements: {e}")
                event_alertes = 0
        else:
            event_alertes = 0
        
        # Récupérer les données codev du candidat (via groupes)
        codev_data = []
        codev_stats = {
            "total": 0,
            "actifs": 0,
            "termines": 0
        }
        if table_exists_anywhere("membre_groupe_codev", session, schema_name):
            try:
                codev_query = text(f"""
                    SELECT DISTINCT
                        g.id as groupe_id,
                        g.nom as groupe_nom,
                        g.description as groupe_description,
                        c.id as cycle_id,
                        c.nom as cycle_nom,
                        c.statut as cycle_statut,
                        mg.statut as statut_membre,
                        COUNT(DISTINCT s.id) as nombre_seances
                    FROM {schema_name}.groupe_codev g
                    INNER JOIN {schema_name}.membre_groupe_codev mg ON g.id = mg.groupe_codev_id
                    INNER JOIN {schema_name}.cycle_codev c ON g.cycle_id = c.id
                    LEFT JOIN {schema_name}.seance_codev s ON g.id = s.groupe_id
                    WHERE mg.candidat_id = :candidat_id
                    GROUP BY g.id, g.nom, g.description, c.id, c.nom, c.statut, mg.statut
                    ORDER BY c.id DESC, g.id DESC
                """)
                codev_results = session.exec(codev_query.bindparams(candidat_id=candidat.id)).all()
                for row in codev_results:
                    codev_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                    
                    # Calculer les statistiques
                    codev_stats["total"] += 1
                    cycle_statut = codev_dict.get("cycle_statut", "").lower() if codev_dict.get("cycle_statut") else ""
                    if cycle_statut == "termine":
                        codev_stats["termines"] += 1
                    elif cycle_statut in ["actif", "en_cours"]:
                        codev_stats["actifs"] += 1
                    
                    codev_data.append(codev_dict)
                
                # Calculer le nombre de groupes codev actifs nécessitant une attention
                from datetime import datetime, timedelta
                now = datetime.now()
                codev_alertes = 0
                
                # Compter les groupes actifs avec des séances récentes ou à venir
                for codev_dict in codev_data:
                    cycle_statut = codev_dict.get("cycle_statut", "").lower() if codev_dict.get("cycle_statut") else ""
                    if cycle_statut in ["actif", "en_cours"]:
                        codev_alertes += 1
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des données codev: {e}")
                codev_alertes = 0
        else:
            codev_alertes = 0
        
        # Récupérer les données e-learning du candidat (via progressions)
        elearning_data = []
        elearning_stats = {
            "total": 0,
            "en_cours": 0,
            "termines": 0,
            "non_commences": 0
        }
        if table_exists_anywhere("progression_elearning", session, schema_name):
            try:
                elearning_query = text(f"""
                    SELECT 
                        pe.id,
                        pe.ressource_id,
                        pe.statut,
                        pe.temps_consacre_minutes as duree_minutes,
                        pe.date_debut,
                        pe.date_fin,
                        pe.score,
                        r.titre as ressource_titre,
                        r.type_ressource,
                        r.url_ressource,
                        m.nom as module_nom,
                        CASE 
                            WHEN pe.statut = 'termine' THEN 100
                            WHEN pe.statut = 'en_cours' THEN 50
                            ELSE 0
                        END as progression_pourcentage
                    FROM {schema_name}.progression_elearning pe
                    LEFT JOIN {schema_name}.ressource_elearning r ON pe.ressource_id = r.id
                    LEFT JOIN {schema_name}.module_elearning m ON r.module_id = m.id
                    WHERE pe.candidat_id = :candidat_id
                    ORDER BY pe.date_debut DESC
                """)
                elearning_results = session.exec(elearning_query.bindparams(candidat_id=candidat.id)).all()
                for row in elearning_results:
                    elearn_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                    
                    # Calculer les statistiques
                    elearning_stats["total"] += 1
                    statut = elearn_dict.get("statut", "").lower() if elearn_dict.get("statut") else ""
                    if statut == "termine":
                        elearning_stats["termines"] += 1
                    elif statut == "en_cours":
                        elearning_stats["en_cours"] += 1
                    else:
                        elearning_stats["non_commences"] += 1
                    
                    elearning_data.append(elearn_dict)
                
                # Calculer le nombre de ressources e-learning en cours nécessitant une attention
                from datetime import datetime, timedelta
                now = datetime.now()
                elearning_alertes = 0
                
                # Compter les ressources en cours non terminées
                for elearn_dict in elearning_data:
                    statut = elearn_dict.get("statut", "").lower() if elearn_dict.get("statut") else ""
                    if statut == "en_cours":
                        elearning_alertes += 1
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des données e-learning: {e}")
                elearning_alertes = 0
        else:
            elearning_alertes = 0
        
        return templates.TemplateResponse(
            "pages/espace_candidat.html",
            {
                "request": request,
                "utilisateur": current_user,
                "candidat": candidat,
                "rendez_vous": rendez_vous,
                "rdv_stats": rdv_stats,
                "rdv_alertes": rdv_alertes,
                "seminaires": seminaires,
                "sem_stats": sem_stats,
                "sem_alertes": sem_alertes,
                "events": events,
                "event_stats": event_stats,
                "event_alertes": event_alertes,
                "codev_data": codev_data,
                "codev_stats": codev_stats,
                "codev_alertes": codev_alertes,
                "elearning_data": elearning_data,
                "elearning_stats": elearning_stats,
                "elearning_alertes": elearning_alertes,
                "schema_name": schema_name,
                "is_admin": is_admin
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur dans espace_candidat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de l'espace candidat: {str(e)}")


@router.post("/espace-candidat/rdv/{rdv_id}/emarger", name="emarger_rdv_candidat", response_class=JSONResponse)
async def emarger_rdv_candidat(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    signature: str = Form(...)
):
    """Permet au candidat connecté d'émarger un rendez-vous"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier si l'utilisateur est admin
        is_admin = current_user.role == "administrateur" or current_user.role == "directeur_general"
        
        # Récupérer le candidat connecté
        candidat = get_candidat_from_user(session, current_user, schema_name)
        
        # Récupérer le RDV pour obtenir le candidat_id
        rdv_query = text(f"""
            SELECT id, candidat_id FROM {schema_name}.rendez_vous 
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        rdv_dict = dict(rdv_result._mapping) if hasattr(rdv_result, '_mapping') else dict(rdv_result)
        rdv_candidat_id = rdv_dict.get("candidat_id")
        
        # Si pas admin, vérifier que le RDV appartient au candidat
        if not is_admin:
            if not candidat or candidat.id != rdv_candidat_id:
                raise HTTPException(status_code=403, detail="Ce rendez-vous ne vous appartient pas")
        else:
            # Si admin, récupérer le candidat du RDV
            if rdv_candidat_id:
                candidat_query = text(f"""
                    SELECT * FROM {schema_name}.candidat 
                    WHERE id = :candidat_id
                    LIMIT 1
                """)
                candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_candidat_id)).first()
                if candidat_result:
                    if hasattr(candidat_result, '_mapping'):
                        candidat_dict = dict(candidat_result._mapping)
                    else:
                        candidat_dict = dict(candidat_result)
                    candidat = type('Candidat', (), candidat_dict)()
                else:
                    raise HTTPException(status_code=404, detail="Candidat du rendez-vous non trouvé")
        
        # Vérifier que la table émargement existe
        if not table_exists_anywhere("emargement_rdv", session, schema_name):
            raise HTTPException(status_code=404, detail="Émargement non disponible")
        
        # Récupérer ou créer l'émargement
        emargement_query = text(f"""
            SELECT id FROM {schema_name}.emargement_rdv WHERE rdv_id = :rdv_id
        """)
        emargement = session.exec(emargement_query.bindparams(rdv_id=rdv_id)).first()
        
        # Extraire les données base64
        if "," in signature:
            signature_base64 = signature.split(",")[1]
        else:
            signature_base64 = signature
        
        # Décoder le base64
        try:
            signature_bytes = base64.b64decode(signature_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Format de signature invalide: {str(e)}")
        
        # Sauvegarder la signature
        signatures_dir = path_config.UPLOAD_DIR / "signatures" / schema_name.lower()
        signatures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"signature_candidat_rdv{rdv_id}_{timestamp}.png"
        file_path = signatures_dir / filename
        with open(file_path, "wb") as f:
            f.write(signature_bytes)
        
        signature_url = f"{path_config.get_mount_path('media')}/signatures/{schema_name.lower()}/{filename}"
        
        # Mettre à jour ou créer l'émargement
        now = datetime.now(timezone.utc)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        if emargement:
            # Mettre à jour
            update_query = text(f"""
                UPDATE {schema_name}.emargement_rdv
                SET signature_candidat = :signature_url,
                    date_signature_candidat = :date_signature,
                    candidat_id = :candidat_id,
                    ip_address = :ip_address,
                    user_agent = :user_agent
                WHERE id = :emargement_id
            """)
            session.exec(update_query.bindparams(
                signature_url=signature_url,
                date_signature=now,
                candidat_id=candidat.id,
                ip_address=ip_address,
                user_agent=user_agent,
                emargement_id=emargement.id
            ))
        else:
            # Créer
            insert_query = text(f"""
                INSERT INTO {schema_name}.emargement_rdv 
                (rdv_id, type_signataire, candidat_id, signature_candidat, 
                 date_signature_candidat, ip_address, user_agent, cree_le)
                VALUES (:rdv_id, :type_signataire, :candidat_id, :signature_url,
                        :date_signature, :ip_address, :user_agent, :cree_le)
            """)
            session.exec(insert_query.bindparams(
                rdv_id=rdv_id,
                type_signataire="candidat",
                candidat_id=candidat.id,
                signature_url=signature_url,
                date_signature=now,
                ip_address=ip_address,
                user_agent=user_agent,
                cree_le=now
            ))
        
        session.commit()
        
        return JSONResponse({
            "status": "success",
            "message": "Émargement enregistré avec succès",
            "date_signature": now.isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'émargement: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'émargement: {str(e)}")


@router.post("/espace-candidat/rdv/{rdv_id}/avis", name="donner_avis_rdv", response_class=JSONResponse)
async def donner_avis_rdv(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    note: int = Form(...),
    avis: str = Form("")
):
    """Permet au candidat de donner son avis sur le conseiller après un RDV"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier si l'utilisateur est admin
        is_admin = current_user.role == "administrateur" or current_user.role == "directeur_general"
        
        # Récupérer le candidat connecté
        candidat = get_candidat_from_user(session, current_user, schema_name)
        
        # Récupérer le RDV pour obtenir le candidat_id
        rdv_query = text(f"""
            SELECT id, candidat_id, statut FROM {schema_name}.rendez_vous 
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        rdv_dict = dict(rdv_result._mapping) if hasattr(rdv_result, '_mapping') else dict(rdv_result)
        rdv_candidat_id = rdv_dict.get("candidat_id")
        
        # Si pas admin, vérifier que le RDV appartient au candidat
        if not is_admin:
            if not candidat or candidat.id != rdv_candidat_id:
                raise HTTPException(status_code=403, detail="Ce rendez-vous ne vous appartient pas")
        else:
            # Si admin, récupérer le candidat du RDV
            if rdv_candidat_id:
                candidat_query = text(f"""
                    SELECT * FROM {schema_name}.candidat 
                    WHERE id = :candidat_id
                    LIMIT 1
                """)
                candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_candidat_id)).first()
                if candidat_result:
                    if hasattr(candidat_result, '_mapping'):
                        candidat_dict = dict(candidat_result._mapping)
                    else:
                        candidat_dict = dict(candidat_result)
                    candidat = type('Candidat', (), candidat_dict)()
                else:
                    raise HTTPException(status_code=404, detail="Candidat du rendez-vous non trouvé")
        
        # Vérifier que la note est valide (1-5)
        if note < 1 or note > 5:
            raise HTTPException(status_code=400, detail="La note doit être entre 1 et 5")
        
        # Vérifier si la colonne existe, sinon on l'ajoute via ALTER TABLE
        try:
            update_query = text(f"""
                UPDATE {schema_name}.rendez_vous
                SET note_conseiller = :note,
                    avis_candidat = :avis
                WHERE id = :rdv_id
            """)
            session.exec(update_query.bindparams(
                note=note,
                avis=avis,
                rdv_id=rdv_id
            ))
            session.commit()
        except Exception as e:
            # Si les colonnes n'existent pas, on les crée
            logger.warning(f"Colonnes d'avis non trouvées, tentative de création: {e}")
            try:
                alter_query1 = text(f"""
                    ALTER TABLE {schema_name}.rendez_vous 
                    ADD COLUMN IF NOT EXISTS note_conseiller INTEGER
                """)
                alter_query2 = text(f"""
                    ALTER TABLE {schema_name}.rendez_vous 
                    ADD COLUMN IF NOT EXISTS avis_candidat TEXT
                """)
                session.exec(alter_query1)
                session.exec(alter_query2)
                session.commit()
                
                # Réessayer la mise à jour
                update_query = text(f"""
                    UPDATE {schema_name}.rendez_vous
                    SET note_conseiller = :note,
                        avis_candidat = :avis
                    WHERE id = :rdv_id
                """)
                session.exec(update_query.bindparams(
                    note=note,
                    avis=avis,
                    rdv_id=rdv_id
                ))
                session.commit()
            except Exception as e2:
                logger.error(f"Erreur lors de la création des colonnes d'avis: {e2}")
                raise HTTPException(status_code=500, detail="Impossible d'enregistrer l'avis")
        
        return JSONResponse({
            "status": "success",
            "message": "Avis enregistré avec succès"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de l'avis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement de l'avis: {str(e)}")


@router.get("/espace-bpi", name="espace_bpi", response_class=HTMLResponse)
async def espace_bpi(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme: Optional[str] = None,
    partenaire_bpi_filter: Optional[str] = Query(None, description="Filtre optionnel par partenaire BPI")
):
    """Espace BPI avec statistiques détaillées - Vue globale sur tous les schémas"""
    try:
        # Récupérer tous les schémas de programmes pour agréger les données
        all_schemas = get_all_program_schemas(session)
        
        if not all_schemas:
            logger.warning("Aucun schéma de programme trouvé")
            all_schemas = []
        
        stats = {}
        
        # Définir les listes de schémas avec les tables nécessaires
        schemas_with_candidat = [s for s in all_schemas if table_exists_anywhere("candidat", session, s)]
        schemas_with_suivi = [s for s in all_schemas if table_exists_anywhere("suivi_mensuel", session, s)]
        
        # Récupérer la liste des partenaires BPI distincts pour le filtre
        partenaires_bpi_list = []
        try:
            union_parts_partenaire = []
            for schema in schemas_with_candidat:
                union_parts_partenaire.append(f"""
                    SELECT DISTINCT partenaire_bpi
                    FROM {schema}.candidat
                    WHERE partenaire_bpi IS NOT NULL AND TRIM(partenaire_bpi) != ''
                """)
            
            if union_parts_partenaire:
                partenaires_query_str = f"""
                    SELECT DISTINCT partenaire_bpi
                    FROM (
                        {' UNION ALL '.join(union_parts_partenaire)}
                    ) AS combined
                    ORDER BY partenaire_bpi
                """
                partenaires_query = text(partenaires_query_str)
                partenaires_results = session.exec(partenaires_query).all()
                partenaires_bpi_list = [row.partenaire_bpi for row in partenaires_results if row.partenaire_bpi]
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des partenaires BPI: {e}")
        
        # Helper pour ajouter le filtre partenaire_bpi à une clause WHERE (uniquement si un filtre est sélectionné)
        def add_partenaire_bpi_to_where(where_clause: str, table_alias: str = "c") -> str:
            """Ajoute le filtre partenaire_bpi à une clause WHERE si un filtre est sélectionné"""
            if not partenaire_bpi_filter:
                return where_clause
            if where_clause:
                return f"{where_clause} AND {table_alias}.partenaire_bpi = '{partenaire_bpi_filter}'"
            else:
                return f"WHERE {table_alias}.partenaire_bpi = '{partenaire_bpi_filter}'"
        
        # 1. Sociologie : homme, femme, nc (agrégé sur tous les schémas)
        if schemas_with_candidat:
            try:
                # Construire la requête UNION ALL pour tous les schémas
                union_parts = []
                for schema in schemas_with_candidat:
                    where_clause = "WHERE statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause += f" AND partenaire_bpi = '{partenaire_bpi_filter}'"
                    
                    union_parts.append(f"""
                        SELECT 
                            CASE 
                                WHEN civilite IS NULL OR TRIM(civilite) = '' THEN 'Non communiqué'
                                -- Normalisation explicite des valeurs connues pour Homme (M, Mr, Monsieur, Homme)
                                WHEN LOWER(TRIM(civilite)) IN ('m', 'mr', 'monsieur', 'homme') THEN 'Homme'
                                -- Normalisation explicite des valeurs connues pour Femme (Mme, Madame, Femme)
                                WHEN LOWER(TRIM(civilite)) IN ('mme', 'madame', 'femme') THEN 'Femme'
                                -- Vérifications avec LIKE pour les variantes contenant ces mots
                                WHEN LOWER(TRIM(civilite)) LIKE '%homme%' OR LOWER(TRIM(civilite)) LIKE '%monsieur%' THEN 'Homme'
                                WHEN LOWER(TRIM(civilite)) LIKE '%femme%' OR LOWER(TRIM(civilite)) LIKE '%madame%' THEN 'Femme'
                                ELSE 'Non communiqué'
                            END as civilite
                        FROM {schema}.candidat
                        {where_clause}
                    """)
                
                sociologie_query_str = f"""
                    SELECT 
                        civilite,
                        COUNT(*) as nombre
                    FROM (
                        {' UNION ALL '.join(union_parts)}
                    ) AS combined
                    GROUP BY civilite
                """
                sociologie_query = text(sociologie_query_str)
                sociologie_results = session.exec(sociologie_query).all()
                total_sociologie = sum(row.nombre for row in sociologie_results)
                stats['sociologie'] = {
                    'homme': 0,
                    'femme': 0,
                    'Non communiqué': 0,
                    'total': total_sociologie
                }
                for row in sociologie_results:
                    civ = (row.civilite or '').strip()
                    if civ.lower() == 'homme':
                        stats['sociologie']['homme'] += row.nombre
                    elif civ.lower() == 'femme':
                        stats['sociologie']['femme'] += row.nombre
                    else:
                        stats['sociologie']['Non communiqué'] += row.nombre
                
                # Calculer les pourcentages
                if total_sociologie > 0:
                    stats['sociologie']['homme_pct'] = round((stats['sociologie']['homme'] / total_sociologie) * 100, 2)
                    stats['sociologie']['femme_pct'] = round((stats['sociologie']['femme'] / total_sociologie) * 100, 2)
                    stats['sociologie']['Non communiqué_pct'] = round((stats['sociologie']['Non communiqué'] / total_sociologie) * 100, 2)
            except Exception as e:
                logger.warning(f"Erreur lors du calcul de la sociologie: {e}")
                stats['sociologie'] = {'homme': 0, 'femme': 0, 'Non communiqué': 0, 'total': 0, 'homme_pct': 0, 'femme_pct': 0, 'Non communiqué_pct': 0}
        
        # 2. Tranche d'âge (agrégé sur tous les schémas)
        if schemas_with_candidat:
            try:
                union_parts = []
                for schema in schemas_with_candidat:
                    where_clause = "WHERE statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause += f" AND partenaire_bpi = '{partenaire_bpi_filter}'"
                    
                    union_parts.append(f"""
                        SELECT 
                            CASE 
                                WHEN date_naissance IS NULL THEN 'Non communiqué'
                                WHEN EXTRACT(YEAR FROM AGE(date_naissance)) < 25 THEN '< 25 ans'
                                WHEN EXTRACT(YEAR FROM AGE(date_naissance)) BETWEEN 25 AND 34 THEN '25-34 ans'
                                WHEN EXTRACT(YEAR FROM AGE(date_naissance)) BETWEEN 35 AND 44 THEN '35-44 ans'
                                WHEN EXTRACT(YEAR FROM AGE(date_naissance)) BETWEEN 45 AND 54 THEN '45-54 ans'
                                WHEN EXTRACT(YEAR FROM AGE(date_naissance)) >= 55 THEN '55+ ans'
                                ELSE 'Non communiqué'
                            END as tranche_age
                        FROM {schema}.candidat
                        {where_clause}
                    """)
                
                age_query_str = f"""
                    SELECT 
                        tranche_age,
                        COUNT(*) as nombre
                    FROM (
                        {' UNION ALL '.join(union_parts)}
                    ) AS combined
                    GROUP BY tranche_age
                """
                age_query = text(age_query_str)
                age_results = session.exec(age_query).all()
                total_age = sum(row.nombre for row in age_results)
                stats['tranche_age'] = {}
                for row in age_results:
                    stats['tranche_age'][row.tranche_age] = {
                        'nombre': row.nombre,
                        'pourcentage': round((row.nombre / total_age) * 100, 2) if total_age > 0 else 0
                    }
                stats['tranche_age']['total'] = total_age
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des tranches d'âge: {e}")
                stats['tranche_age'] = {'total': 0}
        
        # 3. Diplôme (agrégé sur tous les schémas)
        if schemas_with_candidat:
            try:
                union_parts = []
                for schema in schemas_with_candidat:
                    where_clause = "WHERE statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause += f" AND partenaire_bpi = '{partenaire_bpi_filter}'"
                    
                    union_parts.append(f"""
                        SELECT COALESCE(NULLIF(TRIM(niveau_etudes), ''), 'Non communiqué') as diplome
                        FROM {schema}.candidat
                        {where_clause}
                    """)
                
                diplome_query_str = f"""
                    SELECT 
                        diplome,
                        COUNT(*) as nombre
                    FROM (
                        {' UNION ALL '.join(union_parts)}
                    ) AS combined
                    GROUP BY diplome
                    ORDER BY nombre DESC
                """
                diplome_query = text(diplome_query_str)
                diplome_results = session.exec(diplome_query).all()
                total_diplome = sum(row.nombre for row in diplome_results)
                stats['diplome'] = {}
                for row in diplome_results:
                    diplome_value = row.diplome or 'Non communiqué'
                    if diplome_value == 'nc' or diplome_value == '':
                        diplome_value = 'Non communiqué'
                    stats['diplome'][diplome_value] = {
                        'nombre': row.nombre,
                        'pourcentage': round((row.nombre / total_diplome) * 100, 2) if total_diplome > 0 else 0
                    }
                stats['diplome']['total'] = total_diplome
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des diplômes: {e}")
                stats['diplome'] = {'total': 0}
        
        # 4. Situation socio-pro : entrée, sortie, 1 an après (agrégé sur tous les schémas)
        # À l'entrée : utiliser situation_socio de la table preinscription
        # À la sortie : utiliser situation_socioprofessionnelle de suivi_mensuel juste après la date de fin du programme
        # 1 an après : utiliser situation_socioprofessionnelle de suivi_mensuel 1 an après la date de fin du programme
        schemas_with_preinscription = [s for s in all_schemas if table_exists_anywhere("preinscription", session, s)]
        if schemas_with_candidat or schemas_with_suivi:
            try:
                # Situation à l'entrée : utiliser situation_socio de preinscription OU candidat
                union_parts_entree = []
                for schema in schemas_with_preinscription:
                    where_clause = "WHERE c.statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause += f" AND c.partenaire_bpi = '{partenaire_bpi_filter}'"
                    
                    union_parts_entree.append(f"""
                        SELECT CASE 
                            WHEN COALESCE(p.situation_socio, c.situation_socio, '') = '' OR COALESCE(p.situation_socio, c.situation_socio, '') = 'nc' THEN 'Non communiqué'
                            ELSE COALESCE(p.situation_socio, c.situation_socio, 'Non communiqué')
                        END as situation
                        FROM {schema}.preinscription p
                        INNER JOIN {schema}.candidat c ON p.candidat_id = c.id
                        {where_clause}
                    """)
                
                if union_parts_entree:
                    situation_entree_query_str = f"""
                        SELECT 
                            situation,
                            COUNT(*) as nombre
                        FROM (
                            {' UNION ALL '.join(union_parts_entree)}
                        ) AS combined
                        GROUP BY situation
                    """
                    situation_entree_query = text(situation_entree_query_str)
                    situation_entree_results = session.exec(situation_entree_query).all()
                else:
                    situation_entree_results = []
                total_entree = sum(row.nombre for row in situation_entree_results)
                stats['situation_entree'] = {}
                for row in situation_entree_results:
                    situation_value = row.situation or 'Non communiqué'
                    if situation_value == 'nc' or situation_value == '':
                        situation_value = 'Non communiqué'
                    stats['situation_entree'][situation_value] = {
                        'nombre': row.nombre,
                        'pourcentage': round((row.nombre / total_entree) * 100, 2) if total_entree > 0 else 0
                    }
                stats['situation_entree']['total'] = total_entree
                
                # Situation à la sortie : utiliser suivi_mensuel juste après la date de fin du programme
                situation_sortie_all = {}
                if schemas_with_suivi and schemas_with_preinscription:
                    for schema in schemas_with_suivi:
                        situation_sortie_query = text(f"""
                            SELECT 
                                CASE 
                                    WHEN sm.situation_socioprofessionnelle IS NULL OR TRIM(sm.situation_socioprofessionnelle) = '' OR sm.situation_socioprofessionnelle = 'nc' THEN 'Non communiqué'
                                    ELSE sm.situation_socioprofessionnelle
                                END as situation,
                                COUNT(DISTINCT sm.candidat_id) as nombre
                            FROM {schema}.suivi_mensuel sm
                            INNER JOIN {schema}.candidat c ON sm.candidat_id = c.id
                            INNER JOIN {schema}.preinscription p ON p.candidat_id = c.id
                            INNER JOIN public.programme pr ON p.programme_id = pr.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            AND pr.date_fin IS NOT NULL
                            AND sm.mois >= pr.date_fin
                            AND sm.mois <= pr.date_fin + INTERVAL '3 months'
                            AND sm.mois = (
                                SELECT MIN(sm2.mois)
                                FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = sm.candidat_id
                                AND sm2.mois >= pr.date_fin
                            )
                            GROUP BY CASE 
                                WHEN sm.situation_socioprofessionnelle IS NULL OR TRIM(sm.situation_socioprofessionnelle) = '' OR sm.situation_socioprofessionnelle = 'nc' THEN 'Non communiqué'
                                ELSE sm.situation_socioprofessionnelle
                            END
                        """)
                        try:
                            situation_sortie_results = session.exec(situation_sortie_query).all()
                            for row in situation_sortie_results:
                                situation = row.situation or 'Non communiqué'
                                if situation == 'nc' or situation == '':
                                    situation = 'Non communiqué'
                                situation_sortie_all[situation] = situation_sortie_all.get(situation, 0) + row.nombre
                        except Exception as e:
                            logger.debug(f"Erreur pour schéma {schema}: {e}")
                            continue
                
                situation_sortie_results = [type('Row', (), {'situation': k, 'nombre': v})() for k, v in situation_sortie_all.items()]
                total_sortie = sum(row.nombre for row in situation_sortie_results)
                stats['situation_sortie'] = {}
                for row in situation_sortie_results:
                    situation_value = row.situation or 'Non communiqué'
                    if situation_value == 'nc' or situation_value == '':
                        situation_value = 'Non communiqué'
                    stats['situation_sortie'][situation_value] = {
                        'nombre': row.nombre,
                        'pourcentage': round((row.nombre / total_sortie) * 100, 2) if total_sortie > 0 else 0
                    }
                stats['situation_sortie']['total'] = total_sortie
                
                # Situation 1 an après : utiliser suivi_mensuel 1 an après la date de fin du programme
                situation_1an_all = {}
                if schemas_with_suivi and schemas_with_preinscription:
                    for schema in schemas_with_suivi:
                        where_clause_1an = "WHERE c.statut = 'VALIDE'"
                        if partenaire_bpi_filter:
                            where_clause_1an += f" AND c.partenaire_bpi = '{partenaire_bpi_filter}'"
                        
                        situation_1an_query = text(f"""
                            SELECT 
                                CASE 
                                    WHEN sm.situation_socioprofessionnelle IS NULL OR TRIM(sm.situation_socioprofessionnelle) = '' OR sm.situation_socioprofessionnelle = 'nc' THEN 'Non communiqué'
                                    ELSE sm.situation_socioprofessionnelle
                                END as situation,
                                COUNT(DISTINCT sm.candidat_id) as nombre
                            FROM {schema}.suivi_mensuel sm
                            INNER JOIN {schema}.candidat c ON sm.candidat_id = c.id
                            INNER JOIN {schema}.preinscription p ON p.candidat_id = c.id
                            INNER JOIN public.programme pr ON p.programme_id = pr.id
                            {where_clause_1an}
                            AND pr.date_fin IS NOT NULL
                            AND sm.mois >= pr.date_fin + INTERVAL '11 months'
                            AND sm.mois <= pr.date_fin + INTERVAL '13 months'
                            AND sm.mois = (
                                SELECT MIN(sm2.mois)
                                FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = sm.candidat_id
                                AND sm2.mois >= pr.date_fin + INTERVAL '11 months'
                                AND sm2.mois <= pr.date_fin + INTERVAL '13 months'
                            )
                            GROUP BY CASE 
                                WHEN sm.situation_socioprofessionnelle IS NULL OR TRIM(sm.situation_socioprofessionnelle) = '' OR sm.situation_socioprofessionnelle = 'nc' THEN 'Non communiqué'
                                ELSE sm.situation_socioprofessionnelle
                            END
                        """)
                        try:
                            situation_1an_results = session.exec(situation_1an_query).all()
                            for row in situation_1an_results:
                                situation = row.situation or 'Non communiqué'
                                if situation == 'nc' or situation == '':
                                    situation = 'Non communiqué'
                                situation_1an_all[situation] = situation_1an_all.get(situation, 0) + row.nombre
                        except Exception as e:
                            logger.debug(f"Erreur pour schéma {schema}: {e}")
                            continue
                
                situation_1an_results = [type('Row', (), {'situation': k, 'nombre': v})() for k, v in situation_1an_all.items()]
                total_1an = sum(row.nombre for row in situation_1an_results)
                stats['situation_1an'] = {}
                for row in situation_1an_results:
                    situation_value = row.situation or 'Non communiqué'
                    if situation_value == 'nc' or situation_value == '':
                        situation_value = 'Non communiqué'
                    stats['situation_1an'][situation_value] = {
                        'nombre': row.nombre,
                        'pourcentage': round((row.nombre / total_1an) * 100, 2) if total_1an > 0 else 0
                    }
                stats['situation_1an']['total'] = total_1an
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des situations socio-pro: {e}")
                stats['situation_entree'] = {'total': 0}
                stats['situation_sortie'] = {'total': 0}
                stats['situation_1an'] = {'total': 0}
        
        # 5. Domicile adresse : QPV, Hors QPV, QPV limit, Non communiqué (agrégé sur tous les schémas)
        # Utiliser les données de la table eligibilite qui contient les vérifications QPV des deux adresses
        schemas_with_eligibilite = [s for s in all_schemas if table_exists_anywhere("eligibilite", session, s) and table_exists_anywhere("candidat", session, s)]
        if schemas_with_eligibilite:
            try:
                # Compter d'abord tous les candidats valides pour avoir le total
                total_candidats_query_parts = []
                for schema in schemas_with_eligibilite:
                    where_clause_count = "WHERE c.statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause_count += f" AND c.partenaire_bpi = '{partenaire_bpi_filter}'"
                    
                    total_candidats_query_parts.append(f"""
                        SELECT COUNT(*) as total
                        FROM {schema}.candidat c
                        {where_clause_count}
                    """)
                
                total_candidats = 0
                for schema in schemas_with_eligibilite:
                    where_clause_count = "WHERE statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause_count += f" AND partenaire_bpi = '{partenaire_bpi_filter}'"
                    count_query = text(f"SELECT COUNT(*) as total FROM {schema}.candidat {where_clause_count}")
                    result = session.exec(count_query).first()
                    if result:
                        total_candidats += result[0] if isinstance(result, tuple) else result.total
                
                # Récupérer toutes les éligibilités avec leurs détails JSON de tous les schémas
                union_parts = []
                for schema in schemas_with_eligibilite:
                    union_parts.append(f"""
                        SELECT 
                            e.details_json,
                            p.candidat_id
                        FROM {schema}.eligibilite e
                        INNER JOIN {schema}.preinscription p ON e.preinscription_id = p.id
                        INNER JOIN {schema}.candidat c ON p.candidat_id = c.id
                        WHERE c.statut = 'VALIDE'
                        AND e.details_json IS NOT NULL
                    """)
                
                eligibilite_query_str = f"""
                    SELECT details_json, candidat_id
                    FROM (
                        {' UNION ALL '.join(union_parts)}
                    ) AS combined
                """
                eligibilite_query = text(eligibilite_query_str)
                eligibilite_results = session.exec(eligibilite_query).all()
                
                domicile_qpv_counts = {'QPV': 0, 'QPV limit': 0, 'Hors QPV': 0, 'Non communiqué': 0}
                candidats_avec_eligibilite = set()
                
                for row in eligibilite_results:
                    candidats_avec_eligibilite.add(row.candidat_id)
                    try:
                        details = json.loads(row.details_json) if row.details_json else {}
                        # Chercher l'adresse personnelle dans les adresses analysées
                        adresses_analysees = details.get('adresses_analysees', [])
                        qpv_status = 'Non communiqué'
                        
                        for analyse in adresses_analysees:
                            if analyse.get('type') == 'personnelle' and 'resultat' in analyse:
                                resultat = analyse['resultat']
                                nom_qp = resultat.get('nom_qp', '')
                                if nom_qp.startswith('QPV limit'):
                                    qpv_status = 'QPV limit'
                                    break
                                elif nom_qp.startswith('QPV:'):
                                    qpv_status = 'QPV'
                                    break
                                elif nom_qp == 'Aucun QPV' or not nom_qp:
                                    qpv_status = 'Hors QPV'
                        
                        domicile_qpv_counts[qpv_status] = domicile_qpv_counts.get(qpv_status, 0) + 1
                    except Exception as e:
                        logger.debug(f"Erreur lors du parsing JSON pour candidat {row.candidat_id}: {e}")
                        domicile_qpv_counts['Non communiqué'] += 1
                
                # Ajouter les candidats sans éligibilité en "Non communiqué"
                candidats_sans_eligibilite = total_candidats - len(candidats_avec_eligibilite)
                domicile_qpv_counts['Non communiqué'] += candidats_sans_eligibilite
                
                total_domicile = sum(domicile_qpv_counts.values())
                stats['domicile_qpv'] = {}
                for status, count in domicile_qpv_counts.items():
                    stats['domicile_qpv'][status] = {
                        'nombre': count,
                        'pourcentage': round((count / total_domicile) * 100, 2) if total_domicile > 0 else 0
                    }
                stats['domicile_qpv']['total'] = total_domicile
            except Exception as e:
                logger.warning(f"Erreur lors du calcul du domicile QPV: {e}")
                stats['domicile_qpv'] = {'total': 0}
        
        # 6. Entreprise adresse : QPV, Hors QPV, QPV limit, Non communiqué (agrégé sur tous les schémas)
        # Utiliser les données de la table eligibilite qui contient les vérifications QPV des deux adresses
        if schemas_with_eligibilite:
            try:
                # Compter d'abord tous les candidats valides pour avoir le total
                total_candidats_entreprise = 0
                for schema in schemas_with_eligibilite:
                    where_clause_count = "WHERE statut = 'VALIDE'"
                    if partenaire_bpi_filter:
                        where_clause_count += f" AND partenaire_bpi = '{partenaire_bpi_filter}'"
                    count_query = text(f"SELECT COUNT(*) as total FROM {schema}.candidat {where_clause_count}")
                    result = session.exec(count_query).first()
                    if result:
                        total_candidats_entreprise += result[0] if isinstance(result, tuple) else result.total
                
                # Récupérer toutes les éligibilités avec leurs détails JSON de tous les schémas
                union_parts = []
                for schema in schemas_with_eligibilite:
                    union_parts.append(f"""
                        SELECT 
                            e.details_json,
                            p.candidat_id
                        FROM {schema}.eligibilite e
                        INNER JOIN {schema}.preinscription p ON e.preinscription_id = p.id
                        INNER JOIN {schema}.candidat c ON p.candidat_id = c.id
                        WHERE c.statut = 'VALIDE'
                        AND e.details_json IS NOT NULL
                    """)
                
                eligibilite_query_str = f"""
                    SELECT details_json, candidat_id
                    FROM (
                        {' UNION ALL '.join(union_parts)}
                    ) AS combined
                """
                eligibilite_query = text(eligibilite_query_str)
                eligibilite_results = session.exec(eligibilite_query).all()
                
                entreprise_qpv_counts = {'QPV': 0, 'QPV limit': 0, 'Hors QPV': 0, 'Non communiqué': 0}
                candidats_avec_eligibilite_entreprise = set()
                
                for row in eligibilite_results:
                    candidats_avec_eligibilite_entreprise.add(row.candidat_id)
                    try:
                        details = json.loads(row.details_json) if row.details_json else {}
                        # Chercher l'adresse entreprise dans les adresses analysées
                        adresses_analysees = details.get('adresses_analysees', [])
                        qpv_status = 'Non communiqué'
                        
                        for analyse in adresses_analysees:
                            if analyse.get('type') == 'entreprise' and 'resultat' in analyse:
                                resultat = analyse['resultat']
                                nom_qp = resultat.get('nom_qp', '')
                                if nom_qp.startswith('QPV limit'):
                                    qpv_status = 'QPV limit'
                                    break
                                elif nom_qp.startswith('QPV:'):
                                    qpv_status = 'QPV'
                                    break
                                elif nom_qp == 'Aucun QPV' or not nom_qp:
                                    qpv_status = 'Hors QPV'
                        
                        entreprise_qpv_counts[qpv_status] = entreprise_qpv_counts.get(qpv_status, 0) + 1
                    except Exception as e:
                        logger.debug(f"Erreur lors du parsing JSON pour candidat {row.candidat_id}: {e}")
                        entreprise_qpv_counts['Non communiqué'] += 1
                
                # Ajouter les candidats sans éligibilité en "Non communiqué"
                candidats_sans_eligibilite_entreprise = total_candidats_entreprise - len(candidats_avec_eligibilite_entreprise)
                entreprise_qpv_counts['Non communiqué'] += candidats_sans_eligibilite_entreprise
                
                total_entreprise_qpv = sum(entreprise_qpv_counts.values())
                stats['entreprise_qpv'] = {}
                for status, count in entreprise_qpv_counts.items():
                    stats['entreprise_qpv'][status] = {
                        'nombre': count,
                        'pourcentage': round((count / total_entreprise_qpv) * 100, 2) if total_entreprise_qpv > 0 else 0
                    }
                stats['entreprise_qpv']['total'] = total_entreprise_qpv
            except Exception as e:
                logger.warning(f"Erreur lors du calcul de l'entreprise QPV: {e}")
                stats['entreprise_qpv'] = {'total': 0}
        
        # 7. Entrepreneurs entrées et sorties par années (agrégé sur tous les schémas)
        schemas_with_preinscription = [s for s in all_schemas if table_exists_anywhere("preinscription", session, s)]
        if schemas_with_preinscription:
            try:
                # Entrées par année - UNION ALL sur tous les schémas
                union_parts_entrees = []
                for schema in schemas_with_preinscription:
                    union_parts_entrees.append(f"""
                        SELECT 
                            EXTRACT(YEAR FROM cree_le) as annee,
                            candidat_id
                        FROM {schema}.preinscription
                        WHERE candidat_id IN (
                            SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'
                        )
                    """)
                
                entrees_query_str = f"""
                    SELECT 
                        annee,
                        COUNT(DISTINCT candidat_id) as nombre
                    FROM (
                        {' UNION ALL '.join(union_parts_entrees)}
                    ) AS combined
                    GROUP BY annee
                    ORDER BY annee
                """
                entrees_query = text(entrees_query_str)
                entrees_results = session.exec(entrees_query).all()
                stats['entrees_par_annee'] = {}
                for row in entrees_results:
                    if row.annee:
                        stats['entrees_par_annee'][int(row.annee)] = row.nombre
                
                # Sorties par année (basé sur la date de fin du dernier suivi) - UNION ALL sur tous les schémas
                if schemas_with_suivi:
                    union_parts_sorties = []
                    for schema in schemas_with_suivi:
                        union_parts_sorties.append(f"""
                            SELECT 
                                EXTRACT(YEAR FROM MAX(mois)) as annee,
                                candidat_id
                            FROM {schema}.suivi_mensuel
                            WHERE candidat_id IN (
                                SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            )
                            GROUP BY candidat_id
                        """)
                    
                    sorties_query_str = f"""
                        SELECT 
                            annee,
                            COUNT(DISTINCT candidat_id) as nombre
                        FROM (
                            {' UNION ALL '.join(union_parts_sorties)}
                        ) AS combined
                        GROUP BY annee
                    """
                    sorties_query = text(sorties_query_str)
                    sorties_results = session.exec(sorties_query).all()
                    stats['sorties_par_annee'] = {}
                    for row in sorties_results:
                        annee = int(row.annee) if row.annee else None
                        if annee:
                            stats['sorties_par_annee'][annee] = stats['sorties_par_annee'].get(annee, 0) + row.nombre
                else:
                    stats['sorties_par_annee'] = {}
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des entrées/sorties: {e}")
                stats['entrees_par_annee'] = {}
                stats['sorties_par_annee'] = {}
        
        # 8. Entreprises à la rentrée, la sortie et 1 an après (agrégé sur tous les schémas)
        schemas_with_entreprise = [s for s in all_schemas if table_exists_anywhere("entreprise", session, s) and table_exists_anywhere("suivi_mensuel", session, s)]
        if schemas_with_entreprise:
            try:
                # Entreprises à la rentrée, sortie et 1 an après - traiter chaque schéma séparément
                entreprises_entree_total = 0
                entreprises_sortie_total = 0
                entreprises_1an_total = 0
                
                for schema in schemas_with_entreprise:
                    try:
                        # Entreprises à la rentrée (premier suivi ou candidats sans suivi)
                        entreprises_entree_query = text(f"""
                            SELECT COUNT(DISTINCT e.id) as nombre
                            FROM {schema}.entreprise e
                            INNER JOIN {schema}.candidat c ON e.candidat_id = c.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            AND (
                                NOT EXISTS (
                                    SELECT 1 FROM {schema}.suivi_mensuel sm
                                    WHERE sm.candidat_id = c.id
                                )
                                OR EXISTS (
                                    SELECT 1 FROM {schema}.suivi_mensuel sm
                                    WHERE sm.candidat_id = c.id
                                    AND sm.mois = (
                                        SELECT MIN(mois) FROM {schema}.suivi_mensuel sm2
                                        WHERE sm2.candidat_id = c.id
                                    )
                                )
                            )
                        """)
                        result = session.exec(entreprises_entree_query).first()
                        entreprises_entree_total += result.nombre if result else 0
                        
                        # Entreprises à la sortie (dernier suivi avec statut_programme = 'termine' ou 'abandonne')
                        entreprises_sortie_query = text(f"""
                            SELECT COUNT(DISTINCT e.id) as nombre
                            FROM {schema}.entreprise e
                            INNER JOIN {schema}.candidat c ON e.candidat_id = c.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            AND EXISTS (
                                SELECT 1 FROM {schema}.suivi_mensuel sm
                                WHERE sm.candidat_id = c.id
                                AND sm.mois = (
                                    SELECT MAX(mois) FROM {schema}.suivi_mensuel sm2
                                    WHERE sm2.candidat_id = c.id
                                )
                                AND (sm.statut_programme = 'termine' OR sm.statut_programme = 'abandonne')
                            )
                        """)
                        result = session.exec(entreprises_sortie_query).first()
                        entreprises_sortie_total += result.nombre if result else 0
                        
                        # Entreprises 1 an après (suivi avec statut_programme = 'termine' ou 'abandonne')
                        entreprises_1an_query = text(f"""
                            SELECT COUNT(DISTINCT e.id) as nombre
                            FROM {schema}.entreprise e
                            INNER JOIN {schema}.candidat c ON e.candidat_id = c.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            AND EXISTS (
                                SELECT 1 FROM {schema}.suivi_mensuel sm
                                WHERE sm.candidat_id = c.id
                                AND sm.mois >= (
                                    SELECT MAX(mois) + INTERVAL '12 months' - INTERVAL '1 month'
                                    FROM {schema}.suivi_mensuel sm2
                                    WHERE sm2.candidat_id = c.id
                                    AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                                )
                                AND sm.mois <= (
                                    SELECT MAX(mois) + INTERVAL '12 months' + INTERVAL '1 month'
                                    FROM {schema}.suivi_mensuel sm2
                                    WHERE sm2.candidat_id = c.id
                                    AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                                )
                            )
                        """)
                        result = session.exec(entreprises_1an_query).first()
                        entreprises_1an_total += result.nombre if result else 0
                    except Exception as e:
                        logger.debug(f"Erreur pour schéma {schema}: {e}")
                        continue
                
                stats['entreprises_entree'] = entreprises_entree_total
                stats['entreprises_sortie'] = entreprises_sortie_total
                stats['entreprises_1an'] = entreprises_1an_total
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des entreprises: {e}")
                stats['entreprises_entree'] = 0
                stats['entreprises_sortie'] = 0
                stats['entreprises_1an'] = 0
        
        # 9. Chiffres d'affaires : entrée, sortie et 1 an après (agrégé sur tous les schémas)
        # Utiliser les intervalles pour l'entrée (table entreprise) et convertir en intervalles pour sortie/1an (suivi_mensuel)
        
        # Fonction pour convertir un montant (float) en intervalle
        def ca_to_intervalle(montant):
            if montant is None:
                return 'Non communiqué'
            try:
                montant_float = float(montant)
                if montant_float < 10000:
                    return '0 - 10 000 €'
                elif montant_float < 50000:
                    return '10 000 - 50 000 €'
                elif montant_float < 100000:
                    return '50 000 - 100 000 €'
                elif montant_float < 500000:
                    return '100 000 - 500 000 €'
                elif montant_float < 1000000:
                    return '500 000 - 1 000 000 €'
                else:
                    return '1 000 000 € et plus'
            except (ValueError, TypeError):
                return 'Non communiqué'
        
        schemas_with_entreprise = [s for s in all_schemas if table_exists_anywhere("entreprise", session, s) and table_exists_anywhere("candidat", session, s)]
        if schemas_with_entreprise:
            try:
                # CA à l'entrée : utiliser les intervalles de la table entreprise
                ca_entree_intervalles = {
                    '0 - 10 000 €': 0,
                    '10 000 - 50 000 €': 0,
                    '50 000 - 100 000 €': 0,
                    '100 000 - 500 000 €': 0,
                    '500 000 - 1 000 000 €': 0,
                    '1 000 000 € et plus': 0,
                    'Non communiqué': 0
                }
                
                for schema in schemas_with_entreprise:
                    try:
                        ca_entree_query = text(f"""
                            SELECT 
                                CASE 
                                    WHEN chiffre_affaires IS NULL OR TRIM(chiffre_affaires) = '' THEN 'Non communiqué'
                                    ELSE chiffre_affaires
                                END as intervalle,
                                COUNT(*) as nombre
                            FROM {schema}.entreprise e
                            INNER JOIN {schema}.candidat c ON e.candidat_id = c.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            GROUP BY CASE 
                                WHEN chiffre_affaires IS NULL OR TRIM(chiffre_affaires) = '' THEN 'Non communiqué'
                                ELSE chiffre_affaires
                            END
                        """)
                        results = session.exec(ca_entree_query).all()
                        for row in results:
                            intervalle = row.intervalle or 'Non communiqué'
                            if intervalle not in ca_entree_intervalles:
                                intervalle = 'Non communiqué'
                            ca_entree_intervalles[intervalle] = ca_entree_intervalles.get(intervalle, 0) + row.nombre
                    except Exception as e:
                        logger.debug(f"Erreur pour schéma {schema}: {e}")
                        continue
                
                stats['ca_entree'] = ca_entree_intervalles
                stats['ca_entree']['total'] = sum(ca_entree_intervalles.values())
                
                # CA à la sortie : convertir chiffre_affaires_actuel en intervalles
                ca_sortie_intervalles = {
                    '0 - 10 000 €': 0,
                    '10 000 - 50 000 €': 0,
                    '50 000 - 100 000 €': 0,
                    '100 000 - 500 000 €': 0,
                    '500 000 - 1 000 000 €': 0,
                    '1 000 000 € et plus': 0,
                    'Non communiqué': 0
                }
                
                # CA 1 an après : convertir chiffre_affaires_actuel en intervalles
                ca_1an_intervalles = {
                    '0 - 10 000 €': 0,
                    '10 000 - 50 000 €': 0,
                    '50 000 - 100 000 €': 0,
                    '100 000 - 500 000 €': 0,
                    '500 000 - 1 000 000 €': 0,
                    '1 000 000 € et plus': 0,
                    'Non communiqué': 0
                }
                
                if schemas_with_suivi:
                    for schema in schemas_with_suivi:
                        try:
                            # CA à la sortie
                            ca_sortie_query = text(f"""
                                SELECT chiffre_affaires_actuel
                                FROM {schema}.suivi_mensuel
                                WHERE candidat_id IN (
                                    SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                                )
                                AND mois = (
                                    SELECT MAX(mois) FROM {schema}.suivi_mensuel sm2
                                    WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                    AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                                )
                                AND (statut_programme = 'termine' OR statut_programme = 'abandonne')
                            """)
                            results = session.exec(ca_sortie_query).all()
                            for row in results:
                                ca_value = None
                                if hasattr(row, 'chiffre_affaires_actuel'):
                                    ca_value = row.chiffre_affaires_actuel
                                elif isinstance(row, (tuple, list)) and len(row) > 0:
                                    ca_value = row[0]
                                elif hasattr(row, '_mapping'):
                                    ca_value = row._mapping.get('chiffre_affaires_actuel')
                                intervalle = ca_to_intervalle(ca_value)
                                ca_sortie_intervalles[intervalle] = ca_sortie_intervalles.get(intervalle, 0) + 1
                            
                            # CA 1 an après
                            ca_1an_query = text(f"""
                                SELECT chiffre_affaires_actuel
                                FROM {schema}.suivi_mensuel
                                WHERE candidat_id IN (
                                    SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                                )
                                AND mois >= (
                                    SELECT MAX(mois) + INTERVAL '12 months' - INTERVAL '1 month'
                                    FROM {schema}.suivi_mensuel sm2
                                    WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                    AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                                )
                                AND mois <= (
                                    SELECT MAX(mois) + INTERVAL '12 months' + INTERVAL '1 month'
                                    FROM {schema}.suivi_mensuel sm2
                                    WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                    AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                                )
                            """)
                            results = session.exec(ca_1an_query).all()
                            for row in results:
                                ca_value = None
                                if hasattr(row, 'chiffre_affaires_actuel'):
                                    ca_value = row.chiffre_affaires_actuel
                                elif isinstance(row, (tuple, list)) and len(row) > 0:
                                    ca_value = row[0]
                                elif hasattr(row, '_mapping'):
                                    ca_value = row._mapping.get('chiffre_affaires_actuel')
                                intervalle = ca_to_intervalle(ca_value)
                                ca_1an_intervalles[intervalle] = ca_1an_intervalles.get(intervalle, 0) + 1
                        except Exception as e:
                            logger.debug(f"Erreur pour schéma {schema}: {e}")
                            continue
                
                stats['ca_sortie'] = ca_sortie_intervalles
                stats['ca_sortie']['total'] = sum(ca_sortie_intervalles.values())
                stats['ca_1an'] = ca_1an_intervalles
                stats['ca_1an']['total'] = sum(ca_1an_intervalles.values())
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des CA: {e}")
                stats['ca_entree'] = {
                    '0 - 10 000 €': 0,
                    '10 000 - 50 000 €': 0,
                    '50 000 - 100 000 €': 0,
                    '100 000 - 500 000 €': 0,
                    '500 000 - 1 000 000 €': 0,
                    '1 000 000 € et plus': 0,
                    'Non communiqué': 0,
                    'total': 0
                }
                stats['ca_sortie'] = {
                    '0 - 10 000 €': 0,
                    '10 000 - 50 000 €': 0,
                    '50 000 - 100 000 €': 0,
                    '100 000 - 500 000 €': 0,
                    '500 000 - 1 000 000 €': 0,
                    '1 000 000 € et plus': 0,
                    'Non communiqué': 0,
                    'total': 0
                }
                stats['ca_1an'] = {
                    '0 - 10 000 €': 0,
                    '10 000 - 50 000 €': 0,
                    '50 000 - 100 000 €': 0,
                    '100 000 - 500 000 €': 0,
                    '500 000 - 1 000 000 €': 0,
                    '1 000 000 € et plus': 0,
                    'Non communiqué': 0,
                    'total': 0
                }
        
        # 10. Changement de statuts : entrée, sortie et 1 an après (agrégé sur tous les schémas)
        # À l'entrée : utiliser raison_sociale de la table entreprise
        # À la sortie et 1 an après : utiliser statut_juridique du suivi_mensuel
        schemas_with_entreprise = [s for s in all_schemas if table_exists_anywhere("entreprise", session, s) and table_exists_anywhere("candidat", session, s)]
        if schemas_with_entreprise:
            try:
                # Statuts à l'entrée : utiliser raison_sociale de la table entreprise
                statut_entree_all = {}
                
                for schema in schemas_with_entreprise:
                    try:
                        statut_entree_query = text(f"""
                            SELECT 
                                CASE 
                                    WHEN raison_sociale IS NULL OR TRIM(raison_sociale) = '' THEN 'Non communiqué'
                                    ELSE raison_sociale
                                END as statut,
                                COUNT(DISTINCT e.candidat_id) as nombre
                            FROM {schema}.entreprise e
                            INNER JOIN {schema}.candidat c ON e.candidat_id = c.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            GROUP BY CASE 
                                WHEN raison_sociale IS NULL OR TRIM(raison_sociale) = '' THEN 'Non communiqué'
                                ELSE raison_sociale
                            END
                        """)
                        results = session.exec(statut_entree_query).all()
                        for row in results:
                            statut = row.statut or 'Non communiqué'
                            if statut == 'nc' or statut == '':
                                statut = 'Non communiqué'
                            statut_entree_all[statut] = statut_entree_all.get(statut, 0) + row.nombre
                    except Exception as e:
                        logger.debug(f"Erreur pour schéma {schema}: {e}")
                        continue
                
                # Agréger les résultats pour l'entrée
                total_statut_entree = sum(statut_entree_all.values())
                stats['statut_entree'] = {}
                for statut, nombre in statut_entree_all.items():
                    statut_value = statut if statut != 'nc' and statut != '' else 'Non communiqué'
                    stats['statut_entree'][statut_value] = {
                        'nombre': nombre,
                        'pourcentage': round((nombre / total_statut_entree) * 100, 2) if total_statut_entree > 0 else 0
                    }
                stats['statut_entree']['total'] = total_statut_entree
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des statuts à l'entrée: {e}")
                stats['statut_entree'] = {'total': 0}
        
        # Statuts à la sortie et 1 an après : utiliser statut_juridique du suivi_mensuel
        if schemas_with_suivi:
            try:
                statut_sortie_all = {}
                statut_1an_all = {}
                
                for schema in schemas_with_suivi:
                    try:
                        # Statuts à la sortie
                        statut_sortie_query = text(f"""
                            SELECT 
                                CASE 
                                    WHEN statut_juridique IS NULL OR TRIM(statut_juridique) = '' THEN 'Non communiqué'
                                    ELSE statut_juridique
                                END as statut,
                                COUNT(DISTINCT candidat_id) as nombre
                            FROM {schema}.suivi_mensuel
                            WHERE candidat_id IN (
                                SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            )
                            AND mois = (
                                SELECT MAX(mois) FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                            )
                            AND (statut_programme = 'termine' OR statut_programme = 'abandonne')
                            GROUP BY CASE 
                                WHEN statut_juridique IS NULL OR TRIM(statut_juridique) = '' THEN 'Non communiqué'
                                ELSE statut_juridique
                            END
                        """)
                        results = session.exec(statut_sortie_query).all()
                        for row in results:
                            statut = row.statut or 'Non communiqué'
                            if statut == 'nc' or statut == '':
                                statut = 'Non communiqué'
                            statut_sortie_all[statut] = statut_sortie_all.get(statut, 0) + row.nombre
                        
                        # Statuts 1 an après (suivi avec statut_programme = 'termine' ou 'abandonne')
                        statut_1an_query = text(f"""
                            SELECT 
                                CASE 
                                    WHEN statut_juridique IS NULL OR TRIM(statut_juridique) = '' THEN 'Non communiqué'
                                    ELSE statut_juridique
                                END as statut,
                                COUNT(DISTINCT candidat_id) as nombre
                            FROM {schema}.suivi_mensuel
                            WHERE candidat_id IN (
                                SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            )
                            AND mois >= (
                                SELECT MAX(mois) + INTERVAL '12 months' - INTERVAL '1 month'
                                FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                            )
                            AND mois <= (
                                SELECT MAX(mois) + INTERVAL '12 months' + INTERVAL '1 month'
                                FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                            )
                            GROUP BY CASE 
                                WHEN statut_juridique IS NULL OR TRIM(statut_juridique) = '' THEN 'Non communiqué'
                                ELSE statut_juridique
                            END
                        """)
                        results = session.exec(statut_1an_query).all()
                        for row in results:
                            statut = row.statut or 'Non communiqué'
                            if statut == 'nc' or statut == '':
                                statut = 'Non communiqué'
                            statut_1an_all[statut] = statut_1an_all.get(statut, 0) + row.nombre
                    except Exception as e:
                        logger.debug(f"Erreur pour schéma {schema}: {e}")
                        continue
                
                # Agréger les résultats pour la sortie
                total_statut_sortie = sum(statut_sortie_all.values())
                stats['statut_sortie'] = {}
                for statut, nombre in statut_sortie_all.items():
                    statut_value = statut if statut != 'nc' and statut != '' else 'Non communiqué'
                    stats['statut_sortie'][statut_value] = {
                        'nombre': nombre,
                        'pourcentage': round((nombre / total_statut_sortie) * 100, 2) if total_statut_sortie > 0 else 0
                    }
                stats['statut_sortie']['total'] = total_statut_sortie
                
                # Agréger les résultats pour 1 an après
                total_statut_1an = sum(statut_1an_all.values())
                stats['statut_1an'] = {}
                for statut, nombre in statut_1an_all.items():
                    statut_value = statut if statut != 'nc' and statut != '' else 'Non communiqué'
                    stats['statut_1an'][statut_value] = {
                        'nombre': nombre,
                        'pourcentage': round((nombre / total_statut_1an) * 100, 2) if total_statut_1an > 0 else 0
                    }
                stats['statut_1an']['total'] = total_statut_1an
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des statuts (sortie/1an): {e}")
                if 'statut_sortie' not in stats:
                    stats['statut_sortie'] = {'total': 0}
                if 'statut_1an' not in stats:
                    stats['statut_1an'] = {'total': 0}
        
        # 11. Répartition par secteur d'activités (agrégé sur tous les schémas)
        schemas_with_entreprise_all = [s for s in all_schemas if table_exists_anywhere("candidat", session, s) and table_exists_anywhere("entreprise", session, s)]
        if schemas_with_entreprise_all:
            try:
                # Secteurs d'activités - traiter chaque schéma séparément
                secteur_existant_all = {}
                secteur_projet_all = {}
                secteur_tous_all = {}
                
                for schema in schemas_with_entreprise_all:
                    try:
                        # Entreprises existantes (avec SIRET)
                        secteur_existant_query = text(f"""
                            SELECT 
                                COALESCE(e.code_naf, c.secteur_activite, 'nc') as secteur,
                                COUNT(*) as nombre
                            FROM {schema}.entreprise e
                            INNER JOIN {schema}.candidat c ON e.candidat_id = c.id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            AND e.siret IS NOT NULL
                            GROUP BY COALESCE(e.code_naf, c.secteur_activite, 'nc')
                        """)
                        results = session.exec(secteur_existant_query).all()
                        for row in results:
                            secteur = row.secteur or 'nc'
                            secteur_existant_all[secteur] = secteur_existant_all.get(secteur, 0) + row.nombre
                        
                        # Projets non immatriculés (sans SIRET)
                        secteur_projet_query = text(f"""
                            SELECT 
                                COALESCE(c.secteur_activite, 'nc') as secteur,
                                COUNT(*) as nombre
                            FROM {schema}.candidat c
                            LEFT JOIN {schema}.entreprise e ON c.id = e.candidat_id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            AND (e.siret IS NULL OR e.siret = '')
                            GROUP BY COALESCE(c.secteur_activite, 'nc')
                        """)
                        results = session.exec(secteur_projet_query).all()
                        for row in results:
                            secteur = row.secteur or 'nc'
                            secteur_projet_all[secteur] = secteur_projet_all.get(secteur, 0) + row.nombre
                        
                        # Tous projets confondus
                        secteur_tous_query = text(f"""
                            SELECT 
                                COALESCE(e.code_naf, c.secteur_activite, 'nc') as secteur,
                                COUNT(*) as nombre
                            FROM {schema}.candidat c
                            LEFT JOIN {schema}.entreprise e ON c.id = e.candidat_id
                            WHERE c.statut = 'VALIDE'{" AND c.partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            GROUP BY COALESCE(e.code_naf, c.secteur_activite, 'nc')
                        """)
                        results = session.exec(secteur_tous_query).all()
                        for row in results:
                            secteur = row.secteur or 'nc'
                            secteur_tous_all[secteur] = secteur_tous_all.get(secteur, 0) + row.nombre
                    except Exception as e:
                        logger.debug(f"Erreur pour schéma {schema}: {e}")
                        continue
                
                # Agréger les résultats
                total_secteur_existant = sum(secteur_existant_all.values())
                stats['secteur_existant'] = {}
                for secteur, nombre in secteur_existant_all.items():
                    stats['secteur_existant'][secteur] = {
                        'nombre': nombre,
                        'pourcentage': round((nombre / total_secteur_existant) * 100, 2) if total_secteur_existant > 0 else 0
                    }
                stats['secteur_existant']['total'] = total_secteur_existant
                
                total_secteur_projet = sum(secteur_projet_all.values())
                stats['secteur_projet'] = {}
                for secteur, nombre in secteur_projet_all.items():
                    stats['secteur_projet'][secteur] = {
                        'nombre': nombre,
                        'pourcentage': round((nombre / total_secteur_projet) * 100, 2) if total_secteur_projet > 0 else 0
                    }
                stats['secteur_projet']['total'] = total_secteur_projet
                
                total_secteur_tous = sum(secteur_tous_all.values())
                stats['secteur_tous'] = {}
                for secteur, nombre in secteur_tous_all.items():
                    stats['secteur_tous'][secteur] = {
                        'nombre': nombre,
                        'pourcentage': round((nombre / total_secteur_tous) * 100, 2) if total_secteur_tous > 0 else 0
                    }
                stats['secteur_tous']['total'] = total_secteur_tous
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des secteurs: {e}")
                stats['secteur_existant'] = {'total': 0}
                stats['secteur_projet'] = {'total': 0}
                stats['secteur_tous'] = {'total': 0}
        
        # 12. Répartition par nombre de salariés : entrée, sortie et 1 an après (agrégé sur tous les schémas)
        if schemas_with_suivi:
            try:
                # Salariés à l'entrée, sortie et 1 an après - traiter chaque schéma séparément
                salarie_entree_all = {}
                salarie_sortie_all = {}
                salarie_1an_all = {}
                
                for schema in schemas_with_suivi:
                    try:
                        # Salariés à l'entrée
                        salarie_entree_query = text(f"""
                            SELECT 
                                COALESCE(nb_cdi, 0) + COALESCE(nb_cdd, 0) + COALESCE(nb_stagiaires, 0) + COALESCE(nb_alternants, 0) as total_salaries,
                                COUNT(DISTINCT candidat_id) as nombre
                            FROM {schema}.suivi_mensuel
                            WHERE candidat_id IN (
                                SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            )
                            AND mois = (
                                SELECT MIN(mois) FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                            )
                            GROUP BY COALESCE(nb_cdi, 0) + COALESCE(nb_cdd, 0) + COALESCE(nb_stagiaires, 0) + COALESCE(nb_alternants, 0)
                        """)
                        results = session.exec(salarie_entree_query).all()
                        for row in results:
                            tranche = f"{int(row.total_salaries)} salarié(s)"
                            salarie_entree_all[tranche] = salarie_entree_all.get(tranche, 0) + row.nombre
                        
                        # Salariés à la sortie
                        salarie_sortie_query = text(f"""
                            SELECT 
                                COALESCE(nb_cdi, 0) + COALESCE(nb_cdd, 0) + COALESCE(nb_stagiaires, 0) + COALESCE(nb_alternants, 0) as total_salaries,
                                COUNT(DISTINCT candidat_id) as nombre
                            FROM {schema}.suivi_mensuel
                            WHERE candidat_id IN (
                                SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            )
                            AND mois = (
                                SELECT MAX(mois) FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                            )
                            GROUP BY COALESCE(nb_cdi, 0) + COALESCE(nb_cdd, 0) + COALESCE(nb_stagiaires, 0) + COALESCE(nb_alternants, 0)
                        """)
                        results = session.exec(salarie_sortie_query).all()
                        for row in results:
                            tranche = f"{int(row.total_salaries)} salarié(s)"
                            salarie_sortie_all[tranche] = salarie_sortie_all.get(tranche, 0) + row.nombre
                        
                        # Salariés 1 an après (suivi avec statut_programme = 'termine' ou 'abandonne')
                        salarie_1an_query = text(f"""
                            SELECT 
                                COALESCE(nb_cdi, 0) + COALESCE(nb_cdd, 0) + COALESCE(nb_stagiaires, 0) + COALESCE(nb_alternants, 0) as total_salaries,
                                COUNT(DISTINCT candidat_id) as nombre
                            FROM {schema}.suivi_mensuel
                            WHERE candidat_id IN (
                                SELECT id FROM {schema}.candidat WHERE statut = 'VALIDE'{" AND partenaire_bpi = '" + partenaire_bpi_filter + "'" if partenaire_bpi_filter else ""}
                            )
                            AND mois >= (
                                SELECT MAX(mois) + INTERVAL '12 months' - INTERVAL '1 month'
                                FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                            )
                            AND mois <= (
                                SELECT MAX(mois) + INTERVAL '12 months' + INTERVAL '1 month'
                                FROM {schema}.suivi_mensuel sm2
                                WHERE sm2.candidat_id = suivi_mensuel.candidat_id
                                AND (sm2.statut_programme = 'termine' OR sm2.statut_programme = 'abandonne')
                            )
                            GROUP BY COALESCE(nb_cdi, 0) + COALESCE(nb_cdd, 0) + COALESCE(nb_stagiaires, 0) + COALESCE(nb_alternants, 0)
                        """)
                        results = session.exec(salarie_1an_query).all()
                        for row in results:
                            tranche = f"{int(row.total_salaries)} salarié(s)"
                            salarie_1an_all[tranche] = salarie_1an_all.get(tranche, 0) + row.nombre
                    except Exception as e:
                        logger.debug(f"Erreur pour schéma {schema}: {e}")
                        continue
                
                # Agréger les résultats
                stats['salarie_entree'] = salarie_entree_all.copy()
                stats['salarie_entree']['total'] = sum(salarie_entree_all.values())
                
                stats['salarie_sortie'] = salarie_sortie_all.copy()
                stats['salarie_sortie']['total'] = sum(salarie_sortie_all.values())
                
                stats['salarie_1an'] = salarie_1an_all.copy()
                stats['salarie_1an']['total'] = sum(salarie_1an_all.values())
            except Exception as e:
                logger.warning(f"Erreur lors du calcul des salariés: {e}")
                stats['salarie_entree'] = {'total': 0}
                stats['salarie_sortie'] = {'total': 0}
                stats['salarie_1an'] = {'total': 0}
        
        return templates.TemplateResponse(
            "pages/espace_bpi.html",
            {
                "request": request,
                "utilisateur": current_user,
                "stats": stats,
                "schema_name": "global",  # Vue globale sur tous les schémas
                "partenaires_bpi_list": partenaires_bpi_list,
                "partenaire_bpi_filter": partenaire_bpi_filter
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur dans espace_bpi: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de l'espace BPI: {str(e)}")

