from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from sqlalchemy import text
from datetime import datetime, date, timezone
from typing import List, Optional
import secrets
import string
import logging
import base64

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.program_schema_integration import get_schema_from_request, get_schema_routing_service, SchemaRoutingService, table_exists_anywhere
from ..core.config import settings
from ..core.path_config import path_config
from ..models.base import User, Programme
from ..models.event import Event, InvitationEvent, PresenceEvent
from ..models.enums import MethodeSignatureEvent
from ..schemas.event_schemas import EventCreate, EventUpdate, InvitationEventCreate, PresenceEventCreate
from ..services.event_service import EventService
from ..core.security import get_current_user
from ..templates import templates

router = APIRouter()
event_service = EventService()
logger = logging.getLogger(__name__)

# === ROUTES PRINCIPALES ===

@router.get("/", name="liste_events", response_class=HTMLResponse)
async def liste_events(
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme_id: Optional[int] = None
):
    """Liste des événements"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [liste_events] Schéma configuré: {schema_name}")
        
        # Configurer explicitement le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            logger.warning(f"⚠️ Table event n'existe pas dans le schéma {schema_name}")
            return templates.TemplateResponse("pages/events/liste.html", {
                "request": request,
                "events": [],
                "stats": {"total_events": 0, "events_planifies": 0, "events_en_cours": 0, "events_termines": 0},
                "programmes": [],
                "current_user": current_user,
                "utilisateur": current_user,
                "programme_id": programme_id,
                "schema_name": schema_name
            })
        
        # Construire la requête SQL directe
        base_query = f"""
            SELECT e.id, e.titre, e.description, e.programme_id, e.date_debut, e.date_fin,
                   e.heure_debut, e.heure_fin, e.lieu, e.statut, e.organisateur_id,
                   e.cree_le, e.modifie_le,
                   p.nom as programme_nom, p.code as programme_code,
                   u.nom_complet as organisateur_nom
            FROM {schema_name}.event e
            LEFT JOIN public.programme p ON e.programme_id = p.id
            LEFT JOIN public."user" u ON e.organisateur_id = u.id
        """
        
        where_conditions = []
        params = {}
        
        if programme_id:
            where_conditions.append("e.programme_id = :programme_id")
            params['programme_id'] = programme_id
        
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        base_query += " ORDER BY e.date_debut DESC"
        
        # Exécuter la requête
        if params:
            query = text(base_query).bindparams(**params)
        else:
            query = text(base_query)
        
        events_results = db.exec(query).all()
        
        # Convertir les résultats en objets simples
        events = []
        for row in events_results:
            events.append(type('Event', (), {
                'id': row.id,
                'titre': row.titre,
                'description': row.description,
                'programme_id': row.programme_id,
                'date_debut': row.date_debut,
                'date_fin': row.date_fin,
                'heure_debut': row.heure_debut,
                'heure_fin': row.heure_fin,
                'lieu': row.lieu,
                'statut': row.statut,
                'organisateur_id': row.organisateur_id,
                'organisateur_nom': row.organisateur_nom,
                'programme': type('Programme', (), {
                    'id': row.programme_id,
                    'code': row.programme_code,
                    'nom': row.programme_nom
                })() if row.programme_id else None,
                'cree_le': row.cree_le,
                'modifie_le': row.modifie_le
            })())
        
        # Récupérer les statistiques
        try:
            stats = event_service.get_event_stats(db, schema_name)
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des statistiques: {e}")
            stats = {"total_events": 0, "events_planifies": 0, "events_en_cours": 0, "events_termines": 0}
        
        # Récupérer les programmes
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY code")
        programmes_results = db.exec(programmes_query).all()
        programmes = [type('Programme', (), {
            'id': p.id,
            'code': p.code,
            'nom': p.nom
        })() for p in programmes_results]
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/liste.html", {
            "request": request,
            "events": events,
            "stats": stats,
            "programmes": programmes,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_id": programme_id,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans liste_events: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.get("/nouveau", name="form_event", response_class=HTMLResponse)
async def form_event(
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [form_event] Schéma configuré: {schema_name}")
        
        # Récupérer le programme correspondant au paramètre programme de l'URL
        programme_param = request.query_params.get('programme', '').upper()
        selected_programme = None
        
        if programme_param:
            # Chercher le programme par son code dans le schéma public (explicite)
            programme_query = text("SELECT * FROM public.programme WHERE code = :code")
            programme_result = db.exec(programme_query.bindparams(code=programme_param)).first()
            if programme_result:
                selected_programme = type('Programme', (), {
                    'id': programme_result.id,
                    'code': programme_result.code,
                    'nom': programme_result.nom
                })()
        
        # Programme est dans le schéma public - récupérer tous les programmes
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY code")
        programmes_results = db.exec(programmes_query).all()
        programmes = [type('Programme', (), {
            'id': p.id,
            'code': p.code,
            'nom': p.nom
        })() for p in programmes_results]
        
        # Récupérer les utilisateurs pour la sélection de l'organisateur
        users_query = text("SELECT id, nom_complet, email, role FROM public.\"user\" WHERE actif = true ORDER BY nom_complet")
        users_results = db.exec(users_query).all()
        users = [type('User', (), {
            'id': u.id,
            'nom_complet': u.nom_complet,
            'email': u.email,
            'role': u.role
        })() for u in users_results]
        
        return templates.TemplateResponse("pages/events/form.html", {
            "request": request,
            "programmes": programmes,
            "selected_programme": selected_programme,
            "users": users,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name,
            "is_edit": False
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans form_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du formulaire: {str(e)}")

@router.post("/nouveau", name="creer_event")
async def creer_event(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    heure_debut: str = Form(""),
    heure_fin: str = Form(""),
    lieu: str = Form(""),
    programme_id: int = Form(...),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Créer un nouvel événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        logger.info(f"🔍 [creer_event] Schéma configuré: {schema_name}")
        logger.info(f"🔍 [creer_event] programme_id reçu: {programme_id}")
        
        # Vérifier que le programme existe et correspond au schéma
        programme_query = text("SELECT id, code FROM public.programme WHERE id = :programme_id AND actif = true")
        programme_result = db.exec(programme_query.bindparams(programme_id=programme_id)).first()
        if not programme_result:
            logger.warning(f"⚠️ [creer_event] Programme {programme_id} non trouvé ou inactif")
            raise HTTPException(status_code=400, detail=f"Programme invalide: {programme_id}")
        
        logger.info(f"🔍 [creer_event] Programme trouvé: {programme_result.code} (id: {programme_result.id})")
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Table event non trouvée dans ce programme")
        
        # Conversion des heures
        heure_debut_dt = None
        heure_fin_dt = None
        
        if heure_debut:
            try:
                heure_debut_dt = datetime.strptime(f"{date_debut} {heure_debut}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        if heure_fin:
            try:
                heure_fin_dt = datetime.strptime(f"{date_fin} {heure_fin}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        event_data = EventCreate(
            titre=titre,
            description=description if description else None,
            date_debut=date_debut,
            date_fin=date_fin,
            heure_debut=heure_debut_dt,
            heure_fin=heure_fin_dt,
            lieu=lieu if lieu else None,
            programme_id=programme_id,
            organisateur_id=current_user.id
        )
        
        event_result = event_service.create_event(event_data, db, schema_name)
        if not event_result:
            raise HTTPException(status_code=500, detail="Erreur lors de la création de l'événement")
        
        # Récupérer l'événement complet après création
        event_dict = event_service.get_event(event_result['id'], db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement créé mais non trouvé")
        
        presences_data = event_service.get_presences_with_combined_status(event_dict['id'], db, schema_name)
        stats = event_service.get_presence_stats_with_invitations(event_dict['id'], db, schema_name)
        
        # Convertir l'événement en objet simple pour le template
        event_obj = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'programme_id': event_dict['programme_id'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'heure_debut': event_dict.get('heure_debut'),
            'heure_fin': event_dict.get('heure_fin'),
            'lieu': event_dict.get('lieu'),
            'statut': event_dict['statut'],
            'organisateur_id': event_dict.get('organisateur_id'),
            'organisateur_nom': event_dict.get('organisateur_nom'),
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict.get('programme_code'),
                'nom': event_dict.get('programme_nom')
            })() if event_dict['programme_id'] else None,
            'cree_le': event_dict.get('cree_le'),
            'modifie_le': event_dict.get('modifie_le')
        })()
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/detail.html", {
            "request": request,
            "event": event_obj,
            "presences_data": presences_data,
            "stats": stats,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans creer_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de l'événement: {str(e)}")

@router.get("/{event_id}", name="detail_event", response_class=HTMLResponse)
async def detail_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Détail d'un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [detail_event] Schéma configuré: {schema_name}")
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'programme_id': event_dict['programme_id'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'heure_debut': event_dict['heure_debut'],
            'heure_fin': event_dict['heure_fin'],
            'lieu': event_dict['lieu'],
            'statut': event_dict['statut'],
            'organisateur_id': event_dict['organisateur_id'],
            'organisateur_nom': event_dict['organisateur_nom'],
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict['programme_code'],
                'nom': event_dict['programme_nom']
            })() if event_dict['programme_id'] else None,
            'cree_le': event_dict['cree_le'],
            'modifie_le': event_dict['modifie_le']
        })()
        
        presences_data = event_service.get_presences_with_combined_status(event_id, db, schema_name)
        stats = event_service.get_presence_stats_with_invitations(event_id, db, schema_name)
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/detail.html", {
            "request": request,
            "event": event,
            "presences_data": presences_data,
            "stats": stats,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans detail_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.get("/{event_id}/edit", name="edit_event", response_class=HTMLResponse)
async def edit_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire d'édition d'un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'programme_id': event_dict['programme_id'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'heure_debut': event_dict.get('heure_debut'),
            'heure_fin': event_dict.get('heure_fin'),
            'lieu': event_dict.get('lieu'),
            'statut': event_dict['statut']
        })()
        
        # Récupérer le programme correspondant au paramètre programme de l'URL
        programme_param = request.query_params.get('programme', '').upper()
        selected_programme = None
        
        if programme_param:
            # Chercher le programme par son code dans le schéma public (explicite)
            programme_query = text("SELECT * FROM public.programme WHERE code = :code")
            programme_result = db.exec(programme_query.bindparams(code=programme_param)).first()
            if programme_result:
                selected_programme = type('Programme', (), {
                    'id': programme_result.id,
                    'code': programme_result.code,
                    'nom': programme_result.nom
                })()
        
        # Récupérer les programmes
        programmes_query = text("SELECT * FROM public.programme WHERE actif = true ORDER BY code")
        programmes_results = db.exec(programmes_query).all()
        programmes = [type('Programme', (), {
            'id': p.id,
            'code': p.code,
            'nom': p.nom
        })() for p in programmes_results]
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/form.html", {
            "request": request,
            "event": event,
            "programmes": programmes,
            "selected_programme": selected_programme,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name,
            "is_edit": True
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans edit_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du formulaire: {str(e)}")

@router.post("/{event_id}/update", name="update_event")
async def update_event(
    event_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    heure_debut: str = Form(""),
    heure_fin: str = Form(""),
    lieu: str = Form(""),
    programme_id: int = Form(...),
    statut: str = Form("planifie"),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Mettre à jour un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Conversion des heures
        heure_debut_dt = None
        heure_fin_dt = None
        
        if heure_debut:
            try:
                heure_debut_dt = datetime.strptime(f"{date_debut} {heure_debut}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        if heure_fin:
            try:
                heure_fin_dt = datetime.strptime(f"{date_fin} {heure_fin}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        # Préparer les données de mise à jour
        update_data = EventUpdate(
            titre=titre,
            description=description if description else None,
            date_debut=date_debut,
            date_fin=date_fin,
            heure_debut=heure_debut_dt,
            heure_fin=heure_fin_dt,
            lieu=lieu if lieu else None,
            programme_id=programme_id,
            statut=statut
        )
        
        # Mettre à jour l'événement
        updated_event = event_service.update_event(event_id, update_data, db, schema_name)
        
        # Récupérer le paramètre programme pour la redirection
        programme_param = request.query_params.get('programme', '')
        redirect_url = request.url_for("detail_event", event_id=event_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans update_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour: {str(e)}")

# === ROUTES D'ÉMARGEMENT ===

@router.get("/{event_id}/emargement", name="emargement_event", response_class=HTMLResponse)
async def emargement_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement pour un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [emargement_event] Schéma configuré: {schema_name}")
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'programme_id': event_dict['programme_id'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu'],
            'statut': event_dict['statut'],
            'organisateur_nom': event_dict['organisateur_nom'],
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict['programme_code'],
                'nom': event_dict['programme_nom']
            })() if event_dict['programme_id'] else None
        })()
        
        presences = event_service.get_presences_with_invitations(event_id, db, schema_name)
        stats = event_service.get_presence_stats_with_invitations(event_id, db, schema_name)
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/emargement.html", {
            "request": request,
            "event": event,
            "presences": presences,
            "stats": stats,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans emargement_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.get("/{event_id}/emargement-direct", name="emargement_direct_event", response_class=HTMLResponse)
async def emargement_direct_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement direct pour un événement (mode tablette avec authentification)"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [emargement_direct_event] Schéma configuré: {schema_name}")
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'programme_id': event_dict['programme_id'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu'],
            'statut': event_dict['statut'],
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict.get('programme_code'),
                'nom': event_dict.get('programme_nom')
            })() if event_dict['programme_id'] else None
        })()
        
        presences = event_service.get_presences_with_invitations(event_id, db, schema_name)
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/emargement_direct.html", {
            "request": request,
            "event": event,
            "presences": presences,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans emargement_direct_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.get("/{event_id}/invitations", name="invitations_event", response_class=HTMLResponse)
async def invitations_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page de gestion des invitations"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [invitations_event] Schéma configuré: {schema_name}")
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'programme_id': event_dict['programme_id'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu'],
            'statut': event_dict['statut'],
            'organisateur_nom': event_dict['organisateur_nom'],
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict['programme_code'],
                'nom': event_dict['programme_nom']
            })() if event_dict['programme_id'] else None
        })()
        
        invitations = event_service.get_invitations_by_event(event_id, db, schema_name)
        
        # Réinitialiser complètement la transaction après get_invitations_by_event
        try:
            db.rollback()
        except:
            pass
        
        try:
            db.commit()
        except:
            pass
        
        # S'assurer qu'on a une nouvelle transaction propre
        try:
            db.begin()
        except:
            pass
        
        # Configurer le search_path dans une nouvelle transaction
        try:
            db.exec(text(f"SET search_path TO {schema_name}, public"))
        except Exception as e:
            logger.error(f"❌ Erreur lors de la configuration du search_path: {str(e)}")
            # Rollback et réessayer
            try:
                db.rollback()
                db.commit()
                db.begin()
                db.exec(text(f"SET search_path TO {schema_name}, public"))
            except:
                pass
        
        # Récupérer les candidats validés du programme avec requête SQL directe
        candidats_query = text(f"""
            SELECT id, nom, prenom, email, photo_profil, statut
            FROM {schema_name}.candidat
            WHERE statut = 'VALIDE'
            ORDER BY nom, prenom
        """)
        candidats_results = db.exec(candidats_query).all()
        candidats = [type('Candidat', (), {
            'id': c.id,
            'nom': c.nom,
            'prenom': c.prenom,
            'email': c.email,
            'photo_profil': c.photo_profil,
            'statut': c.statut
        })() for c in candidats_results]
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/invitations.html", {
            "request": request,
            "event": event,
            "invitations": invitations,
            "candidats": candidats,
            "inscriptions": candidats,  # Pour compatibilité avec le template
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans invitations_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.post("/{event_id}/invitations/envoyer", name="envoyer_invitations_event")
async def envoyer_invitations_event(
    event_id: int,
    request: Request,
    type_invitation: str = Form(...),
    candidats_ids: List[int] = Form([]),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Envoyer des invitations"""
    from ..models.enums import TypeInvitation
    from ..core.program_schema_integration import get_schema_from_request
    
    try:
        logger.info(f"📧 [envoyer_invitations_event] Début - Event {event_id}, Type: {type_invitation}, Candidats: {len(candidats_ids)}")
        logger.debug(f"   📋 Liste candidats_ids: {candidats_ids}")
        
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if not candidats_ids:
            logger.warning(f"⚠️ Aucun candidat sélectionné pour l'événement {event_id}")
            # Rediriger quand même pour éviter une erreur
            programme_param = request.query_params.get('programme', '')
            redirect_url = request.url_for("invitations_event", event_id=event_id)
            if programme_param:
                redirect_url = f"{redirect_url}?programme={programme_param}"
            return RedirectResponse(url=redirect_url, status_code=303)
        
        type_inv = TypeInvitation(type_invitation)
        logger.info(f"📧 [envoyer_invitations_event] Appel de send_invitations_bulk pour {len(candidats_ids)} candidats")
        invitations = event_service.send_invitations_bulk(event_id, type_inv, candidats_ids, db, schema_name)
        logger.info(f"✅ [envoyer_invitations_event] {len(invitations)} invitations créées et emails envoyés")
        
        programme_param = request.query_params.get('programme', '')
        redirect_url = request.url_for("invitations_event", event_id=event_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        logger.error(f"❌ Erreur dans envoyer_invitations_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi des invitations: {str(e)}")


@router.post("/{event_id}/emargement-direct", name="marquer_presence_event_direct")
async def marquer_presence_event_direct(
    event_id: int,
    request: Request,
    candidat_id: int = Form(...),
    presence: str = Form("present"),
    methode_signature: str = Form("MANUEL"),
    signature_data: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Marquer la présence d'un candidat à un événement (mode tablette avec authentification)"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Vérifier que l'événement existe
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Préparer les données selon la méthode
        signature_manuelle = None
        signature_digitale = None
        
        # Sauvegarder la signature digitale si fournie
        if methode_signature == "digital" and signature_data:
            try:
                # Extraire les données base64 (enlever le préfixe "data:image/png;base64,")
                if "," in signature_data:
                    signature_base64 = signature_data.split(",")[1]
                else:
                    signature_base64 = signature_data
                
                # Décoder le base64
                signature_bytes = base64.b64decode(signature_base64)
                
                # Créer le dossier de sauvegarde des signatures en utilisant path_config
                signatures_dir = path_config.UPLOAD_DIR / "emargements" / "signatures" / schema_name.lower()
                signatures_dir.mkdir(parents=True, exist_ok=True)
                
                # Générer un nom de fichier unique
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                filename = f"signature_event{event_id}_candidat{candidat_id}_{timestamp}.png"
                file_path = signatures_dir / filename
                
                # Sauvegarder l'image
                with open(file_path, "wb") as f:
                    f.write(signature_bytes)
                
                # Générer l'URL relative pour la base de données
                signature_digitale = f"{path_config.get_mount_path('media')}/emargements/signatures/{schema_name.lower()}/{filename}"
            except Exception as e:
                logger.error(f"❌ Erreur lors de la sauvegarde de la signature digitale: {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Erreur lors de la sauvegarde de la signature: {str(e)}")
        elif methode_signature == "MANUEL" or methode_signature == "manuel":
            # Pour la signature manuelle, on utilise directement le texte
            signature_manuelle = signature_data
        
        presence_data = PresenceEventCreate(
            event_id=event_id,
            candidat_id=candidat_id,
            presence=presence,
            methode_signature=MethodeSignatureEvent(methode_signature.upper()) if methode_signature else None,
            signature_manuelle=signature_manuelle,
            signature_digitale=signature_digitale,
            heure_arrivee=datetime.now(timezone.utc),
            commentaire=note if note else None,
            ip_signature=request.client.host if request.client else None
        )
        
        presence_obj = event_service.mark_presence(presence_data, db, schema_name)
        
        # Rediriger vers la page d'émargement direct après validation
        programme_param = request.query_params.get('programme', '')
        redirect_url = request.url_for("emargement_direct_event", event_id=event_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans marquer_presence_event_direct: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors du marquage de présence: {str(e)}")

# === ROUTES D'ÉMARGEMENT PAR LIEN (MODE DISTANCE) ===

@router.get("/{event_id}/emargement/liens", name="generer_liens_emargement_event", response_class=HTMLResponse)
async def generer_liens_emargement_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page de génération des liens d'émargement pour un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict.get('lieu')
        })()
        
        # Récupérer les invitations de l'événement
        invitations = event_service.get_invitations_by_event(event_id, db, schema_name)
        
        return templates.TemplateResponse("pages/events/generer_liens_emargement.html", {
            "request": request,
            "event": event,
            "invitations": invitations,
            "utilisateur": current_user
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans generer_liens_emargement_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.post("/{event_id}/emargement/liens/envoyer", name="envoyer_liens_emargement_event")
async def envoyer_liens_emargement_event(
    event_id: int,
    request: Request,
    invitation_ids: List[int] = Form(...),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Envoyer les liens d'émargement par email pour un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Récupérer les invitations de l'événement
        all_invitations = event_service.get_invitations_by_event(event_id, db, schema_name)
        
        # Filtrer les invitations sélectionnées
        invitations = [inv for inv in all_invitations if inv.get('id') in invitation_ids]
        
        # Envoyer les emails avec les liens d'émargement
        from ..core.config import settings
        base_url = settings.get_base_url_for_email()
        programme_param = request.query_params.get('programme', '')
        
        sent_count = 0
        for invitation in invitations:
            try:
                # Générer le lien d'émargement avec le paramètre programme
                emargement_url = f"{base_url}/events/{event_id}/emargement/lien/{invitation.get('token_invitation')}"
                if programme_param:
                    emargement_url = f"{emargement_url}?programme={programme_param}"
                
                # Préparer l'email
                subject = f"Lien d'émargement - {event_dict['titre']}"
                template_data = {
                    'nom': f"{invitation.get('candidat_prenom', '')} {invitation.get('candidat_nom', '')}",
                    'event_titre': event_dict['titre'],
                    'date_event': event_dict['date_debut'].strftime('%d/%m/%Y') if event_dict.get('date_debut') else '',
                    'lieu': event_dict.get('lieu') or "À définir",
                    'emargement_url': emargement_url,
                    'base_url': base_url
                }
                
                # Envoyer l'email
                event_service.email_service.send_template_email(
                    to_email=invitation.get('candidat_email'),
                    subject=subject,
                    template="event_emargement_lien",
                    data=template_data
                )
                sent_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erreur envoi email émargement événement: {str(e)}", exc_info=True)
        
        # Rediriger vers la page d'émargement
        redirect_url = request.url_for("emargement_event", event_id=event_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans envoyer_liens_emargement_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi: {str(e)}")

@router.get("/invitation/{token}/accepter", name="accepter_invitation_event", response_class=HTMLResponse)
async def accepter_invitation_event(
    request: Request,
    token: str,
    programme: Optional[str] = None,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Accepter une invitation d'événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        if programme:
            schema_name = programme.lower()
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Accepter l'invitation
        invitation = event_service.accept_invitation(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation non trouvée")
        
        # Vérifier que l'invitation n'est pas déjà refusée
        if invitation.get('statut') and str(invitation.get('statut')).upper() == 'REFUSEE':
            raise HTTPException(status_code=400, detail="Cette invitation a été refusée")
        
        # Récupérer l'événement
        event_id = invitation.get('event_id')
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir l'événement en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu'],
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict.get('programme_code'),
                'nom': event_dict.get('programme_nom')
            })() if event_dict.get('programme_id') else None
        })()
        
        # Convertir l'invitation en objet simple pour le template
        invitation_obj = type('InvitationEvent', (), {
            'id': invitation.get('id'),
            'event_id': invitation.get('event_id'),
            'token_invitation': invitation.get('token_invitation'),
            'candidat_id': invitation.get('candidat_id'),
            'statut': invitation.get('statut'),
            'candidat': type('Candidat', (), {
                'id': invitation.get('candidat_id'),
                'nom': invitation.get('candidat_nom', ''),
                'prenom': invitation.get('candidat_prenom', ''),
                'email': invitation.get('candidat_email', '')
            })() if invitation.get('candidat_id') else None
        })()
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/emargement_lien.html", {
            "request": request,
            "event": event,
            "invitation": invitation_obj,
            "presence": None,
            "accepted": True,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans accepter_invitation_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'acceptation: {str(e)}")

@router.get("/invitation/{token}/refuser", name="refuser_invitation_event", response_class=HTMLResponse)
async def refuser_invitation_event(
    request: Request,
    token: str,
    programme: Optional[str] = None,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Refuser une invitation d'événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        if programme:
            schema_name = programme.lower()
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Refuser l'invitation
        invitation = event_service.reject_invitation(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation non trouvée")
        
        # Récupérer l'événement
        event_id = invitation.get('event_id')
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir l'événement en objet simple pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu'],
            'programme': type('Programme', (), {
                'id': event_dict['programme_id'],
                'code': event_dict.get('programme_code'),
                'nom': event_dict.get('programme_nom')
            })() if event_dict.get('programme_id') else None
        })()
        
        # Convertir l'invitation en objet simple pour le template (compatible avec emargement_lien.html)
        invitation_obj = type('InvitationEvent', (), {
            'id': invitation.get('id'),
            'event_id': invitation.get('event_id'),
            'token_invitation': invitation.get('token_invitation'),
            'candidat_id': invitation.get('candidat_id'),
            'statut': invitation.get('statut'),
            'candidat': type('Candidat', (), {
                'id': invitation.get('candidat_id'),
                'nom': invitation.get('candidat_nom', ''),
                'prenom': invitation.get('candidat_prenom', ''),
                'email': invitation.get('candidat_email', '')
            })() if invitation.get('candidat_id') else None
        })()
        
        # Récupérer le paramètre programme pour le template
        programme_param = request.query_params.get('programme', '')
        
        return templates.TemplateResponse("pages/events/emargement_lien.html", {
            "request": request,
            "event": event,
            "invitation": invitation_obj,
            "presence": None,
            "refused": True,
            "programme_param": programme_param,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans refuser_invitation_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors du refus: {str(e)}")

@router.get("/{event_id}/emargement/lien/{token}", name="emargement_lien_event", response_class=HTMLResponse)
async def emargement_lien_event(
    event_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement via lien unique pour un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier le token et récupérer l'invitation
        invitation = event_service.get_invitation_by_token(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
        
        # Vérifier que l'invitation est pour cet événement
        if invitation.get('event_id') != event_id:
            raise HTTPException(status_code=400, detail="Lien d'émargement incorrect")
        
        # Récupérer l'événement
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir l'événement en objet simple
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu']
        })()
        
        # Convertir l'invitation en objet simple
        invitation_obj = type('InvitationEvent', (), {
            'id': invitation.get('id'),
            'event_id': invitation.get('event_id'),
            'token_invitation': invitation.get('token_invitation'),
            'candidat_id': invitation.get('candidat_id'),
            'statut': invitation.get('statut'),
            'candidat': type('Candidat', (), {
                'id': invitation.get('candidat_id'),
                'nom': invitation.get('candidat_nom', ''),
                'prenom': invitation.get('candidat_prenom', ''),
                'email': invitation.get('candidat_email', '')
            })() if invitation.get('candidat_id') else None
        })()
        
        # Vérifier si déjà présent
        presence = event_service.get_presence_candidat(event_id, invitation.get('candidat_id'), db, schema_name)
        
        return templates.TemplateResponse("pages/events/emargement_lien.html", {
            "request": request,
            "event": event,
            "invitation": invitation_obj,
            "presence": presence
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans emargement_lien_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.post("/{event_id}/emargement/lien/{token}", name="signer_emargement_lien_event")
async def signer_emargement_lien_event(
    event_id: int,
    token: str,
    request: Request,
    methode_signature: str = Form("digital"),
    signature_data: str = Form(""),
    nom_signature: str = Form(""),
    photo_data: str = Form(""),
    commentaire: str = Form(""),
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Signer l'émargement via lien pour un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Vérifier le token
        invitation = event_service.get_invitation_by_token(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
        
        # Vérifier que l'invitation est pour cet événement
        if invitation.get('event_id') != event_id:
            raise HTTPException(status_code=400, detail="Lien d'émargement incorrect")
        
        # Créer la présence
        candidat_id = invitation.get('candidat_id')
        if not candidat_id:
            raise HTTPException(status_code=400, detail="Candidat non trouvé dans l'invitation")
        
        # Préparer les données selon la méthode
        signature_manuelle = None
        signature_digitale = None
        photo_signature = None
        
        # Sauvegarder la photo si fournie
        if photo_data:
            try:
                # Extraire les données base64 (enlever le préfixe "data:image/...;base64,")
                if "," in photo_data:
                    photo_base64 = photo_data.split(",")[1]
                else:
                    photo_base64 = photo_data
                
                # Décoder le base64
                photo_bytes = base64.b64decode(photo_base64)
                
                # Créer le dossier de sauvegarde des photos en utilisant path_config
                photos_dir = path_config.UPLOAD_DIR / "emargements" / "photos" / schema_name.lower()
                photos_dir.mkdir(parents=True, exist_ok=True)
                
                # Générer un nom de fichier unique
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                filename = f"photo_event{event_id}_candidat{candidat_id}_{timestamp}.png"
                file_path = photos_dir / filename
                
                # Sauvegarder l'image
                with open(file_path, "wb") as f:
                    f.write(photo_bytes)
                
                # Générer l'URL relative pour la base de données
                photo_signature = f"{path_config.get_mount_path('media')}/emargements/photos/{schema_name.lower()}/{filename}"
            except Exception as e:
                logger.error(f"❌ Erreur lors de la sauvegarde de la photo: {str(e)}", exc_info=True)
                # Continuer sans photo plutôt que d'échouer complètement
                photo_signature = None
        
        # Sauvegarder la signature digitale si fournie
        if methode_signature == "digital" and signature_data:
            try:
                # Extraire les données base64 (enlever le préfixe "data:image/png;base64,")
                if "," in signature_data:
                    signature_base64 = signature_data.split(",")[1]
                else:
                    signature_base64 = signature_data
                
                # Décoder le base64
                signature_bytes = base64.b64decode(signature_base64)
                
                # Créer le dossier de sauvegarde des signatures en utilisant path_config
                signatures_dir = path_config.UPLOAD_DIR / "emargements" / "signatures" / schema_name.lower()
                signatures_dir.mkdir(parents=True, exist_ok=True)
                
                # Générer un nom de fichier unique
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                filename = f"signature_event{event_id}_candidat{candidat_id}_{timestamp}.png"
                file_path = signatures_dir / filename
                
                # Sauvegarder l'image
                with open(file_path, "wb") as f:
                    f.write(signature_bytes)
                
                # Générer l'URL relative pour la base de données
                signature_digitale = f"{path_config.get_mount_path('media')}/emargements/signatures/{schema_name.lower()}/{filename}"
            except Exception as e:
                logger.error(f"❌ Erreur lors de la sauvegarde de la signature: {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Erreur lors de la sauvegarde de la signature: {str(e)}")
        elif methode_signature == "manuel":
            signature_manuelle = nom_signature  # Le nom saisi
        
        presence_data = PresenceEventCreate(
            event_id=event_id,
            candidat_id=candidat_id,
            presence="present",
            heure_arrivee=datetime.now(timezone.utc),
            methode_signature=MethodeSignatureEvent(methode_signature.upper()) if methode_signature else None,
            signature_manuelle=signature_manuelle,
            signature_digitale=signature_digitale,
            photo_signature=photo_signature,
            commentaire=commentaire if commentaire else None,
            ip_signature=request.client.host if request.client else None
        )
        
        presence_obj = event_service.mark_presence(presence_data, db, schema_name)
        
        # Note: L'acceptation de l'invitation se fait via le bouton dans l'email, pas lors de l'émargement
        # L'émargement crée seulement la présence, pas l'acceptation
        
        # Récupérer l'événement pour le template
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convertir en objets simples pour le template
        event = type('Event', (), {
            'id': event_dict['id'],
            'titre': event_dict['titre'],
            'description': event_dict['description'],
            'date_debut': event_dict['date_debut'],
            'date_fin': event_dict['date_fin'],
            'lieu': event_dict['lieu']
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_id,
            'nom': invitation.get('candidat_nom', ''),
            'prenom': invitation.get('candidat_prenom', ''),
            'email': invitation.get('candidat_email', '')
        })()
        
        return templates.TemplateResponse("pages/events/emargement_confirmation.html", {
            "request": request,
            "event": event,
            "presence": presence_obj,
            "candidat": candidat
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans signer_emargement_lien_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la signature: {str(e)}")

# === ROUTES PUBLIQUES (pour les invitations) ===
# Note: Les routes d'acceptation et de refus sont définies plus haut (lignes 941 et 1015)

@router.post("/{event_id}/participant/{candidat_id}/supprimer", name="supprimer_participant_event")
async def supprimer_participant_event(
    event_id: int,
    candidat_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer un participant d'un événement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table event existe dans le schéma
        table_exists = table_exists_anywhere("event", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Événement non trouvé dans ce programme")
        
        # Vérifier que l'événement existe
        event_dict = event_service.get_event(event_id, db, schema_name)
        if not event_dict:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Supprimer le participant
        success = event_service.remove_participant_from_event(event_id, candidat_id, db, schema_name)
        
        if not success:
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression du participant")
        
        # Récupérer le paramètre programme pour la redirection
        programme_param = request.query_params.get('programme', '')
        
        # Rediriger vers la page d'origine (Referer) ou vers la page d'émargement par défaut
        referer = request.headers.get("referer")
        if referer and f"/events/{event_id}" in referer:
            redirect_url = referer
        else:
            redirect_url = request.url_for("emargement_event", event_id=event_id)
        
        if programme_param:
            separator = '&' if '?' in redirect_url else '?'
            redirect_url = f"{redirect_url}{separator}programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans supprimer_participant_event: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")