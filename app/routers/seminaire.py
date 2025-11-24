# app/routers/seminaire.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime, date, timezone
import os
import uuid
import logging
import base64

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.path_config import path_config
from ..core.program_schema_integration import table_exists_anywhere, get_schema_routing_service, SchemaRoutingService, get_schema_from_request
from ..core.config import settings
from ..services.file_upload_service import FileUploadService
from ..models.base import User, Programme, Candidat
from ..models.seminaire import Seminaire, SessionSeminaire, InvitationSeminaire, PresenceSeminaire, LivrableSeminaire, RenduLivrable
from ..models.enums import StatutSeminaire, TypeInvitation, StatutPresence, MethodeSignature
from ..schemas.seminaire_schemas import (
    SeminaireCreate, SeminaireUpdate, SessionSeminaireCreate,
    InvitationSeminaireCreate, PresenceSeminaireCreate, LivrableSeminaireCreate,
    SeminaireFilter, PresenceFilter
)
from ..services.seminaire_service import SeminaireService
from ..templates import templates

router = APIRouter()
seminaire_service = SeminaireService()
logger = logging.getLogger(__name__)

# === ROUTES WEB ===

@router.get("/", name="liste_seminaires", response_class=HTMLResponse)
async def liste_seminaires(
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme_id: Optional[int] = None,
    statut: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """Page de liste des séminaires"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [liste_seminaires] Schéma configuré: {schema_name}")
        
        # Configurer explicitement le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            logger.warning(f"⚠️ Table seminaire n'existe pas dans le schéma {schema_name}")
            return templates.TemplateResponse("pages/seminaires/liste.html", {
                "request": request,
                "seminaires": [],
                "stats": {"total_seminaires": 0, "seminaires_planifies": 0, "seminaires_en_cours": 0, "seminaires_termines": 0},
                "programmes": [],
                "current_user": current_user,
                "utilisateur": current_user,
                "programme_id": programme_id,
                "filters": {}
            })
        
        # Construire la requête SQL directe avec filtres
        try:
            base_query = f"""
                SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                       s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                       s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                       s.organisateur as organisateur_nom, p.nom as programme_nom, p.code as programme_code
                FROM {schema_name}.seminaire s
                LEFT JOIN public.programme p ON s.programme_id = p.id
            """
            
            where_conditions = []
            params = {}
            
            if programme_id:
                where_conditions.append("s.programme_id = :programme_id")
                params['programme_id'] = programme_id
            
            if statut:
                where_conditions.append("LOWER(s.statut) = LOWER(:statut)")
                params['statut'] = statut
            
            if date_from:
                where_conditions.append("s.date_debut >= :date_from")
                params['date_from'] = date_from
            
            if date_to:
                where_conditions.append("s.date_debut <= :date_to")
                params['date_to'] = date_to
            
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            base_query += " ORDER BY s.date_debut DESC"
            
            # Exécuter la requête
            if params:
                query = text(base_query).bindparams(**params)
            else:
                query = text(base_query)
            
            seminaires_results = db.exec(query).all()
            
            # Convertir les résultats en objets simples
            seminaires = []
            for row in seminaires_results:
                statut_str = str(row.statut).lower() if row.statut else 'planifie'
                if hasattr(row.statut, 'value'):
                    statut_str = row.statut.value.lower()
                
                seminaires.append(type('Seminaire', (), {
                    'id': row.id,
                    'titre': row.titre,
                    'description': row.description,
                    'programme_id': row.programme_id,
                    'date_debut': row.date_debut,
                    'date_fin': row.date_fin,
                    'lieu': row.lieu,
                    'adresse_complete': row.adresse_complete,
                    'organisateur': row.organisateur,
                    'capacite_max': row.capacite_max,
                    'statut': statut_str,
                    'actif': row.actif,
                    'invitation_auto': row.invitation_auto,
                    'invitation_promos': row.invitation_promos,
                    'cree_le': row.cree_le,
                    'modifie_le': row.modifie_le,
                    'organisateur_nom': row.organisateur_nom,
                    'programme': type('Programme', (), {
                        'nom': row.programme_nom,
                        'code': row.programme_code or row.programme_nom
                    })()
                })())
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la récupération des séminaires: {e}")
            seminaires = []
        
        # Calculer les statistiques via requête SQL directe
        try:
            stats_query = text(f"""
                SELECT 
                    COUNT(*) as total_seminaires,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'planifie') as seminaires_planifies,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'en_cours') as seminaires_en_cours,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'termine') as seminaires_termines
                FROM {schema_name}.seminaire
            """)
            stats_result = db.exec(stats_query).first()
            
            stats = {
                'total_seminaires': stats_result.total_seminaires or 0,
                'seminaires_planifies': stats_result.seminaires_planifies or 0,
                'seminaires_en_cours': stats_result.seminaires_en_cours or 0,
                'seminaires_termines': stats_result.seminaires_termines or 0,
                'total_participants': 0,
                'taux_presence_moyen': 0
            }
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la récupération des statistiques séminaires: {e}")
            stats = {"total_seminaires": 0, "seminaires_planifies": 0, "seminaires_en_cours": 0, "seminaires_termines": 0}
        
        try:
            # Programme est dans le schéma public, pas besoin de get_model_for_schema
            programmes = db.exec(select(Programme).where(Programme.actif == True)).all()
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la récupération des programmes: {e}")
            programmes = []
        
        return templates.TemplateResponse("pages/seminaires/liste.html", {
            "request": request,
            "seminaires": seminaires,
            "stats": stats,
            "programmes": programmes,
            "current_user": current_user,
            "utilisateur": current_user,
            "programme_id": programme_id,
            "filters": {
                "statut": statut or "",
                "date_from": date_from or "",
                "date_to": date_to or ""
            }
        })
    except Exception as e:
        logger.error(f"❌ Erreur dans liste_seminaires: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.get("/nouveau", name="form_seminaire", response_class=HTMLResponse)
async def nouveau_seminaire_form(
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'un nouveau séminaire"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [nouveau_seminaire_form] Schéma configuré: {schema_name}")
        
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
        
        return templates.TemplateResponse("pages/seminaires/nouveau.html", {
            "request": request,
            "programmes": programmes,
            "selected_programme": selected_programme,
            "users": users,
            "current_user": current_user,
            "utilisateur": current_user
        })
    except Exception as e:
        logger.error(f"❌ Erreur dans nouveau_seminaire_form: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du formulaire: {str(e)}")

@router.post("/nouveau",name="creer_seminaire")
async def creer_seminaire(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    programme_id: int = Form(...),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    lieu: str = Form(""),
    adresse_complete: str = Form(""),
    capacite_max: int = Form(None),
    organisateur: str = Form(...),
    invitation_auto: bool = Form(False),
    invitation_promos: bool = Form(False),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Créer un nouveau séminaire"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        logger.info(f"🔍 [creer_seminaire] Schéma configuré: {schema_name}")
        logger.info(f"🔍 [creer_seminaire] programme_id reçu: {programme_id}")
        logger.info(f"🔍 [creer_seminaire] organisateur reçu: {organisateur}")
        
        # Vérifier que le programme existe et correspond au schéma
        programme_query = text("SELECT id, code FROM public.programme WHERE id = :programme_id AND actif = true")
        programme_result = db.exec(programme_query.bindparams(programme_id=programme_id)).first()
        if not programme_result:
            logger.warning(f"⚠️ [creer_seminaire] Programme {programme_id} non trouvé ou inactif")
            raise HTTPException(status_code=400, detail=f"Programme invalide: {programme_id}")
        
        logger.info(f"🔍 [creer_seminaire] Programme trouvé: {programme_result.code} (id: {programme_result.id})")
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaires non disponibles dans ce programme")
        
        # Créer le schéma Pydantic pour la validation
        seminaire_data = SeminaireCreate(
            titre=titre,
            description=description or None,
            programme_id=programme_id,
            date_debut=date_debut,
            date_fin=date_fin,
            lieu=lieu or None,
            adresse_complete=adresse_complete or None,
            organisateur=organisateur.strip(),
            capacite_max=capacite_max,
            invitation_auto=invitation_auto,
            invitation_promos=invitation_promos
        )
        
        # Utiliser le service pour créer le séminaire avec le schéma explicite
        seminaire_result = seminaire_service.create_seminaire(seminaire_data, db, schema_name)
        if not seminaire_result:
            raise HTTPException(status_code=500, detail="Erreur lors de la création du séminaire")
        
        # Construire l'URL de redirection avec le paramètre programme
        programme_param = schema_name.upper() if schema_name and schema_name != 'public' else ''
        redirect_url = request.url_for("detail_seminaire", seminaire_id=seminaire_result["id"])
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans creer_seminaire: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du séminaire: {str(e)}")

@router.get("/{seminaire_id}/modifier", name="modifier_seminaire_form", response_class=HTMLResponse)
async def modifier_seminaire_form(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de modification d'un séminaire"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [modifier_seminaire_form] Schéma configuré: {schema_name}")
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Utiliser le service pour récupérer le séminaire avec le schéma explicite
        seminaire_data = seminaire_service.get_seminaire(seminaire_id, db, schema_name)
        if not seminaire_data:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Récupérer les informations du programme
        programme = db.get(Programme, seminaire_data["programme_id"])
        
        # Récupérer le programme correspondant au paramètre programme de l'URL (pour vérification)
        programme_param = request.query_params.get('programme', '').upper()
        selected_programme = programme  # Par défaut, utiliser le programme du séminaire
        
        if programme_param:
            # Chercher le programme par son code dans le schéma public (explicite)
            programme_query = text("SELECT * FROM public.programme WHERE code = :code")
            programme_result = db.exec(programme_query.bindparams(code=programme_param)).first()
            if programme_result and programme_result.id == seminaire_data["programme_id"]:
                selected_programme = type('Programme', (), {
                    'id': programme_result.id,
                    'code': programme_result.code,
                    'nom': programme_result.nom
                })()
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_data["statut"]:
            if hasattr(seminaire_data["statut"], 'value'):
                statut_str = seminaire_data["statut"].value.lower()
            else:
                statut_str = str(seminaire_data["statut"]).lower()
        
        # Créer un objet simple pour le template
        seminaire_obj = type('Seminaire', (), {
            'id': seminaire_data["id"],
            'titre': seminaire_data["titre"],
            'description': seminaire_data["description"],
            'programme_id': seminaire_data["programme_id"],
            'date_debut': seminaire_data["date_debut"],
            'date_fin': seminaire_data["date_fin"],
            'lieu': seminaire_data["lieu"],
            'adresse_complete': seminaire_data["adresse_complete"],
            'organisateur': seminaire_data["organisateur"],
            'capacite_max': seminaire_data["capacite_max"],
            'statut': statut_str,
            'actif': seminaire_data["actif"],
            'invitation_auto': seminaire_data["invitation_auto"],
            'invitation_promos': seminaire_data["invitation_promos"],
            'cree_le': seminaire_data["cree_le"],
            'modifie_le': seminaire_data["modifie_le"],
            'programme_code': programme.code if programme else None,
            'programme_nom': programme.nom if programme else None,
            'organisateur_nom': seminaire_data["organisateur"]
        })()
        
        # Récupérer tous les programmes du schéma public (explicite)
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
        
        return templates.TemplateResponse("pages/seminaires/nouveau.html", {
            "request": request,
            "programmes": programmes,
            "seminaire": seminaire_obj,
            "selected_programme": selected_programme,
            "users": users,
            "is_edit": True,
            "current_user": current_user,
            "utilisateur": current_user
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans modifier_seminaire_form: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du formulaire: {str(e)}")

@router.post("/{seminaire_id}/modifier", name="modifier_seminaire")
async def modifier_seminaire(
    seminaire_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    programme_id: int = Form(...),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    lieu: str = Form(""),
    adresse_complete: str = Form(""),
    capacite_max: int = Form(None),
    organisateur: str = Form(...),
    invitation_auto: bool = Form(False),
    invitation_promos: bool = Form(False),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Modifier un séminaire existant"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Configurer explicitement le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        logger.info(f"🔍 [modifier_seminaire] Schéma configuré: {schema_name}")
        logger.info(f"🔍 [modifier_seminaire] programme_id reçu: {programme_id}")
        logger.info(f"🔍 [modifier_seminaire] organisateur reçu: {organisateur}")
        
        # Vérifier que le programme existe et correspond au schéma
        programme_query = text("SELECT id, code FROM public.programme WHERE id = :programme_id AND actif = true")
        programme_result = db.exec(programme_query.bindparams(programme_id=programme_id)).first()
        if not programme_result:
            logger.warning(f"⚠️ [modifier_seminaire] Programme {programme_id} non trouvé ou inactif")
            raise HTTPException(status_code=400, detail=f"Programme invalide: {programme_id}")
        
        logger.info(f"🔍 [modifier_seminaire] Programme trouvé: {programme_result.code} (id: {programme_result.id})")
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaires non disponibles dans ce programme")
        
        # Créer le schéma Pydantic pour la validation
        seminaire_update_data = SeminaireUpdate(
            titre=titre,
            description=description or None,
            programme_id=programme_id,
            date_debut=date_debut,
            date_fin=date_fin,
            lieu=lieu or None,
            adresse_complete=adresse_complete or None,
            organisateur=organisateur.strip(),
            capacite_max=capacite_max,
            invitation_auto=invitation_auto,
            invitation_promos=invitation_promos
        )
        
        # Utiliser le service pour mettre à jour le séminaire avec le schéma explicite
        seminaire = seminaire_service.update_seminaire(seminaire_id, seminaire_update_data, db, schema_name)
        
        if not seminaire:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Construire l'URL de redirection avec le paramètre programme
        programme_param = schema_name.upper() if schema_name and schema_name != 'public' else ''
        redirect_url = request.url_for("detail_seminaire", seminaire_id=seminaire_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans modifier_seminaire: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la modification du séminaire: {str(e)}")

@router.post("/{seminaire_id}/supprimer", name="supprimer_seminaire")
async def supprimer_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer un séminaire et toutes ses données associées"""
    try:
        logger.info(f"🔍 [supprimer_seminaire] Début - seminaire_id={seminaire_id}")
        
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        logger.info(f"🔍 [supprimer_seminaire] Schéma détecté: {schema_name}")
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        logger.info(f"🔍 [supprimer_seminaire] Vérification de l'existence de la table seminaire dans {schema_name}")
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            logger.warning(f"⚠️ [supprimer_seminaire] Table seminaire n'existe pas dans {schema_name}")
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Vérifier que le séminaire existe via requête SQL directe
        logger.info(f"🔍 [supprimer_seminaire] Vérification de l'existence du séminaire {seminaire_id}")
        seminaire_query = text(f"SELECT id FROM {schema_name}.seminaire WHERE id = :seminaire_id")
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            logger.warning(f"⚠️ [supprimer_seminaire] Séminaire {seminaire_id} non trouvé")
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        logger.info(f"🔍 [supprimer_seminaire] Séminaire trouvé - id={seminaire_result.id if hasattr(seminaire_result, 'id') else seminaire_result[0]}")
        
        # Supprimer le séminaire (cascade supprimera les sessions, invitations, présences, etc.)
        logger.info(f"🔍 [supprimer_seminaire] Appel de seminaire_service.delete_seminaire({seminaire_id}, db, {schema_name})")
        success = seminaire_service.delete_seminaire(seminaire_id, db, schema_name)
        logger.info(f"🔍 [supprimer_seminaire] Résultat de delete_seminaire: {success}")
        
        if not success:
            logger.error(f"❌ [supprimer_seminaire] delete_seminaire a retourné False")
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression du séminaire")
        
        logger.info(f"✅ [supprimer_seminaire] Suppression réussie pour seminaire_id={seminaire_id}")
        return {"message": "Séminaire supprimé avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans supprimer_seminaire: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@router.get("/{seminaire_id}",name="detail_seminaire", response_class=HTMLResponse)
async def detail_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page de détail d'un séminaire"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [detail_seminaire] Schéma configuré: {schema_name}")
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   s.organisateur as organisateur_nom, p.nom as programme_nom, p.code as programme_code
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme_code': seminaire_result.programme_code,
            'programme_nom': seminaire_result.programme_nom,
            'organisateur_nom': seminaire_result.organisateur_nom,
            'programme': type('Programme', (), {
                'nom': seminaire_result.programme_nom,
                'code': seminaire_result.programme_code or seminaire_result.programme_nom
            })()
        })()
        
        # Récupérer les sessions via requête SQL directe
        sessions_query = text(f"""
            SELECT id, seminaire_id, titre, description, type_session, date_session,
                   heure_debut, heure_fin, lieu, visioconf_url, capacite, obligatoire, cree_le
            FROM {schema_name}.session_seminaire
            WHERE seminaire_id = :seminaire_id
            ORDER BY date_session, heure_debut
        """)
        sessions_results = db.exec(sessions_query.bindparams(seminaire_id=seminaire_id)).all()
        
        # Convertir les sessions en objets simples
        sessions = []
        for session_row in sessions_results:
            type_session_str = None
            if session_row.type_session:
                if hasattr(session_row.type_session, 'value'):
                    type_session_str = session_row.type_session.value.lower()
                else:
                    type_session_str = str(session_row.type_session).lower()
            
            sessions.append(type('SessionSeminaire', (), {
                'id': session_row.id,
                'seminaire_id': session_row.seminaire_id,
                'titre': session_row.titre,
                'description': session_row.description,
                'type_session': type_session_str,
                'date_session': session_row.date_session,
                'heure_debut': session_row.heure_debut,
                'heure_fin': session_row.heure_fin,
                'lieu': session_row.lieu,
                'visioconf_url': session_row.visioconf_url,
                'capacite': session_row.capacite,
                'obligatoire': session_row.obligatoire,
                'cree_le': session_row.cree_le
            })())
        
        # Récupérer les invitations via requête SQL directe
        invitations_query = text(f"""
            SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                   i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                   c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email
            FROM {schema_name}.invitation_seminaire i
            LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
            WHERE i.seminaire_id = :seminaire_id
            ORDER BY i.cree_le DESC
        """)
        invitations_results = db.exec(invitations_query.bindparams(seminaire_id=seminaire_id)).all()
        
        # Convertir les invitations en objets simples
        invitations = []
        seen_candidates = {}
        for inv_row in invitations_results:
            # Éviter les doublons par candidat (garder la plus récente)
            if inv_row.candidat_id:
                if inv_row.candidat_id in seen_candidates:
                    continue
                seen_candidates[inv_row.candidat_id] = True
            
            statut_str = str(inv_row.statut).lower() if inv_row.statut else 'envoyee'
            type_inv_str = None
            if inv_row.type_invitation:
                if hasattr(inv_row.type_invitation, 'value'):
                    type_inv_str = inv_row.type_invitation.value.lower()
                else:
                    type_inv_str = str(inv_row.type_invitation).lower()
            
            invitations.append(type('InvitationSeminaire', (), {
                'id': inv_row.id,
                'seminaire_id': inv_row.seminaire_id,
                'type_invitation': type_inv_str,
                'candidat_id': inv_row.candidat_id,
                'promotion_id': inv_row.promotion_id,
                'statut': statut_str,
                'email_envoye': inv_row.email_envoye,
                'date_envoi': inv_row.date_envoi,
                'date_reponse': inv_row.date_reponse,
                'token_invitation': inv_row.token_invitation,
                'cree_le': inv_row.cree_le,
                'candidat': type('Candidat', (), {
                    'nom': inv_row.candidat_nom,
                    'prenom': inv_row.candidat_prenom,
                    'email': inv_row.candidat_email
                })() if inv_row.candidat_id else None
            })())
        
        # Récupérer les livrables via requête SQL directe
        # Note: La table peut ne pas avoir toutes les colonnes du modèle (selon le script SQL)
        # Utiliser une requête avec seulement les colonnes de base qui existent
        livrables_query = text(f"""
            SELECT id, seminaire_id, titre, description, type_livrable, date_limite, cree_le
            FROM {schema_name}.livrable_seminaire
            WHERE seminaire_id = :seminaire_id
            ORDER BY date_limite, cree_le
        """)
        livrables_results = db.exec(livrables_query.bindparams(seminaire_id=seminaire_id)).all()
        
        # Convertir les livrables en objets simples
        livrables = []
        for liv_row in livrables_results:
            livrables.append(type('LivrableSeminaire', (), {
                'id': liv_row.id,
                'seminaire_id': liv_row.seminaire_id,
                'titre': liv_row.titre,
                'description': liv_row.description,
                'type_livrable': liv_row.type_livrable,
                'date_limite': liv_row.date_limite,
                'format_accepte': None,  # Colonne peut ne pas exister dans la table
                'taille_max_mb': None,  # Colonne peut ne pas exister dans la table
                'obligatoire': True,  # Valeur par défaut
                'consignes': None,  # Colonne peut ne pas exister dans la table
                'cree_le': liv_row.cree_le
            })())
        
        # Récupérer toutes les présences (personnes ayant signé) pour toutes les sessions
        presences = seminaire_service.get_presences_seminaire(seminaire_id, db, schema_name)
        
        # Grouper les présences par session
        presences_par_session = {}
        for presence in presences:
            session_id = presence['session_id']
            if session_id not in presences_par_session:
                presences_par_session[session_id] = {
                    'session_titre': presence['session_titre'],
                    'session_date': presence['session_date'],
                    'session_heure_debut': presence['session_heure_debut'],
                    'presences': []
                }
            presences_par_session[session_id]['presences'].append(presence)
        
        return templates.TemplateResponse("pages/seminaires/detail.html", {
            "request": request,
            "seminaire": seminaire,
            "sessions": sessions,
            "invitations": invitations,
            "livrables": livrables,
            "presences_par_session": presences_par_session,
            "current_user": current_user,
            "utilisateur": current_user
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans detail_seminaire: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du séminaire: {str(e)}")

@router.get("/{seminaire_id}/sessions/nouvelle",name="nouvelle_session_seminaire", response_class=HTMLResponse)
async def nouvelle_session_form(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'une nouvelle session"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom, s.organisateur as organisateur_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })(),
            'organisateur_nom': seminaire_result.organisateur_nom
        })()
        
        return templates.TemplateResponse("pages/seminaires/session_nouvelle.html", {
            "request": request,
            "seminaire": seminaire,
            "current_user": current_user,
            "utilisateur": current_user
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans nouvelle_session_form: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage du formulaire: {str(e)}")

@router.post("/{seminaire_id}/sessions/nouvelle",name="creer_session_seminaire")
async def creer_session(
    seminaire_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    date_session: date = Form(...),
    heure_debut: str = Form(...),  # Changé de datetime à str
    heure_fin: str = Form(None),  # Changé de datetime à str
    lieu: str = Form(""),
    visioconf_url: str = Form(""),
    capacite: int = Form(None),
    obligatoire: bool = Form(True),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Créer une nouvelle session"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Combiner la date et l'heure pour créer des datetime
        from datetime import datetime, time
        
        # Parser les heures
        heure_debut_time = datetime.strptime(heure_debut, "%H:%M").time()
        heure_fin_time = datetime.strptime(heure_fin, "%H:%M").time() if heure_fin else None
        
        # Créer les datetime complets
        datetime_debut = datetime.combine(date_session, heure_debut_time)
        datetime_fin = datetime.combine(date_session, heure_fin_time) if heure_fin_time else None
        
        session_data = SessionSeminaireCreate(
            seminaire_id=seminaire_id,
            titre=titre,
            description=description,
            date_session=date_session,
            heure_debut=datetime_debut,  # Utiliser le datetime combiné
            heure_fin=datetime_fin,      # Utiliser le datetime combiné
            lieu=lieu,
            visioconf_url=visioconf_url,
            capacite=capacite,
            obligatoire=obligatoire
        )
        
        session = seminaire_service.create_session(session_data, db)
        
        # Construire l'URL de redirection avec le paramètre programme
        programme_param = schema_name.upper() if schema_name and schema_name != 'public' else ''
        redirect_url = request.url_for("detail_seminaire", seminaire_id=seminaire_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans creer_session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la session: {str(e)}")

@router.get("/{seminaire_id}/invitations",name="invitations_seminaire", response_class=HTMLResponse)
async def invitations_seminaire(
    seminaire_id: int,
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
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom, s.organisateur as organisateur_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })(),
            'organisateur_nom': seminaire_result.organisateur_nom
        })()
        
        invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db, schema_name)
        
        # Récupérer les candidats disponibles pour invitation via requête SQL directe
        from ..models.enums import DecisionJury
        
        candidats_query = text(f"""
            SELECT id, nom, prenom, email, statut, photo_profil
            FROM {schema_name}.candidat
            WHERE statut = :statut
            ORDER BY nom, prenom
        """)
        candidats_results = db.exec(candidats_query.bindparams(statut=DecisionJury.VALIDE.value)).all()
        
        # Convertir les résultats en objets simples
        candidats = []
        for result in candidats_results:
            candidats.append(type('Candidat', (), {
                'id': result.id,
                'nom': result.nom,
                'prenom': result.prenom,
                'email': result.email,
                'statut': result.statut,
                'photo_profil': result.photo_profil if hasattr(result, 'photo_profil') else None
            })())
        
        return templates.TemplateResponse("pages/seminaires/invitations.html", {
            "request": request,
            "seminaire": seminaire,
            "invitations": invitations,
            "inscriptions": candidats,  # NOTE: Utiliser candidats au lieu d'inscriptions
            "current_user": current_user,
            "utilisateur": current_user
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans invitations_seminaire: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage des invitations: {str(e)}")

@router.post("/{seminaire_id}/invitations/envoyer",name="envoyer_invitations_seminaire")
async def envoyer_invitations(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Envoyer des invitations"""
    try:
        # Récupérer les données du formulaire manuellement
        # D'abord, lire le body brut pour voir ce qui est réellement envoyé
        # NOTE: request.body() ne peut être lu qu'une fois, donc on le lit avant request.form()
        try:
            body = await request.body()
            logger.info(f"📋 Body brut de la requête (premiers 500 chars): {body[:500]}")
            logger.info(f"📋 Body brut longueur: {len(body)} bytes")
            if body:
                logger.info(f"📋 Body brut décodé: {body.decode('utf-8', errors='ignore')[:500]}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la lecture du body: {e}")
        
        # Si le body est vide, essayer de récupérer depuis request._form
        form_data = await request.form()
        logger.info(f"📋 Content-Type de la requête: {request.headers.get('content-type', '')}")
        logger.info(f"📋 Toutes les données du formulaire: {dict(form_data)}")
        logger.info(f"📋 Keys dans form_data: {list(form_data.keys())}")
        logger.info(f"📋 Type de form_data: {type(form_data)}")
        
        # Récupérer type_invitation et candidats_ids depuis le formulaire
        type_invitation = form_data.get('type_invitation', 'individuelle')
        
        # Récupérer candidats_ids - FastAPI peut les parser comme une liste ou comme des valeurs multiples
        candidats_ids = []
        try:
            # Essayer getlist() qui fonctionne pour les valeurs multiples
            candidats_from_form = form_data.getlist('candidats_ids')
            logger.info(f"📋 getlist('candidats_ids'): {candidats_from_form}")
            if candidats_from_form:
                candidats_ids = [int(cid) for cid in candidats_from_form if cid and str(cid).isdigit()]
        except Exception as e:
            logger.error(f"❌ Erreur avec getlist: {e}")
            # Fallback: essayer get() qui peut retourner une valeur unique ou une liste
            try:
                candidats_single = form_data.get('candidats_ids')
                logger.info(f"📋 get('candidats_ids'): {candidats_single}, type: {type(candidats_single)}")
                if candidats_single:
                    if isinstance(candidats_single, list):
                        candidats_ids = [int(cid) for cid in candidats_single if cid and str(cid).isdigit()]
                    else:
                        candidats_ids = [int(candidats_single)]
            except Exception as e2:
                logger.error(f"❌ Erreur avec get: {e2}")
        
        logger.info(f"📋 Candidats IDs finaux: {candidats_ids}")
        
        # Vérifier si des candidats ont été sélectionnés
        if not candidats_ids or len(candidats_ids) == 0:
            raise HTTPException(status_code=400, detail="Veuillez sélectionner au moins un candidat")
        
        # Récupérer le schéma depuis les query params ou le formulaire
        schema_name = request.query_params.get('programme') or form_data.get('programme') or 'acd'
        if schema_name:
            schema_name = schema_name.lower()
        else:
            schema_name = 'acd'
        
        logger.info(f"🔍 Schéma détecté pour l'envoi d'invitations: {schema_name}")
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        type_inv = TypeInvitation(type_invitation)
        invitations = seminaire_service.send_invitations_bulk(seminaire_id, type_inv, candidats_ids, db, schema_name)
        
        # Construire l'URL de redirection avec le paramètre programme
        redirect_url = request.url_for("invitations_seminaire", seminaire_id=seminaire_id)
        if schema_name and schema_name != 'public':
            redirect_url = f"{redirect_url}?programme={schema_name.upper()}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans envoyer_invitations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi des invitations: {str(e)}")

@router.get("/{seminaire_id}/sessions/{session_id}/emargement/liens", name="generer_liens_emargement", response_class=HTMLResponse)
async def generer_liens_emargement(
    request: Request,
    seminaire_id: int,
    session_id: int,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page de génération des liens d'émargement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom, s.organisateur as organisateur_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })(),
            'organisateur_nom': seminaire_result.organisateur_nom
        })()
        
        session = seminaire_service.get_session(session_id, db)
        if not session:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        # Récupérer les invitations du séminaire
        invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db, schema_name)
        
        return templates.TemplateResponse("pages/seminaires/generer_liens_emargement.html", {
            "request": request,
            "seminaire": seminaire,
            "session": session,
            "invitations": invitations
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans generer_liens_emargement: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.post("/{seminaire_id}/sessions/{session_id}/emargement/liens/envoyer", name="envoyer_liens_emargement")
async def envoyer_liens_emargement(
    seminaire_id: int,
    session_id: int,
    request: Request,
    invitation_ids: List[int] = Form(...),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Envoyer les liens d'émargement par email"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer les invitations sélectionnées
        invitations = []
        for invitation_id in invitation_ids:
            invitation = seminaire_service.get_invitation(invitation_id, db)
            if invitation:
                invitations.append(invitation)
        
        # Envoyer les emails avec les liens d'émargement
        sent_count = 0
        for invitation in invitations:
            try:
                # Générer le lien d'émargement
                from ..core.config import settings
                base_url = settings.get_base_url_for_email()
                emargement_url = f"{base_url}/seminaires/{seminaire_id}/sessions/{session_id}/emargement/lien/{invitation.token_invitation}"
                
                # Préparer l'email
                subject = f"Lien d'émargement - {invitation.seminaire.titre}"
                template_data = {
                    'nom': f"{invitation.inscription.candidat.prenom} {invitation.inscription.candidat.nom}",
                    'seminaire_titre': invitation.seminaire.titre,
                    'session_titre': invitation.seminaire.sessions[0].titre if invitation.seminaire.sessions else "Session",
                    'date_session': invitation.seminaire.sessions[0].date_session.strftime('%d/%m/%Y') if invitation.seminaire.sessions else "",
                    'emargement_url': emargement_url,
                    'base_url': base_url
                }
                
                # Envoyer l'email
                seminaire_service.email_service.send_template_email(
                    to_email=invitation.inscription.candidat.email,
                    subject=subject,
                    template="emargement_lien",
                    data=template_data
                )
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Erreur envoi email émargement: {e}")
        
        return RedirectResponse(url=request.url_for("emargement_seminaire", seminaire_id=seminaire_id, session_id=session_id), status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans envoyer_liens_emargement: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi des liens: {str(e)}")

@router.get("/invitation/{token}/accepter", name="accepter_invitation_seminaire", response_class=HTMLResponse)
async def accepter_invitation(
    request: Request,
    token: str,
    programme: Optional[str] = None,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Accepter une invitation et rediriger vers la page d'émargement"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        if programme:
            schema_name = programme.lower()
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Accepter l'invitation (mettre à jour le statut à "ACCEPTEE")
        # L'acceptation se fait via le bouton dans l'email, pas lors de l'émargement
        invitation = seminaire_service.accept_invitation(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation non trouvée")
        
        # Vérifier que l'invitation n'est pas déjà refusée
        if invitation.get('statut') and str(invitation.get('statut')).upper() == 'REFUSEE':
            raise HTTPException(status_code=400, detail="Cette invitation a été refusée")
        
        # Après acceptation, rediriger vers une page de confirmation
        # (pas vers l'émargement car l'acceptation ≠ présence)
        seminaire_id = invitation.get('seminaire_id')
        seminaire_dict = seminaire_service.get_seminaire(seminaire_id, db, schema_name)
        
        # Convertir le séminaire en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_dict.get('id'),
            'titre': seminaire_dict.get('titre'),
            'description': seminaire_dict.get('description'),
            'date_debut': seminaire_dict.get('date_debut'),
            'date_fin': seminaire_dict.get('date_fin'),
            'lieu': seminaire_dict.get('lieu')
        })()
        
        # Convertir l'invitation en objet simple pour le template
        invitation_obj = type('InvitationSeminaire', (), {
            'id': invitation.get('id'),
            'seminaire_id': invitation.get('seminaire_id'),
            'token_invitation': invitation.get('token_invitation'),
            'candidat_id': invitation.get('candidat_id'),
            'statut': invitation.get('statut'),
            'inscription': type('Inscription', (), {
                'id': invitation.get('candidat_id'),
                'candidat': type('Candidat', (), {
                    'id': invitation.get('candidat_id'),
                    'nom': invitation.get('candidat_nom', ''),
                    'prenom': invitation.get('candidat_prenom', ''),
                    'email': invitation.get('candidat_email', '')
                })()
            })() if invitation.get('candidat_id') else None
        })()
        
        return templates.TemplateResponse("pages/seminaires/emargement_lien.html", {
            "request": request,
            "seminaire": seminaire,
            "session": None,
            "invitation": invitation_obj,
            "presence": None,
            "accepted": True
        })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans accepter_invitation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'acceptation: {str(e)}")

@router.get("/invitation/{token}/refuser", name="refuser_invitation_seminaire", response_class=HTMLResponse)
async def refuser_invitation(
    request: Request,
    token: str,
    programme: Optional[str] = None,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Refuser une invitation et afficher une confirmation"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        if programme:
            schema_name = programme.lower()
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Refuser l'invitation
        invitation = seminaire_service.reject_invitation(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation non trouvée")
        
        # Récupérer le séminaire pour afficher les informations
        seminaire_id = invitation.get('seminaire_id')
        seminaire_dict = seminaire_service.get_seminaire(seminaire_id, db, schema_name)
        
        # Convertir le séminaire en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_dict.get('id'),
            'titre': seminaire_dict.get('titre'),
            'description': seminaire_dict.get('description'),
            'date_debut': seminaire_dict.get('date_debut'),
            'date_fin': seminaire_dict.get('date_fin'),
            'lieu': seminaire_dict.get('lieu')
        })()
        
        # Convertir l'invitation en objet simple pour le template (compatible avec emargement_lien.html)
        invitation_obj = type('InvitationSeminaire', (), {
            'id': invitation.get('id'),
            'seminaire_id': invitation.get('seminaire_id'),
            'token_invitation': invitation.get('token_invitation'),
            'candidat_id': invitation.get('candidat_id'),
            'statut': invitation.get('statut'),
            'inscription': type('Inscription', (), {
                'id': invitation.get('candidat_id'),
                'candidat': type('Candidat', (), {
                    'id': invitation.get('candidat_id'),
                    'nom': invitation.get('candidat_nom', ''),
                    'prenom': invitation.get('candidat_prenom', ''),
                    'email': invitation.get('candidat_email', '')
                })()
            })() if invitation.get('candidat_id') else None
        })()
        
        return templates.TemplateResponse("pages/seminaires/emargement_lien.html", {
            "request": request,
            "seminaire": seminaire,
            "session": None,
            "invitation": invitation_obj,
            "presence": None,
            "refused": True
        })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans refuser_invitation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors du refus: {str(e)}")

@router.get("/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}", name="emargement_lien", response_class=HTMLResponse)
async def emargement_lien(
    request: Request,
    seminaire_id: int,
    session_id: int,
    token: str,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement via lien unique"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Vérifier le token et récupérer l'invitation
        invitation = seminaire_service.get_invitation_by_token(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
        
        # Vérifier que l'invitation est pour ce séminaire
        if invitation.get('seminaire_id') != seminaire_id:
            raise HTTPException(status_code=400, detail="Lien d'émargement incorrect")
        
        # Récupérer le séminaire
        seminaire_dict = seminaire_service.get_seminaire(seminaire_id, db, schema_name)
        if not seminaire_dict:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Récupérer la session
        session_dict = seminaire_service.get_session(session_id, db, schema_name)
        if not session_dict:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        # Vérifier si déjà présent
        candidat_id = invitation.get('candidat_id')
        if candidat_id:
            presence = seminaire_service.get_presence_candidat(session_id, candidat_id, db)
        else:
            presence = None
        
        # Convertir le séminaire en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_dict.get('id'),
            'titre': seminaire_dict.get('titre'),
            'description': seminaire_dict.get('description'),
            'date_debut': seminaire_dict.get('date_debut'),
            'date_fin': seminaire_dict.get('date_fin'),
            'lieu': seminaire_dict.get('lieu')
        })()
        
        # Convertir la session en objet simple pour le template
        session = type('SessionSeminaire', (), {
            'id': session_dict.get('id'),
            'titre': session_dict.get('titre'),
            'date_session': session_dict.get('date_session'),
            'heure_debut': session_dict.get('heure_debut'),
            'heure_fin': session_dict.get('heure_fin')
        })()
        
        # Convertir l'invitation en objet simple pour le template (compatible avec emargement_lien.html)
        invitation_obj = type('InvitationSeminaire', (), {
            'id': invitation.get('id'),
            'seminaire_id': invitation.get('seminaire_id'),
            'token_invitation': invitation.get('token_invitation'),
            'candidat_id': invitation.get('candidat_id'),
            'inscription': type('Inscription', (), {
                'id': invitation.get('candidat_id'),
                'candidat': type('Candidat', (), {
                    'id': invitation.get('candidat_id'),
                    'nom': invitation.get('candidat_nom', ''),
                    'prenom': invitation.get('candidat_prenom', ''),
                    'email': invitation.get('candidat_email', '')
                })()
            })() if invitation.get('candidat_id') else None
        })()
        
        return templates.TemplateResponse("pages/seminaires/emargement_lien.html", {
            "request": request,
            "seminaire": seminaire,
            "session": session,
            "invitation": invitation_obj,
            "presence": presence
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans emargement_lien: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.post("/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}", name="signer_emargement_lien")
async def signer_emargement_lien(
    seminaire_id: int,
    session_id: int,
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
    """Signer l'émargement via lien"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Vérifier le token
        invitation = seminaire_service.get_invitation_by_token(token, db, schema_name)
        if not invitation:
            raise HTTPException(status_code=404, detail="Lien d'émargement invalide")
        
        # Vérifier que l'invitation est pour ce séminaire
        if invitation.get('seminaire_id') != seminaire_id:
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
                filename = f"photo_seminaire{seminaire_id}_session{session_id}_candidat{candidat_id}_{timestamp}.png"
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
                filename = f"signature_seminaire{seminaire_id}_session{session_id}_candidat{candidat_id}_{timestamp}.png"
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
        
        presence_data = PresenceSeminaireCreate(
            session_id=session_id,
            candidat_id=candidat_id,
            presence="present",  # Texte simple
            heure_arrivee=datetime.now(timezone.utc),
            methode_signature=MethodeSignature(methode_signature),
            signature_manuelle=signature_manuelle,
            signature_digitale=signature_digitale,
            photo_signature=photo_signature,
            commentaire=commentaire,
            ip_signature=request.client.host
        )
        
        presence = seminaire_service.mark_presence(presence_data, db)
        
        # Note: L'acceptation de l'invitation se fait via le bouton dans l'email, pas lors de l'émargement
        # L'émargement crée seulement la présence, pas l'acceptation
        
        # Récupérer le séminaire et la session pour le template
        seminaire_dict = seminaire_service.get_seminaire(seminaire_id, db, schema_name)
        session_dict = seminaire_service.get_session(session_id, db, schema_name)
        
        if not seminaire_dict or not session_dict:
            raise HTTPException(status_code=404, detail="Séminaire ou session non trouvé")
        
        # Convertir en objets simples pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_dict.get('id'),
            'titre': seminaire_dict.get('titre'),
            'description': seminaire_dict.get('description'),
            'date_debut': seminaire_dict.get('date_debut'),
            'date_fin': seminaire_dict.get('date_fin'),
            'lieu': seminaire_dict.get('lieu')
        })()
        
        session = type('SessionSeminaire', (), {
            'id': session_dict.get('id'),
            'titre': session_dict.get('titre'),
            'date_session': session_dict.get('date_session'),
            'heure_debut': session_dict.get('heure_debut'),
            'heure_fin': session_dict.get('heure_fin')
        })()
        
        candidat = type('Candidat', (), {
            'id': invitation.get('candidat_id'),
            'nom': invitation.get('candidat_nom', ''),
            'prenom': invitation.get('candidat_prenom', ''),
            'email': invitation.get('candidat_email', '')
        })()
        
        return templates.TemplateResponse("pages/seminaires/emargement_confirmation.html", {
            "request": request,
            "seminaire": seminaire,
            "session": session,
            "presence": presence,
            "candidat": candidat
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans signer_emargement_lien: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la signature: {str(e)}")

@router.get("/{seminaire_id}/sessions/{session_id}/emargement",name="emargement_session", response_class=HTMLResponse)
async def emargement_session(
    seminaire_id: int,
    session_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement pour une session"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Récupérer la session via requête SQL directe
        session_query = text(f"""
            SELECT id, seminaire_id, titre, description, type_session, date_session,
                   heure_debut, heure_fin, lieu, visioconf_url, capacite, obligatoire, cree_le
            FROM {schema_name}.session_seminaire
            WHERE id = :session_id
        """)
        session_result = db.exec(session_query.bindparams(session_id=session_id)).first()
        if not session_result:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir type_session en string minuscule si nécessaire
        type_session_str = None
        if session_result.type_session:
            if hasattr(session_result.type_session, 'value'):
                type_session_str = session_result.type_session.value.lower()
            else:
                type_session_str = str(session_result.type_session).lower()
        
        # Convertir les résultats en objets simples pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })()
        })()
        
        session = type('SessionSeminaire', (), {
            'id': session_result.id,
            'seminaire_id': session_result.seminaire_id,
            'titre': session_result.titre,
            'description': session_result.description,
            'type_session': type_session_str or session_result.type_session,
            'date_session': session_result.date_session,
            'heure_debut': session_result.heure_debut,
            'heure_fin': session_result.heure_fin,
            'lieu': session_result.lieu,
            'visioconf_url': session_result.visioconf_url,
            'capacite': session_result.capacite,
            'obligatoire': session_result.obligatoire,
            'cree_le': session_result.cree_le
        })()
        
        presences_data = seminaire_service.get_presences_with_invitation_details(seminaire_id, session_id, db, schema_name)
        stats = seminaire_service.get_presence_stats_with_invitations(seminaire_id, session_id, db, schema_name)
        
        return templates.TemplateResponse("pages/seminaires/emargement.html", {
            "request": request,
            "seminaire": seminaire,
            "session": session,
            "presences_data": presences_data,
            "stats": stats,
            "current_user": current_user,
            "utilisateur": current_user
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans emargement_session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de l'émargement: {str(e)}")

@router.post("/{seminaire_id}/sessions/{session_id}/emargement",name="marquer_presence_session")
async def marquer_presence(
    seminaire_id: int,
    session_id: int,
    request: Request,
    candidat_id: int = Form(...),
    presence: str = Form(...),
    methode_signature: str = Form("MANUEL"),
    signature_data: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Marquer la présence d'un participant"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
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
                filename = f"signature_seminaire{seminaire_id}_session{session_id}_candidat{candidat_id}_{timestamp}.png"
                file_path = signatures_dir / filename
                
                # Sauvegarder l'image
                with open(file_path, "wb") as f:
                    f.write(signature_bytes)
                
                # Générer l'URL relative pour la base de données
                signature_digitale = f"{path_config.get_mount_path('media')}/emargements/signatures/{schema_name.lower()}/{filename}"
            except Exception as e:
                logger.error(f"❌ Erreur lors de la sauvegarde de la signature digitale: {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Erreur lors de la sauvegarde de la signature: {str(e)}")
        elif methode_signature == "manuel":
            # Pour la signature manuelle, on utilise directement le texte
            signature_manuelle = signature_data
        
        presence_data = PresenceSeminaireCreate(
            session_id=session_id,
            candidat_id=candidat_id,
            presence=StatutPresence(presence),
            methode_signature=MethodeSignature(methode_signature),
            signature_manuelle=signature_manuelle,
            signature_digitale=signature_digitale,
            photo_signature=None,  # Pas de photo pour l'émargement tablette
            note=note
        )
        
        presence_obj = seminaire_service.mark_presence(presence_data, db)
        
        # Rediriger vers emargement_direct pour revenir à la liste
        programme_param = request.query_params.get('programme', '')
        redirect_url = request.url_for("emargement_direct", seminaire_id=seminaire_id, session_id=session_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans marquer_presence: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors du marquage de présence: {str(e)}")

@router.get("/{seminaire_id}/livrables",name="livrables_seminaire", response_class=HTMLResponse)
async def livrables_seminaire(
    seminaire_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page de gestion des livrables"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom, s.organisateur as organisateur_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })(),
            'organisateur_nom': seminaire_result.organisateur_nom
        })()
        
        livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db, schema_name)
        
        return templates.TemplateResponse("pages/seminaires/livrables.html", {
            "request": request,
            "seminaire": seminaire,
            "livrables": livrables,
            "current_user": current_user,
            "utilisateur": current_user,
            "schema_name": schema_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans livrables_seminaire: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage des livrables: {str(e)}")

@router.post("/{seminaire_id}/livrables/nouveau",name="creer_livrable_seminaire")
async def creer_livrable(
    seminaire_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    type_livrable: str = Form(...),
    obligatoire: bool = Form(True),
    date_limite: datetime = Form(None),
    consignes: str = Form(""),
    format_accepte: str = Form(""),
    taille_max_mb: str = Form(""),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Créer un nouveau livrable"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Convertir taille_max_mb en entier ou None
        taille_max_mb_value = None
        if taille_max_mb and taille_max_mb.strip():
            try:
                taille_max_mb_value = int(taille_max_mb)
            except ValueError:
                taille_max_mb_value = None
        
        livrable_data = LivrableSeminaireCreate(
            seminaire_id=seminaire_id,
            titre=titre,
            description=description,
            type_livrable=type_livrable,
            obligatoire=obligatoire,
            date_limite=date_limite,
            consignes=consignes,
            format_accepte=format_accepte,
            taille_max_mb=taille_max_mb_value
        )
        
        livrable = seminaire_service.create_livrable(livrable_data, db)
        programme_param = request.query_params.get('programme', '')
        redirect_url = request.url_for("livrables_seminaire", seminaire_id=seminaire_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans creer_livrable: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du livrable: {str(e)}")

@router.post("/{seminaire_id}/livrables/{livrable_id}/modifier", name="modifier_livrable_seminaire")
async def modifier_livrable(
    seminaire_id: int,
    livrable_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    type_livrable: str = Form(...),
    obligatoire: bool = Form(True),
    date_limite: datetime = Form(None),
    consignes: str = Form(""),
    format_accepte: str = Form(""),
    taille_max_mb: str = Form(""),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Modifier un livrable existant"""
    logger.info(f"🚀🚀🚀 ROUTE modifier_livrable APPELÉE 🚀🚀🚀")
    logger.info(f"🔍 URL complète: {request.url}")
    logger.info(f"🔍 Méthode: {request.method}")
    logger.info(f"🔍 seminaire_id: {seminaire_id}, livrable_id: {livrable_id}")
    logger.info(f"🔍 Path: {request.url.path}")
    logger.info(f"🔍 Query params: {dict(request.query_params)}")
    logger.info(f"🔍 Headers: {dict(request.headers)}")
    try:
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Convertir taille_max_mb en entier ou None
        taille_max_mb_value = None
        if taille_max_mb and taille_max_mb.strip():
            try:
                taille_max_mb_value = int(taille_max_mb)
            except ValueError:
                taille_max_mb_value = None
        
        livrable_data = LivrableSeminaireCreate(
            seminaire_id=seminaire_id,
            titre=titre,
            description=description,
            type_livrable=type_livrable,
            obligatoire=obligatoire,
            date_limite=date_limite,
            consignes=consignes,
            format_accepte=format_accepte,
            taille_max_mb=taille_max_mb_value
        )
        
        livrable = seminaire_service.update_livrable(livrable_id, livrable_data, db, schema_name)
        if not livrable:
            raise HTTPException(status_code=404, detail="Livrable non trouvé")
        
        programme_param = request.query_params.get('programme', '')
        redirect_url = request.url_for("livrables_seminaire", seminaire_id=seminaire_id)
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans modifier_livrable: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la modification du livrable: {str(e)}")

@router.post("/{seminaire_id}/livrables/{livrable_id}/rendre",name="rendre_livrable_seminaire")
async def rendre_livrable(
    seminaire_id: int,
    livrable_id: int,
    request: Request,
    candidat_id: int = Form(...),
    fichier: UploadFile = File(...),
    commentaire: str = Form(""),
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Rendre un livrable"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Vérifier le fichier
        if not fichier.filename:
            raise HTTPException(status_code=400, detail="Aucun fichier fourni")
        
        # Créer le répertoire de stockage
        subfolder = f"seminaires/{seminaire_id}/livrables"
        
        # Générer un nom de fichier unique
        file_extension = os.path.splitext(fichier.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Utiliser FileUploadService pour sauvegarder le fichier
        file_info = await FileUploadService.save_file(
            fichier,
            "media",
            unique_filename,
            subfolder=subfolder
        )
        
        # Créer le rendu
        file_data = {
            'nom_fichier': fichier.filename,
            'chemin_fichier': file_info["relative_path"],
            'taille_fichier': file_info["size"],
            'type_mime': fichier.content_type or 'application/octet-stream',
            'commentaire_candidat': commentaire
        }
        
        rendu = seminaire_service.submit_livrable(livrable_id, candidat_id, file_data, db)
        return RedirectResponse(url=request.url_for("livrables_seminaire", seminaire_id=seminaire_id), status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans rendre_livrable: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors du rendu du livrable: {str(e)}")

@router.get("/{seminaire_id}/livrables/candidat", name="livrables_candidat", response_class=HTMLResponse)
async def livrables_candidat(
    request: Request,
    seminaire_id: int,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page des livrables pour un candidat"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom, s.organisateur as organisateur_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })(),
            'organisateur_nom': seminaire_result.organisateur_nom
        })()
        
        # Récupérer le candidat
        candidat = seminaire_service.get_inscription_candidat(seminaire_id, current_user.email, db)
        if not candidat:
            raise HTTPException(status_code=404, detail="Vous n'êtes pas inscrit à ce séminaire")
        
        # Récupérer les livrables du séminaire
        livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db, schema_name)
        
        # Récupérer les rendus du candidat
        rendus = seminaire_service.get_rendus_candidat(candidat.id, db)
        
        return templates.TemplateResponse("pages/seminaires/livrables_candidat.html", {
            "request": request,
            "seminaire": seminaire,
            "candidat": candidat,
            "inscription": candidat,  # Pour compatibilité avec le template
            "livrables": livrables,
            "rendus": rendus
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans livrables_candidat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage des livrables: {str(e)}")

@router.get("/{seminaire_id}/livrables/{livrable_id}", name="get_livrable", response_class=JSONResponse)
async def get_livrable(
    seminaire_id: int,
    livrable_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Récupérer un livrable par son ID (API JSON)"""
    try:
        # Récupérer le paramètre programme depuis la query string
        programme_param = request.query_params.get('programme')
        if programme_param:
            schema_name = programme_param.lower()
        else:
            schema_name = get_schema_from_request(request) or 'acd'
        
        logger.info(f"🔍 get_livrable - programme_param: {programme_param}, schema_name: {schema_name}")
        schema_routing_service.set_schema(schema_name)
        
        livrable = seminaire_service.get_livrable_by_id(livrable_id, db, schema_name)
        if not livrable:
            raise HTTPException(status_code=404, detail="Livrable non trouvé")
        
        # Formater la date_limite pour le formulaire datetime-local
        date_limite_str = None
        if livrable.date_limite:
            date_limite_str = livrable.date_limite.strftime('%Y-%m-%dT%H:%M')
        
        return JSONResponse(content={
            "id": livrable.id,
            "seminaire_id": livrable.seminaire_id,
            "titre": livrable.titre,
            "description": livrable.description or "",
            "type_livrable": livrable.type_livrable,
            "obligatoire": livrable.obligatoire,
            "date_limite": date_limite_str,
            "consignes": livrable.consignes or "",
            "format_accepte": livrable.format_accepte or "",
            "taille_max_mb": livrable.taille_max_mb
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans get_livrable: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du livrable: {str(e)}")

# === ROUTES PUBLIQUES (pour les invitations) ===

@router.get("/{seminaire_id}/sessions/{session_id}/emargement-direct", name="emargement_direct", response_class=HTMLResponse)
async def emargement_direct(
    seminaire_id: int, session_id: int, request: Request,
    db: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page publique d'émargement direct"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Récupérer le séminaire via requête SQL directe
        seminaire_query = text(f"""
            SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                   s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                   s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                   p.code as programme_code, p.nom as programme_nom, s.organisateur as organisateur_nom
            FROM {schema_name}.seminaire s
            LEFT JOIN public.programme p ON s.programme_id = p.id
            WHERE s.id = :seminaire_id
        """)
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Convertir le statut en string minuscule pour le template
        statut_str = None
        if seminaire_result.statut:
            if hasattr(seminaire_result.statut, 'value'):
                statut_str = seminaire_result.statut.value.lower()
            else:
                statut_str = str(seminaire_result.statut).lower()
        
        # Convertir le résultat en objet simple pour le template
        seminaire = type('Seminaire', (), {
            'id': seminaire_result.id,
            'titre': seminaire_result.titre,
            'description': seminaire_result.description,
            'programme_id': seminaire_result.programme_id,
            'date_debut': seminaire_result.date_debut,
            'date_fin': seminaire_result.date_fin,
            'lieu': seminaire_result.lieu,
            'adresse_complete': seminaire_result.adresse_complete,
            'organisateur': seminaire_result.organisateur,
            'capacite_max': seminaire_result.capacite_max,
            'statut': statut_str,
            'actif': seminaire_result.actif,
            'invitation_auto': seminaire_result.invitation_auto,
            'invitation_promos': seminaire_result.invitation_promos,
            'cree_le': seminaire_result.cree_le,
            'modifie_le': seminaire_result.modifie_le,
            'programme': type('Programme', (), {
                'code': seminaire_result.programme_code or seminaire_result.programme_nom,
                'nom': seminaire_result.programme_nom
            })(),
            'organisateur_nom': seminaire_result.organisateur_nom
        })()
        
        session_obj = seminaire_service.get_session(session_id, db)
        if not session_obj:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        # Récupérer les présences existantes pour l'émargement direct
        presences = seminaire_service.get_presences_for_direct_emargement(seminaire_id, session_id, db, schema_name)
        
        # Récupérer toutes les invitations avec les détails des candidats via requête SQL directe
        invitations_query = text(f"""
            SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                   i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                   c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email, c.photo_profil as candidat_photo_profil
            FROM {schema_name}.invitation_seminaire i
            LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
            WHERE i.seminaire_id = :seminaire_id AND i.candidat_id IS NOT NULL
            ORDER BY c.nom, c.prenom
        """)
        invitations_results = db.exec(invitations_query.bindparams(seminaire_id=seminaire_id)).all()
        
        # Convertir les résultats en objets simples
        invitations = []
        for result in invitations_results:
            statut_str = str(result.statut).lower() if result.statut else 'envoyee'
            type_inv_str = None
            if result.type_invitation:
                if hasattr(result.type_invitation, 'value'):
                    type_inv_str = result.type_invitation.value.lower()
                else:
                    type_inv_str = str(result.type_invitation).lower()
            
            invitations.append(type('InvitationSeminaire', (), {
                'id': result.id,
                'seminaire_id': result.seminaire_id,
                'type_invitation': type_inv_str,
                'candidat_id': result.candidat_id,
                'promotion_id': result.promotion_id,
                'statut': statut_str,
                'email_envoye': result.email_envoye,
                'date_envoi': result.date_envoi,
                'date_reponse': result.date_reponse,
                'token_invitation': result.token_invitation,
                'cree_le': result.cree_le,
                'candidat': type('Candidat', (), {
                    'id': result.candidat_id,
                    'nom': result.candidat_nom,
                    'prenom': result.candidat_prenom,
                    'email': result.candidat_email,
                    'photo_profil': result.candidat_photo_profil
                })() if result.candidat_id else None
            })())
        
        return templates.TemplateResponse("pages/seminaires/emargement_direct.html", {
            "request": request, "seminaire": seminaire, "session": session_obj,
            "presences": presences,
            "invitations": invitations
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans emargement_direct: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")



@router.post("/{seminaire_id}/sessions/{session_id}/supprimer", name="supprimer_session")
async def supprimer_session(
    seminaire_id: int,
    session_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer une session et toutes ses données associées"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Vérifier que le séminaire existe via requête SQL directe
        seminaire_query = text(f"SELECT id FROM {schema_name}.seminaire WHERE id = :seminaire_id")
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Vérifier que la session existe via requête SQL directe
        session_query = text(f"SELECT id FROM {schema_name}.session_seminaire WHERE id = :session_id")
        session_result = db.exec(session_query.bindparams(session_id=session_id)).first()
        if not session_result:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        # Supprimer la session (cascade supprimera les présences, livrables, etc.)
        success = seminaire_service.delete_session(session_id, db, schema_name)
        
        if not success:
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression de la session")
        
        return {"message": "Session supprimée avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans supprimer_session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/{seminaire_id}/sessions/{session_id}/participant/{candidat_id}/supprimer", name="supprimer_participant_session")
async def supprimer_participant_session(
    seminaire_id: int,
    session_id: int,
    candidat_id: int,
    request: Request,
    db: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer un participant d'une session de séminaire"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table seminaire existe dans le schéma
        table_exists = table_exists_anywhere("seminaire", db, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé dans ce programme")
        
        # Vérifier que le séminaire existe via requête SQL directe
        seminaire_query = text(f"SELECT id FROM {schema_name}.seminaire WHERE id = :seminaire_id")
        seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
        if not seminaire_result:
            raise HTTPException(status_code=404, detail="Séminaire non trouvé")
        
        # Vérifier que la session existe via requête SQL directe
        session_query = text(f"SELECT id FROM {schema_name}.session_seminaire WHERE id = :session_id")
        session_result = db.exec(session_query.bindparams(session_id=session_id)).first()
        if not session_result:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        # Supprimer le participant
        success = seminaire_service.remove_participant_from_session(seminaire_id, session_id, candidat_id, db)
        
        if not success:
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression du participant")
        
        # Rediriger vers la page d'origine (Referer) ou vers la page d'émargement par défaut
        referer = request.headers.get("referer")
        if referer and f"/seminaires/{seminaire_id}/sessions/{session_id}" in referer:
            return RedirectResponse(url=referer, status_code=303)
        else:
            return RedirectResponse(url=request.url_for("emargement_seminaire", seminaire_id=seminaire_id, session_id=session_id), status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur dans supprimer_participant_session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression du participant: {str(e)}")