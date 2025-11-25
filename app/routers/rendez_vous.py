# app/routers/rendez_vous.py
from datetime import datetime, date, timezone
from typing import Optional, List
import logging
import os, secrets, string, time
import json
import base64
from pathlib import Path
from fastapi import APIRouter, Depends, Request, Query, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
import httpx
from sqlmodel import Session, select

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user, get_current_user_optional
from ..core.program_schema_integration import table_exists_anywhere, get_schema_routing_service, SchemaRoutingService, get_schema_from_request
from ..core.path_config import path_config
from sqlalchemy import text, and_, or_, func
from ..core.config import settings
from ..core.utils import EmailUtils
from ..models.base import User, Programme, Candidat, Entreprise
from ..models.rendez_vous import RendezVous, EmargementRDV
from ..models.enums import TypeRDV, StatutRDV, UserRole, DecisionJury
from ..schemas.rendez_vous_schemas import RendezVousCreate, RendezVousUpdate, RendezVousFilter
from ..services.rendez_vous_service import RendezVousService
from ..templates import templates

# Configuration vidéo
APP_NAME = os.getenv("APP_NAME", "TIEKA Coaching • Visioconférence")
GOOGLE_MEET_DOMAIN = os.getenv("GOOGLE_MEET_DOMAIN", "meet.google.com")
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "client")
DEFAULT_DISPLAY_NAME = os.getenv("DEFAULT_DISPLAY_NAME", "Invité")

# Utils vidéo
ALPHABET = string.ascii_lowercase + string.digits

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/rendez-vous", name="rendez_vous_home", response_class=HTMLResponse)
def rendez_vous_home(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    candidat_nom: Optional[str] = Query(None),
    statut: Optional[str] = Query(None)
):
    # Normaliser les filtres : convertir None en chaîne vide et supprimer les espaces
    candidat_nom = candidat_nom.strip() if candidat_nom else ""
    statut = statut.strip() if statut else ""
    
    if settings.DEBUG and candidat_nom:
        logger.info(f"🔍 [rendez_vous_home] Filtre candidat_nom reçu: '{candidat_nom}'")

    print("================================================"*30)
    print("DEBUTRENDEZ_VOUS_HOME")
    print("================================================"*30)
    # Récupérer le schéma (get_schema_from_request gère déjà query params, request.state, etc.)
    schema_name = get_schema_from_request(request) or 'acd'
    
    # IMPORTANT: Mettre à jour le service avec le schéma correct AVANT d'obtenir les modèles
    # Cela garantit que le search_path est configuré et que les modèles sont créés avec le bon schéma
    schema_routing_service.set_schema(schema_name)
    
    # IMPORTANT: Configurer explicitement le search_path pour cette session
    # Cela garantit que PostgreSQL utilise le bon schéma même si SQLAlchemy ne génère pas le schéma explicite
    try:
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        logger.info(f"🔍 [RENDEZ_VOUS_HOME] Search_path configuré explicitement pour {schema_name}")
    except Exception as e:
        logger.warning(f"⚠️ [RENDEZ_VOUS_HOME] Impossible de configurer search_path explicitement: {e}")
    
    # Vérifier que le search_path est bien configuré
    try:
        search_path_result = session.exec(text("SHOW search_path")).first()
        logger.info(f"🔍 [RENDEZ_VOUS_HOME] Search_path actuel après set_schema: {search_path_result}")
    except Exception as e:
        logger.warning(f"⚠️ [RENDEZ_VOUS_HOME] Impossible de vérifier search_path: {e}")
    
    logger.info(f"🔍 [RENDEZ_VOUS_HOME] Schéma configuré: {schema_name}")
    
    # Construction des filtres (seulement candidat_nom et statut)
    # Utiliser candidat_nom seulement s'il n'est pas vide
    candidat_nom_filter = candidat_nom if candidat_nom else None
    
    statut_enum = None
    if statut:
        try:
            statut_enum = StatutRDV(statut)
        except ValueError:
            logger.warning(f"Statut invalide: {statut}")
    
    # Utiliser directement les modèles de base avec le schéma spécifié dans les requêtes SQL
    # Pas besoin de créer des classes dynamiques, on utilise directement les modèles avec le schéma dans le SQL
    logger.info(f"🔍 [rendez_vous_home] Utilisation directe des modèles avec schéma {schema_name}")
    
    # Récupération des rendez-vous avec les modèles spécifiques au schéma
    
    try:
        # Vérifier que la table existe dans le schéma avant de faire la requête
        table_exists = table_exists_anywhere("rendez_vous", session, schema_name)
        logger.info(f"🔍 [rendez_vous_home] Table 'rendez_vous' existe dans schéma '{schema_name}': {table_exists}")
        
        # Vérifier le search_path actuel
        try:
            search_path_result = session.exec(text("SHOW search_path")).first()
            logger.info(f"🔍 [rendez_vous_home] Search_path actuel: {search_path_result}")
        except Exception as e:
            logger.info(f"🔍 [rendez_vous_home] Impossible de récupérer search_path: {e}")
        
        # Compter directement les rendez-vous dans le schéma via SQL
        try:
            count_query = text(f"SELECT COUNT(*) FROM {schema_name}.rendez_vous")
            count_result = session.exec(count_query).first()
            logger.info(f"🔍 [rendez_vous_home] Nombre de rendez-vous dans {schema_name}.rendez_vous (via SQL direct): {count_result}")
            
            # Si des rendez-vous existent, afficher quelques exemples
            if count_result and count_result > 0:
                sample_query = text(f"SELECT id, candidat_id, conseiller_id, statut, debut FROM {schema_name}.rendez_vous LIMIT 5")
                sample_results = session.exec(sample_query).all()
                logger.info(f"🔍 [rendez_vous_home] Exemples de rendez-vous dans {schema_name}.rendez_vous: {sample_results}")
        except Exception as e:
            logger.info(f"🔍 [rendez_vous_home] Impossible de compter via SQL direct: {e}")
        
        if not table_exists:
            logger.info(f"🔍 [rendez_vous_home] Table n'existe pas, liste vide")
            rendez_vous = []
        else:
            # Construire la requête SQL directe avec le schéma explicite
            # Utiliser directement les noms de tables avec le schéma au lieu de créer des classes dynamiques
            logger.info(f"🔍 [rendez_vous_home] Construction de la requête SQL directe pour schéma {schema_name}")
            
            # Construire la requête SQL avec le schéma explicite
            base_query = f"""
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
                    c.nom as candidat_nom,
                    c.prenom as candidat_prenom,
                    u.nom_complet as conseiller_nom
                FROM {schema_name}.rendez_vous rv
                INNER JOIN {schema_name}.candidat c ON rv.candidat_id = c.id
                LEFT JOIN public."user" u ON rv.conseiller_id = u.id
            """
            
            # Construire les conditions WHERE
            where_conditions = []
            params = {}
            
            if statut_enum:
                where_conditions.append("rv.statut = :statut")
                params["statut"] = statut_enum.value
            
            if candidat_nom_filter:
                where_conditions.append("(LOWER(c.nom) LIKE :candidat_nom OR LOWER(c.prenom) LIKE :candidat_nom)")
                params["candidat_nom"] = f"%{candidat_nom_filter.lower()}%"
            
            # Ajouter le filtre partenaire_bpi si nécessaire
            from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
            add_partenaire_bpi_filter(current_user, where_conditions, params, "c.")
            
            # Ajouter les conditions WHERE si nécessaire
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            # Ajouter le tri
            base_query += " ORDER BY rv.debut DESC"
            
            logger.info(f"🔍 [rendez_vous_home] Requête SQL directe: {base_query[:200]}...")
            logger.info(f"🔍 [rendez_vous_home] Paramètres: {params}")
            
            # Exécuter la requête SQL directe avec paramètres
            if params:
                query = text(base_query).bindparams(**params)
            else:
                query = text(base_query)
            results = session.exec(query).all()
            logger.info(f"🔍 [rendez_vous_home] Nombre de résultats bruts: {len(results)}")
            
            # Log du contenu brut de la table (seulement en mode DEBUG)
            if settings.DEBUG:
                if len(results) > 0:
                    logger.info(f"📋 [rendez_vous_home] Contenu de la table rendez-vous ({len(results)} résultats):")
                    for idx, row in enumerate(results[:5]):  # Afficher les 5 premiers
                        # row est maintenant un Row avec toutes les colonnes sélectionnées explicitement
                        # Accéder directement aux colonnes via leur nom
                        rdv_id = row.id
                        candidat_id = row.candidat_id
                        conseiller_id = row.conseiller_id
                        statut = row.statut
                        debut = row.debut
                        candidat_nom = row.candidat_nom
                        candidat_prenom = row.candidat_prenom
                        conseiller_nom = row.conseiller_nom
                        
                        logger.info(f"  [{idx+1}] RDV ID={rdv_id}, candidat_id={candidat_id}, conseiller_id={conseiller_id}, statut={statut}, debut={debut}")
                        logger.info(f"      - candidat_nom={candidat_nom}, candidat_prenom={candidat_prenom}")
                        logger.info(f"      - conseiller_nom={conseiller_nom}")
                else:
                    logger.info(f"⚠️ [rendez_vous_home] Aucun résultat trouvé dans la table rendez-vous du schéma {schema_name}")
            
            # Formater les résultats avec les noms au lieu des IDs
            rendez_vous = []
            for row in results:
                # row est un Row avec toutes les colonnes sélectionnées explicitement
                # Accéder directement aux colonnes via leur nom
                rdv_id = row.id
                candidat_id = row.candidat_id
                conseiller_id = row.conseiller_id
                type_rdv = row.type_rdv
                statut = row.statut
                debut = row.debut
                fin = row.fin
                lieu = row.lieu
                notes = row.notes
                meet_link = row.meet_link
                candidat_nom = row.candidat_nom
                candidat_prenom = row.candidat_prenom
                conseiller_nom = row.conseiller_nom
                
                # Construire le nom complet du candidat
                candidat_nom_complet = None
                if candidat_prenom and candidat_nom:
                    candidat_nom_complet = f"{candidat_prenom} {candidat_nom}"
                elif candidat_prenom:
                    candidat_nom_complet = candidat_prenom
                elif candidat_nom:
                    candidat_nom_complet = candidat_nom
                
                # Convertir les enums en strings pour le template (en minuscules pour correspondre aux comparaisons)
                # type_rdv et statut peuvent être des strings ou des enums selon la base de données
                type_rdv_str = None
                if type_rdv:
                    if hasattr(type_rdv, 'value'):
                        type_rdv_str = type_rdv.value.lower()
                    else:
                        type_rdv_str = str(type_rdv).lower()
                
                statut_str = None
                if statut:
                    if hasattr(statut, 'value'):
                        statut_str = statut.value.lower()
                    else:
                        statut_str = str(statut).lower()
                
                rendez_vous.append({
                    "id": rdv_id,
                    "candidat_nom": candidat_nom_complet,
                    "conseiller_nom": conseiller_nom or None,
                    "type_rdv": type_rdv_str,
                    "statut": statut_str,
                    "debut": debut,
                    "fin": fin,
                    "lieu": lieu or None,
                    "notes": notes or None,
                    "meet_link": meet_link or None
                })
            
            # Log des données formatées (seulement en mode DEBUG)
            if settings.DEBUG:
                logger.info(f"📋 [rendez_vous_home] Nombre de rendez-vous formatés: {len(rendez_vous)}")
                if len(rendez_vous) > 0:
                    logger.info(f"📋 [rendez_vous_home] Premier rendez-vous formaté: {rendez_vous[0]}")
                    logger.info(f"📋 [rendez_vous_home] Exemple de données formatées (3 premiers):")
                    for idx, rdv in enumerate(rendez_vous[:3]):
                        logger.info(f"  [{idx+1}] {rdv}")
    except Exception as e:
        logger.error(f"Erreur lors de la recherche des rendez-vous: {e}", exc_info=True)
        logger.info(f"🔍 [rendez_vous_home] Exception détaillée: {e}", exc_info=True)
        rendez_vous = []
    
    # Statistiques avec requête SQL directe
    try:
        # Réutiliser la vérification de l'existence de la table faite plus haut
        if not table_exists:
            logger.info(f"🔍 [rendez_vous_home] Stats - Table rendez_vous n'existe pas dans le schéma {schema_name}, statistiques à zéro")
            stats = {"total": 0, "planifies": 0, "a_venir": 0, "termines": 0, "annules": 0}
        else:
            # D'abord, vérifier les valeurs réelles de statut dans la base de données
            try:
                check_stats_query = text(f"""
                    SELECT DISTINCT statut, COUNT(*) as count
                    FROM {schema_name}.rendez_vous
                    GROUP BY statut
                """)
                statut_values = session.exec(check_stats_query).all()
                logger.info(f"🔍 [rendez_vous_home] Stats - Valeurs de statut trouvées dans {schema_name}.rendez_vous: {statut_values}")
            except Exception as e:
                logger.warning(f"⚠️ [rendez_vous_home] Impossible de vérifier les valeurs de statut: {e}")
            
            # Utiliser une requête SQL directe pour les statistiques avec LOWER() pour être sûr
            stats_query = text(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'planifie') as a_venir,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'termine') as termines,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'annule') as annules
                FROM {schema_name}.rendez_vous
            """)
            
            logger.info(f"🔍 [rendez_vous_home] Stats - Requête SQL directe pour schéma {schema_name}")
            
            stats_result = session.exec(stats_query).first()
            
            if stats_result:
                stats = {
                    "total": stats_result.total or 0,
                    "planifies": stats_result.a_venir or 0,  # Le template utilise "planifies"
                    "a_venir": stats_result.a_venir or 0,
                    "termines": stats_result.termines or 0,
                    "annules": stats_result.annules or 0
                }
                logger.info(f"🔍 [rendez_vous_home] Stats - Schéma {schema_name}: total={stats['total']}, planifies={stats['planifies']}, termines={stats['termines']}, annules={stats['annules']}")
            else:
                stats = {"total": 0, "planifies": 0, "a_venir": 0, "termines": 0, "annules": 0}
                logger.info(f"🔍 [rendez_vous_home] Stats - Aucun résultat trouvé dans le schéma {schema_name}")
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques rendez-vous: {e}", exc_info=True)
        stats = {"total": 0, "planifies": 0, "a_venir": 0, "termines": 0, "annules": 0}
    
    try:
        return templates.TemplateResponse("pages/rendez_vous/liste.html", {
            "request": request,
            "current_user": current_user,
            "utilisateur": current_user,
            "rendez_vous": rendez_vous,
            "filters": {
                "candidat_nom": candidat_nom if candidat_nom else "",
                "statut": statut if statut else ""
            },
            "stats": stats,
            "schema_name": schema_name
        })
    except Exception as e:
        logger.error(f"Erreur lors du rendu du template rendez-vous: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'affichage de la page: {str(e)}")

@router.post("/rendez-vous/creer", name="rendez_vous_create")
def rendez_vous_create(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    candidat_id: int = Form(...),
    programme: str = Form(...),
    conseiller_id: Optional[int] = Form(None),
    type_rdv: str = Form(...),
    statut: str = Form(...),
    debut: str = Form(...),
    fin: Optional[str] = Form(None),
    lieu: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """Créer un nouveau rendez-vous"""
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request, programme=programme) or 'public'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que le candidat est validé via requête SQL directe
        candidat_query = text(f"SELECT id, statut FROM {schema_name}.candidat WHERE id = :candidat_id")
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        
        if candidat_result.statut != DecisionJury.VALIDE.value:
            raise HTTPException(status_code=400, detail="Le candidat doit être validé pour créer un rendez-vous")
        
        if settings.DEBUG:
            logger.info(f"🔍 [RENDEZ_VOUS_CREATE] Candidat validé trouvé: ID={candidat_id}")
        
        # Validation des données
        rdv_data = RendezVousCreate(
            candidat_id=candidat_id,
            conseiller_id=conseiller_id,
            type_rdv=TypeRDV(type_rdv),
            statut=StatutRDV(statut),
            debut=datetime.fromisoformat(debut),
            fin=datetime.fromisoformat(fin) if fin else None,
            lieu=lieu,
            notes=notes
        )
        
        service = RendezVousService(session)
        rdv = service.create_rendez_vous(rdv_data)
        session.commit()
        
        # Inclure le programme dans l'URL de redirection
        redirect_url = request.url_for("rendez_vous_home")
        if programme:
            redirect_url = f"{redirect_url}?programme={programme.upper()}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ [RENDEZ_VOUS_CREATE] Erreur lors de la création du rendez-vous: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création du rendez-vous: {str(e)}")

@router.get("/rendez-vous/{rdv_id}/api", name="rendez_vous_detail_api", response_class=JSONResponse)
def rendez_vous_detail_api(
    rdv_id: int,
    request: Request,
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """API pour récupérer les détails d'un rendez-vous en JSON"""
    
    if settings.DEBUG:
        logger.info(f"🔍 [rendez_vous_detail_api] Appel API pour RDV ID: {rdv_id}")
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'public'
    schema_routing_service.set_schema(schema_name)
    
    if settings.DEBUG:
        logger.info(f"🔍 [rendez_vous_detail_api] Schéma configuré: {schema_name}")
    
    service = RendezVousService(session)
    rdv_details = service.get_rendez_vous_with_details(rdv_id)
    
    if not rdv_details:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    # Récupération des conseillers pour l'édition
    conseillers = session.exec(
        select(User).where(User.role.in_([UserRole.CONSEILLER, UserRole.COORDINATEUR]))
    ).all()
    
    # Formater les dates pour JSON
    rdv_details_formatted = {
        **rdv_details,
        "debut": rdv_details["debut"].isoformat() if rdv_details.get("debut") else None,
        "fin": rdv_details["fin"].isoformat() if rdv_details.get("fin") else None,
        "conseillers": [
            {"id": c.id, "nom_complet": c.nom_complet}
            for c in conseillers
        ],
        "types_rdv": [t.value for t in TypeRDV],
        "statuts_rdv": [s.value for s in StatutRDV]
    }
    
    return JSONResponse(content=rdv_details_formatted)


@router.post("/rendez-vous/{rdv_id}/modifier", name="rendez_vous_update")
def rendez_vous_update(
    rdv_id: int,
    request: Request,
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme: Optional[str] = Form(None),
    conseiller_id: Optional[int] = Form(None),
    type_rdv: str = Form(...),
    statut: str = Form(...),
    debut: str = Form(...),
    fin: Optional[str] = Form(None),
    lieu: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """Modifier un rendez-vous"""
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request, programme=programme) or 'public'
        schema_routing_service.set_schema(schema_name)
        
        # Validation des données
        rdv_data = RendezVousUpdate(
            conseiller_id=conseiller_id,
            type_rdv=TypeRDV(type_rdv),
            statut=StatutRDV(statut),
            debut=datetime.fromisoformat(debut),
            fin=datetime.fromisoformat(fin) if fin else None,
            lieu=lieu,
            notes=notes
        )
        
        service = RendezVousService(session)
        rdv = service.update_rendez_vous(rdv_id, rdv_data)
        
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        session.commit()
        
        # Inclure le programme dans l'URL de redirection
        redirect_url = request.url_for("rendez_vous_home")
        if programme:
            redirect_url = f"{redirect_url}?programme={programme.upper()}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ [RENDEZ_VOUS_UPDATE] Erreur lors de la modification du rendez-vous: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Erreur lors de la modification du rendez-vous: {str(e)}")

@router.post("/rendez-vous/{rdv_id}/supprimer", name="rendez_vous_delete")
def rendez_vous_delete(
    rdv_id: int,
    request: Request,
    programme: Optional[str] = Form(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un rendez-vous"""
    
    # Récupérer le schéma (get_schema_from_request gère déjà le paramètre programme du formulaire)
    # Si le paramètre programme est fourni explicitement, il a la priorité
    schema_name = get_schema_from_request(request, programme=programme) or 'acd'
    
    # Mettre à jour le service avec le schéma correct
    schema_routing_service.set_schema(schema_name)
    
    if settings.DEBUG:
        logger.info(f"🗑️ [rendez_vous_delete] Suppression RDV ID: {rdv_id}, Schéma: {schema_name}, Programme reçu: {programme}")
    
    service = RendezVousService(session)
    success = service.delete_rendez_vous(rdv_id, schema_name=schema_name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    
    if settings.DEBUG:
        logger.info(f"✅ [rendez_vous_delete] RDV {rdv_id} supprimé avec succès")
    
    # Inclure le programme dans l'URL de redirection
    redirect_url = request.url_for("rendez_vous_home")
    if schema_name and schema_name != 'acd':
        redirect_url = f"{redirect_url}?programme={schema_name.upper()}"
    
    return RedirectResponse(url=redirect_url, status_code=303)

@router.get("/rendez-vous/api/candidats-valides", name="rendez_vous_api_candidats_valides", response_class=JSONResponse)
def rendez_vous_api_candidats_valides(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service),
    programme: str = Query("ACD"),
):
    """API pour récupérer les candidats validés pour créer un rendez-vous"""
    try:
        if settings.DEBUG:
            logger.info("🔍 [API_CANDIDATS_VALIDES] Début de la récupération des candidats validés")
        
        # Récupérer et configurer le schéma (même logique que rendez_vous_create)
        schema_name = get_schema_from_request(request, programme=programme) or 'public'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.info(f"🔍 [API_CANDIDATS_VALIDES] Programme: {programme}, Schéma: {schema_name}")
        
        # Récupérer le programme pour obtenir son nom et son code
        programme_obj = session.exec(
            select(Programme).where(Programme.code.ilike(schema_name))
        ).first()
        programme_id = programme_obj.id if programme_obj else None
        programme_nom = programme_obj.nom if programme_obj else schema_name.upper()
        programme_code = programme_obj.code if programme_obj else schema_name.upper()
        
        # Récupérer les candidats validés dans ce schéma via requête SQL directe
        where_conditions = ["c.statut = :statut"]
        params = {"statut": DecisionJury.VALIDE.value}
        
        # Ajouter le filtre partenaire_bpi si nécessaire
        from ..core.partenaire_bpi_filter import add_partenaire_bpi_filter
        add_partenaire_bpi_filter(current_user, where_conditions, params, "c.")
        
        candidats_query = text(f"""
            SELECT 
                c.id as candidat_id,
                c.nom,
                c.prenom,
                c.email,
                e.raison_sociale as entreprise_nom
            FROM {schema_name}.candidat c
            LEFT JOIN {schema_name}.entreprise e ON c.id = e.candidat_id
            WHERE {' AND '.join(where_conditions)}
            ORDER BY c.nom, c.prenom
        """)
        
        candidats_results = session.exec(candidats_query.bindparams(**params)).all()
        
        candidats = []
        for result in candidats_results:
            candidats.append({
                "candidat_id": result.candidat_id,
                "nom_complet": f"{result.prenom} {result.nom}",
                "email": result.email,
                "programme_nom": programme_nom,
                "programme_id": programme_id,
                "programme_code": programme_code,
                "entreprise_nom": result.entreprise_nom or "Non renseignée"
            })
        
        # Récupération des conseillers (dans le schéma public)
        conseillers = session.exec(
            select(User).where(User.role.in_([UserRole.CONSEILLER, UserRole.COORDINATEUR]))
        ).all()
        
        conseillers_list = []
        for conseiller in conseillers:
            conseillers_list.append({
                "id": conseiller.id,
                "nom_complet": conseiller.nom_complet
            })
        
        return JSONResponse(content={
            "candidats": candidats,
            "conseillers": conseillers_list,
            "types_rdv": [t.value for t in TypeRDV],
            "statuts_rdv": [s.value for s in StatutRDV]
        })
    except Exception as e:
        logger.error(f"❌ [API_CANDIDATS_VALIDES] Erreur lors de la récupération des candidats validés: {e}", exc_info=True)
        # Retourner un JSON valide même en cas d'erreur
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": f"Erreur lors de la récupération des données: {str(e)}",
                "candidats": [],
                "conseillers": [],
                "types_rdv": [t.value for t in TypeRDV],
                "statuts_rdv": [s.value for s in StatutRDV]
            }
        )

# ============================================================================
# ROUTES ÉMARGEMENT (fusionnées depuis emargement_router.py)
# ============================================================================

@router.get("/emargement/{rdv_id}", name="emargement_rdv")
async def page_emargement_conseiller(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement pour le conseiller"""
    logger.info(f"📝 Page émargement conseiller - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [page_emargement_conseiller] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv_result.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation de voir ce rendez-vous")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email, statut
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Récupérer l'émargement existant via requête SQL directe
        emargement = None
        if table_exists_anywhere("emargement_rdv", session, schema_name):
            emargement_query = text(f"""
                SELECT id, rdv_id, type_signataire, signataire_id, candidat_id, 
                       signature_conseiller, signature_candidat, 
                       date_signature_conseiller, date_signature_candidat,
                       ip_address, user_agent, cree_le
                FROM {schema_name}.emargement_rdv
                WHERE rdv_id = :rdv_id
            """)
            emargement_result = session.exec(emargement_query.bindparams(rdv_id=rdv_id)).first()
            if emargement_result:
                emargement = emargement_result
        
        # Si pas d'émargement et que la table existe, en créer un via INSERT SQL
        if not emargement and table_exists_anywhere("emargement_rdv", session, schema_name):
            now = datetime.now(timezone.utc)
            insert_query = text(f"""
                INSERT INTO {schema_name}.emargement_rdv 
                (rdv_id, type_signataire, signataire_id, candidat_id, cree_le)
                VALUES (:rdv_id, :type_signataire, :signataire_id, :candidat_id, :cree_le)
                RETURNING id, rdv_id, type_signataire, signataire_id, candidat_id, 
                          signature_conseiller, signature_candidat, 
                          date_signature_conseiller, date_signature_candidat,
                          ip_address, user_agent, cree_le
            """)
            emargement = session.exec(insert_query.bindparams(
                rdv_id=rdv_id,
                type_signataire="conseiller",
                signataire_id=current_user.id,
                candidat_id=candidat_result.id,
                cree_le=now
            )).first()
            session.commit()
        
        # Convertir les résultats en objets simples pour le template
        rdv = type('RendezVous', (), {
            'id': rdv_result.id,
            'candidat_id': rdv_result.candidat_id,
            'conseiller_id': rdv_result.conseiller_id,
            'type_rdv': rdv_result.type_rdv,
            'statut': rdv_result.statut,
            'debut': rdv_result.debut,
            'fin': rdv_result.fin,
            'lieu': rdv_result.lieu,
            'notes': rdv_result.notes,
            'meet_link': rdv_result.meet_link
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_result.id,
            'nom': candidat_result.nom,
            'prenom': candidat_result.prenom,
            'email': candidat_result.email,
            'statut': candidat_result.statut
        })()
        
        if settings.DEBUG:
            logger.debug(f"✅ Page émargement chargée pour RDV {rdv_id} dans schéma {schema_name}")
        
        return templates.TemplateResponse("pages/emargement/conseiller.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "emargement": emargement,
            "utilisateur": current_user,
            "settings": settings,
            "schema_name": schema_name
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans page_emargement_conseiller: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans page_emargement_conseiller: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")



@router.get("/emargement/{rdv_id}/candidat/{token}", name="page_emargement_candidat")
async def page_emargement_candidat(
    request: Request,
    rdv_id: int,
    token: str,
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page d'émargement pour le candidat (via token)"""
    logger.info(f"📝 Page émargement candidat - RDV ID: {rdv_id}, Token: {token[:10]}...")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [page_emargement_candidat] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email, statut
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # TODO: Valider le token (pour l'instant on accepte tout)
        # En production, il faudrait vérifier que le token est valide et non expiré
        
        # Récupérer l'émargement existant via requête SQL directe
        emargement = None
        if table_exists_anywhere("emargement_rdv", session, schema_name):
            emargement_query = text(f"""
                SELECT id, rdv_id, type_signataire, signataire_id, candidat_id, 
                       signature_conseiller, signature_candidat, 
                       date_signature_conseiller, date_signature_candidat,
                       ip_address, user_agent, cree_le
                FROM {schema_name}.emargement_rdv
                WHERE rdv_id = :rdv_id
            """)
            emargement_result = session.exec(emargement_query.bindparams(rdv_id=rdv_id)).first()
            if emargement_result:
                emargement = emargement_result
        
        # Si pas d'émargement et que la table existe, en créer un via INSERT SQL
        if not emargement and table_exists_anywhere("emargement_rdv", session, schema_name):
            now = datetime.now(timezone.utc)
            insert_query = text(f"""
                INSERT INTO {schema_name}.emargement_rdv 
                (rdv_id, type_signataire, candidat_id, cree_le)
                VALUES (:rdv_id, :type_signataire, :candidat_id, :cree_le)
                RETURNING id, rdv_id, type_signataire, signataire_id, candidat_id, 
                          signature_conseiller, signature_candidat, 
                          date_signature_conseiller, date_signature_candidat,
                          ip_address, user_agent, cree_le
            """)
            emargement = session.exec(insert_query.bindparams(
                rdv_id=rdv_id,
                type_signataire="candidat",
                candidat_id=candidat_result.id,
                cree_le=now
            )).first()
            session.commit()
        
        # Convertir les résultats en objets simples pour le template
        rdv = type('RendezVous', (), {
            'id': rdv_result.id,
            'candidat_id': rdv_result.candidat_id,
            'conseiller_id': rdv_result.conseiller_id,
            'type_rdv': rdv_result.type_rdv,
            'statut': rdv_result.statut,
            'debut': rdv_result.debut,
            'fin': rdv_result.fin,
            'lieu': rdv_result.lieu,
            'notes': rdv_result.notes,
            'meet_link': rdv_result.meet_link
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_result.id,
            'nom': candidat_result.nom,
            'prenom': candidat_result.prenom,
            'email': candidat_result.email,
            'statut': candidat_result.statut
        })()
        
        logger.info(f"✅ Page émargement candidat chargée pour RDV {rdv_id}")
        
        # Créer un utilisateur fictif pour le template (candidat non connecté)
        utilisateur_fictif = type('User', (), {
            'id': candidat.id,
            'email': candidat.email,
            'nom_complet': f"{candidat.prenom} {candidat.nom}",
            'role': 'candidat'
        })()
        
        return templates.TemplateResponse("pages/emargement/candidat.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "emargement": emargement,
            "token": token,
            "utilisateur": utilisateur_fictif,
            "settings": settings
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans page_emargement_candidat: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans page_emargement_candidat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/emargement/{rdv_id}/signer", name="signer_emargement_conseiller", response_class=JSONResponse)
async def signer_emargement_conseiller(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Enregistrer la signature d'émargement du conseiller"""
    logger.info(f"✍️ Signature émargement conseiller - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Lire le body JSON
        signature_data = await request.json()
        
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [signer_emargement_conseiller] Schéma configuré: {schema_name}")
        
        # Vérifier que la table existe dans le schéma
        if not table_exists_anywhere("emargement_rdv", session, schema_name):
            raise HTTPException(status_code=404, detail="Émargement non disponible dans ce programme")
        
        # Récupérer l'émargement via requête SQL directe
        emargement_query = text(f"""
            SELECT id, rdv_id, type_signataire, signataire_id, candidat_id, 
                   signature_conseiller, signature_candidat, 
                   date_signature_conseiller, date_signature_candidat,
                   ip_address, user_agent, cree_le
            FROM {schema_name}.emargement_rdv
            WHERE rdv_id = :rdv_id
        """)
        emargement = session.exec(emargement_query.bindparams(rdv_id=rdv_id)).first()
        
        if not emargement:
            raise HTTPException(status_code=404, detail="Émargement non trouvé")
        
        signature_content = signature_data.get("signature")  # Base64 de la signature
        
        if not signature_content:
            raise HTTPException(status_code=400, detail="Signature manquante")
        
        # Extraire les données base64 (enlever le préfixe "data:image/png;base64,")
        if "," in signature_content:
            signature_base64 = signature_content.split(",")[1]
        else:
            signature_base64 = signature_content
        
        # Décoder le base64
        try:
            signature_bytes = base64.b64decode(signature_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Format de signature invalide: {str(e)}")
        
        # Créer le dossier de sauvegarde des signatures en utilisant path_config
        signatures_dir = path_config.UPLOAD_DIR / "signatures" / schema_name.lower()
        signatures_dir.mkdir(parents=True, exist_ok=True)
        
        # Générer un nom de fichier unique
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"signature_conseiller_rdv{rdv_id}_{timestamp}.png"
        file_path = signatures_dir / filename
        
        # Sauvegarder l'image
        with open(file_path, "wb") as f:
            f.write(signature_bytes)
        
        # Générer l'URL relative pour la base de données (utiliser le chemin de montage)
        signature_url = f"{path_config.get_mount_path('media')}/signatures/{schema_name.lower()}/{filename}"
        
        # Mettre à jour l'émargement via UPDATE SQL
        now = datetime.now(timezone.utc)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        update_query = text(f"""
            UPDATE {schema_name}.emargement_rdv
            SET signature_conseiller = :signature_url,
                date_signature_conseiller = :date_signature,
                signataire_id = :signataire_id,
                ip_address = :ip_address,
                user_agent = :user_agent
            WHERE id = :emargement_id
        """)
        session.exec(update_query.bindparams(
            signature_url=signature_url,
            date_signature=now,
            signataire_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            emargement_id=emargement.id
        ))
        session.commit()
        
        logger.info(f"✅ Signature conseiller enregistrée pour RDV {rdv_id}")
        
        return JSONResponse({
            "status": "success",
            "message": "Signature conseiller enregistrée avec succès",
            "date_signature": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans signer_emargement_conseiller: {e.detail}")
        return JSONResponse(
            {"status": "error", "message": e.detail},
            status_code=e.status_code
        )
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans signer_emargement_conseiller: {str(e)}", exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Erreur interne: {str(e)}"},
            status_code=500
        )


@router.post("/emargement/{rdv_id}/candidat/signer", name="signer_emargement_candidat", response_class=JSONResponse)
async def signer_emargement_candidat(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Enregistrer la signature d'émargement du candidat (sans authentification)"""
    logger.info(f"✍️ Signature émargement candidat - RDV ID: {rdv_id}")
    
    try:
        # Lire le body JSON
        signature_data = await request.json()
        
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [signer_emargement_candidat] Schéma configuré: {schema_name}")
        
        # Vérifier que les tables existent dans le schéma
        if not table_exists_anywhere("emargement_rdv", session, schema_name):
            raise HTTPException(status_code=404, detail="Émargement non disponible dans ce programme")
        
        if not table_exists_anywhere("rendez_vous", session, schema_name):
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer l'émargement via requête SQL directe
        emargement_query = text(f"""
            SELECT id, rdv_id, type_signataire, signataire_id, candidat_id, 
                   signature_conseiller, signature_candidat, 
                   date_signature_conseiller, date_signature_candidat,
                   ip_address, user_agent, cree_le
            FROM {schema_name}.emargement_rdv
            WHERE rdv_id = :rdv_id
        """)
        emargement = session.exec(emargement_query.bindparams(rdv_id=rdv_id)).first()
        
        if not emargement:
            raise HTTPException(status_code=404, detail="Émargement non trouvé")
        
        # Récupérer le RDV pour obtenir le candidat_id
        rdv_query = text(f"SELECT candidat_id FROM {schema_name}.rendez_vous WHERE id = :rdv_id")
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        signature_content = signature_data.get("signature")  # Base64 de la signature
        
        if not signature_content:
            raise HTTPException(status_code=400, detail="Signature manquante")
        
        # Extraire les données base64 (enlever le préfixe "data:image/png;base64,")
        if "," in signature_content:
            signature_base64 = signature_content.split(",")[1]
        else:
            signature_base64 = signature_content
        
        # Décoder le base64
        try:
            signature_bytes = base64.b64decode(signature_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Format de signature invalide: {str(e)}")
        
        # Créer le dossier de sauvegarde des signatures en utilisant path_config
        signatures_dir = path_config.UPLOAD_DIR / "signatures" / schema_name.lower()
        signatures_dir.mkdir(parents=True, exist_ok=True)
        
        # Générer un nom de fichier unique
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"signature_candidat_rdv{rdv_id}_{timestamp}.png"
        file_path = signatures_dir / filename
        
        # Sauvegarder l'image
        with open(file_path, "wb") as f:
            f.write(signature_bytes)
        
        # Générer l'URL relative pour la base de données (utiliser le chemin de montage)
        signature_url = f"{path_config.get_mount_path('media')}/signatures/{schema_name.lower()}/{filename}"
        
        # Mettre à jour l'émargement via UPDATE SQL
        now = datetime.now(timezone.utc)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
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
            candidat_id=rdv_result.candidat_id,
            ip_address=ip_address,
            user_agent=user_agent,
            emargement_id=emargement.id
        ))
        session.commit()
        
        logger.info(f"✅ Signature candidat enregistrée pour RDV {rdv_id}")
        
        return JSONResponse({
            "status": "success",
            "message": "Signature candidat enregistrée avec succès",
            "date_signature": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans signer_emargement_candidat: {e.detail}")
        return JSONResponse(
            {"status": "error", "message": e.detail},
            status_code=e.status_code
        )
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans signer_emargement_candidat: {str(e)}", exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Erreur interne: {str(e)}"},
            status_code=500
        )


@router.get("/emargement/{rdv_id}/statut", name="get_statut_emargement", response_class=JSONResponse)
async def get_statut_emargement(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Récupérer le statut de l'émargement d'un RDV"""
    logger.info(f"📊 Statut émargement - RDV ID: {rdv_id}, URL: {request.url}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [get_statut_emargement] Schéma configuré: {schema_name}")
        
        # Vérifier que la table existe dans le schéma
        if not table_exists_anywhere("emargement_rdv", session, schema_name):
            logger.debug(f"🔍 [get_statut_emargement] Table emargement_rdv n'existe pas dans schéma {schema_name}")
            return JSONResponse({
                "status": "not_found",
                "conseiller_signe": False,
                "candidat_signe": False,
                "peut_commencer": False
            })
        
        # Récupérer l'émargement via requête SQL directe
        emargement_query = text(f"""
            SELECT signature_conseiller, signature_candidat, 
                   date_signature_conseiller, date_signature_candidat
            FROM {schema_name}.emargement_rdv
            WHERE rdv_id = :rdv_id
        """)
        emargement = session.exec(emargement_query.bindparams(rdv_id=rdv_id)).first()
        
        if not emargement:
            logger.debug(f"🔍 [get_statut_emargement] Aucun émargement trouvé pour RDV {rdv_id} dans schéma {schema_name}")
            return JSONResponse({
                "status": "not_found",
                "conseiller_signe": False,
                "candidat_signe": False,
                "peut_commencer": False
            })
        
        conseiller_signe = bool(emargement.signature_conseiller and emargement.date_signature_conseiller)
        candidat_signe = bool(emargement.signature_candidat and emargement.date_signature_candidat)
        peut_commencer = conseiller_signe and candidat_signe
        
        return JSONResponse({
            "status": "found",
            "conseiller_signe": conseiller_signe,
            "candidat_signe": candidat_signe,
            "peut_commencer": peut_commencer,
            "date_signature_conseiller": emargement.date_signature_conseiller.isoformat() if emargement.date_signature_conseiller else None,
            "date_signature_candidat": emargement.date_signature_candidat.isoformat() if emargement.date_signature_candidat else None
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans get_statut_emargement: {e.detail}")
        return JSONResponse(
            {"status": "error", "message": e.detail},
            status_code=e.status_code
        )
    except Exception as e:
        logger.error(f"💥 Erreur dans get_statut_emargement: {str(e)}", exc_info=True)
        return JSONResponse(
            {"status": "error", "message": f"Erreur interne: {str(e)}"},
            status_code=500
        )


@router.post("/emargement/{rdv_id}/envoyer-lien-candidat", name="envoyer_lien_emargement_candidat")
async def envoyer_lien_emargement_candidat(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Envoyer le lien d'émargement au candidat par email"""
    logger.info(f"📧 Envoi lien émargement candidat - RDV ID: {rdv_id}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Vérifier que la table existe dans le schéma
        if not table_exists_anywhere("rendez_vous", session, schema_name):
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Convertir en objets simples
        rdv = type('RendezVous', (), {
            'id': rdv_result.id,
            'candidat_id': rdv_result.candidat_id,
            'conseiller_id': rdv_result.conseiller_id,
            'type_rdv': rdv_result.type_rdv,
            'statut': rdv_result.statut,
            'debut': rdv_result.debut,
            'fin': rdv_result.fin,
            'lieu': rdv_result.lieu,
            'notes': rdv_result.notes,
            'meet_link': rdv_result.meet_link
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_result.id,
            'nom': candidat_result.nom,
            'prenom': candidat_result.prenom,
            'email': candidat_result.email
        })()
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation")
        
        # Générer un token simple (en production, utiliser un token sécurisé)
        token = f"emargement_{rdv_id}_{candidat.id}"
        lien_emargement = f"/emargement/{rdv_id}/candidat/{token}"
        
        # Envoyer l'email
        success = EmailUtils.send_emargement_invitation(
            to_email=candidat.email,
            candidat_nom=candidat.nom,
            candidat_prenom=candidat.prenom,
            rdv_id=rdv_id,
            rdv_date=rdv.debut.strftime("%d/%m/%Y à %H:%M") if rdv.debut else "Non définie",
            rdv_type=rdv.type_rdv,
            lien_emargement=lien_emargement
        )
        
        if success:
            logger.info(f"✅ Email émargement envoyé à {candidat.email}")
            return {
                "status": "success",
                "message": "Lien d'émargement envoyé au candidat par email"
            }
        else:
            logger.error(f"❌ Échec envoi email émargement à {candidat.email}")
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de l'email")
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans envoyer_lien_emargement_candidat: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans envoyer_lien_emargement_candidat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


# ============================================================================
# ROUTES VIDÉO (fusionnées depuis video_router.py)
# ============================================================================

def generate_meet_link(type_rdv: Optional[TypeRDV] = None):
    """
    Génère un nom de salle unique pour Jitsi Meet selon le type de rendez-vous.
    Le format est compatible avec l'ancien format Google Meet pour la rétrocompatibilité.
    """
    # Générer un identifiant unique
    unique_id = ''.join(secrets.choice(ALPHABET) for _ in range(10))
    
    # Préfixe selon le type de rendez-vous
    if type_rdv:
        # Utiliser le type de RDV comme préfixe (ex: entretien-abc123, suivi-xyz789)
        prefix = type_rdv.value.lower().replace('_', '-')
        room_name = f"{prefix}-{unique_id}"
    else:
        # Par défaut, utiliser "rdv" si le type n'est pas spécifié
        room_name = f"rdv-{unique_id}"
    
    return room_name

@router.get("/video-rdv/{rdv_id}/commencer", response_class=HTMLResponse, name="video_rdv_start")
def commencer_rdv_video(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page pour commencer un RDV vidéo"""
    logger.info(f"🎥 Début RDV vidéo - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [commencer_rdv_video] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists_rdv = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists_rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv_result.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Générer ou récupérer le lien Meet via UPDATE SQL
        meet_link = rdv_result.meet_link
        if not meet_link:
            meet_link = generate_meet_link(type_rdv=TypeRDV(rdv_result.type_rdv))
            update_query = text(f"""
                UPDATE {schema_name}.rendez_vous
                SET meet_link = :meet_link
                WHERE id = :rdv_id
            """)
            session.exec(update_query.bindparams(meet_link=meet_link, rdv_id=rdv_id))
            session.commit()
        
        # Convertir en objets simples
        rdv = type('RendezVous', (), {
            'id': rdv_result.id,
            'candidat_id': rdv_result.candidat_id,
            'conseiller_id': rdv_result.conseiller_id,
            'type_rdv': rdv_result.type_rdv,
            'statut': rdv_result.statut,
            'debut': rdv_result.debut,
            'fin': rdv_result.fin,
            'lieu': rdv_result.lieu,
            'notes': rdv_result.notes,
            'meet_link': meet_link
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_result.id,
            'nom': candidat_result.nom,
            'prenom': candidat_result.prenom,
            'email': candidat_result.email
        })()
        
        logger.info(f"✅ Page RDV vidéo chargée pour RDV {rdv_id}")
        
        # Récupérer le conseiller si assigné
        conseiller = None
        conseiller_nom = "Non assigné"
        if rdv.conseiller_id:
            conseiller = session.get(User, rdv.conseiller_id)
            if conseiller:
                conseiller_nom = conseiller.nom_complet or f"{conseiller.email}"
        
        # Extraire le nom de la salle depuis le meet_link
        # Le meet_link peut être soit un nom de salle (rdv-abc123) soit un lien complet
        if rdv.meet_link:
            # Si c'est un lien complet, extraire le nom de la salle
            if "/" in rdv.meet_link:
                room_name = rdv.meet_link.split("/")[-1]
            else:
                # Sinon, c'est déjà un nom de salle
                room_name = rdv.meet_link
        else:
            # Générer un nom de salle unique basé sur l'ID du RDV
            room_name = f"rdv-{rdv_id}-{''.join(secrets.choice(ALPHABET) for _ in range(6))}"
        
        # Déterminer si l'utilisateur est l'hôte (conseiller ou admin/coordinateur)
        is_host = current_user.role in ["administrateur", "coordinateur"] or (rdv.conseiller_id and rdv.conseiller_id == current_user.id)
        display_name = current_user.nom_complet or current_user.email
        
        # Récupérer le nom du programme depuis le schéma
        programme_nom = schema_name.upper() if schema_name and schema_name != 'public' else 'ACD'
        
        return templates.TemplateResponse("pages/rendez_vous/seance_jitsi.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "utilisateur": current_user,
            "app_name": APP_NAME,
            "meet_link": meet_link,
            "settings": settings,
            "room_name": room_name,
            "display_name": display_name,
            "is_host": is_host,
            "candidat_prenom": candidat.prenom or "",
            "candidat_nom": candidat.nom or "",
            "conseiller_nom": conseiller_nom,
            "programme_nom": programme_nom,
            "role": "moderator" if is_host else "participant"
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans commencer_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans commencer_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/video-rdv/{rdv_id}/rejoindre", response_class=HTMLResponse, name="video_rdv_join")
def rejoindre_rdv_video(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page pour rejoindre un RDV vidéo"""
    logger.info(f"🎥 Rejoindre RDV vidéo - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [rejoindre_rdv_video] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists_rdv = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists_rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Générer ou récupérer le lien Meet via UPDATE SQL
        meet_link = rdv_result.meet_link
        if not meet_link:
            meet_link = generate_meet_link(type_rdv=TypeRDV(rdv_result.type_rdv))
            update_query = text(f"""
                UPDATE {schema_name}.rendez_vous
                SET meet_link = :meet_link
                WHERE id = :rdv_id
            """)
            session.exec(update_query.bindparams(meet_link=meet_link, rdv_id=rdv_id))
            session.commit()
        
        # Convertir en objets simples
        rdv = type('RendezVous', (), {
            'id': rdv_result.id,
            'candidat_id': rdv_result.candidat_id,
            'conseiller_id': rdv_result.conseiller_id,
            'type_rdv': rdv_result.type_rdv,
            'statut': rdv_result.statut,
            'debut': rdv_result.debut,
            'fin': rdv_result.fin,
            'lieu': rdv_result.lieu,
            'notes': rdv_result.notes,
            'meet_link': meet_link
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_result.id,
            'nom': candidat_result.nom,
            'prenom': candidat_result.prenom,
            'email': candidat_result.email
        })()
        
        logger.info(f"✅ Page rejoindre RDV vidéo chargée pour RDV {rdv_id}")
        
        # Récupérer le conseiller si assigné
        conseiller_nom = "Non assigné"
        if rdv_result.conseiller_id:
            conseiller = session.get(User, rdv_result.conseiller_id)
            if conseiller:
                conseiller_nom = conseiller.nom_complet or f"{conseiller.email}"
        
        # Extraire le nom de la salle depuis le meet_link
        # Le meet_link peut être soit un nom de salle (rdv-abc123) soit un lien complet
        if meet_link:
            # Si c'est un lien complet, extraire le nom de la salle
            if "/" in meet_link:
                room_name = meet_link.split("/")[-1]
            else:
                # Sinon, c'est déjà un nom de salle
                room_name = meet_link
        else:
            # Générer un nom de salle unique basé sur l'ID du RDV
            room_name = f"rdv-{rdv_id}-{''.join(secrets.choice(ALPHABET) for _ in range(6))}"
        
        # Déterminer si l'utilisateur est l'hôte (conseiller ou admin/coordinateur)
        is_host = current_user.role in ["administrateur", "coordinateur"] or (rdv_result.conseiller_id and rdv_result.conseiller_id == current_user.id)
        display_name = current_user.nom_complet or current_user.email
        
        # Récupérer le nom du programme depuis le schéma
        programme_nom = schema_name.upper() if schema_name and schema_name != 'public' else 'ACD'
        
        return templates.TemplateResponse("pages/rendez_vous/seance_jitsi.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "utilisateur": current_user,
            "app_name": APP_NAME,
            "meet_link": meet_link,
            "settings": settings,
            "room_name": room_name,
            "display_name": display_name,
            "is_host": is_host,
            "candidat_prenom": candidat.prenom or "",
            "candidat_nom": candidat.nom or "",
            "conseiller_nom": conseiller_nom,
            "programme_nom": programme_nom,
            "role": "moderator" if is_host else "participant"
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans rejoindre_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans rejoindre_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/video-rdv/{rdv_id}/lien-candidat/{token}", response_class=HTMLResponse, name="video_rdv_candidate_link")
def lien_candidat_rdv_video(
    request: Request,
    rdv_id: int,
    token: str,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user_optional),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Page pour que le candidat rejoigne un RDV vidéo via un lien"""
    logger.info(f"🎥 Lien candidat RDV vidéo - RDV ID: {rdv_id}, Token: {token}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [lien_candidat_rdv_video] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists_rdv = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists_rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Générer ou récupérer le lien Meet via UPDATE SQL
        meet_link = rdv_result.meet_link
        if not meet_link:
            meet_link = generate_meet_link(type_rdv=TypeRDV(rdv_result.type_rdv))
            update_query = text(f"""
                UPDATE {schema_name}.rendez_vous
                SET meet_link = :meet_link
                WHERE id = :rdv_id
            """)
            session.exec(update_query.bindparams(meet_link=meet_link, rdv_id=rdv_id))
            session.commit()
        
        # Convertir en objets simples
        rdv = type('RendezVous', (), {
            'id': rdv_result.id,
            'candidat_id': rdv_result.candidat_id,
            'conseiller_id': rdv_result.conseiller_id,
            'type_rdv': rdv_result.type_rdv,
            'statut': rdv_result.statut,
            'debut': rdv_result.debut,
            'fin': rdv_result.fin,
            'lieu': rdv_result.lieu,
            'notes': rdv_result.notes,
            'meet_link': meet_link
        })()
        
        candidat = type('Candidat', (), {
            'id': candidat_result.id,
            'nom': candidat_result.nom,
            'prenom': candidat_result.prenom,
            'email': candidat_result.email
        })()
        
        logger.info(f"✅ Page lien candidat RDV vidéo chargée pour RDV {rdv_id}")
        
        # Récupérer le conseiller si assigné
        conseiller_nom = "Non assigné"
        if rdv_result.conseiller_id:
            conseiller = session.get(User, rdv_result.conseiller_id)
            if conseiller:
                conseiller_nom = conseiller.nom_complet or f"{conseiller.email}"
        
        # Extraire le nom de la salle depuis le meet_link
        # Le meet_link peut être soit un nom de salle (rdv-abc123) soit un lien complet
        if meet_link:
            # Si c'est un lien complet, extraire le nom de la salle
            if "/" in meet_link:
                room_name = meet_link.split("/")[-1]
            else:
                # Sinon, c'est déjà un nom de salle
                room_name = meet_link
        else:
            # Générer un nom de salle unique basé sur l'ID du RDV
            room_name = f"rdv-{rdv_id}-{''.join(secrets.choice(ALPHABET) for _ in range(6))}"
        
        # Pour le candidat, il n'est jamais hôte
        is_host = False
        display_name = f"{candidat_result.prenom or ''} {candidat_result.nom or ''}".strip() or candidat_result.email or "Candidat"
        
        # Récupérer le nom du programme depuis le schéma
        programme_nom = schema_name.upper() if schema_name and schema_name != 'public' else 'ACD'
        
        return templates.TemplateResponse("pages/rendez_vous/seance_jitsi.html", {
            "request": request,
            "rdv": rdv,
            "candidat": candidat,
            "utilisateur": current_user,
            "app_name": APP_NAME,
            "meet_link": meet_link,
            "settings": settings,
            "room_name": room_name,
            "display_name": display_name,
            "is_host": is_host,
            "candidat_prenom": candidat.prenom or "",
            "candidat_nom": candidat.nom or "",
            "conseiller_nom": conseiller_nom,
            "programme_nom": programme_nom,
            "role": "participant"
        })
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans lien_candidat_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans lien_candidat_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/terminer", name="terminer_rdv_video")
def terminer_rdv_video(
    request: Request,
    rdv_id: int,
    notes: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Terminer un RDV vidéo"""
    logger.info(f"🏁 Fin RDV vidéo - RDV ID: {rdv_id}, User: {current_user.email}")
    
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [terminer_rdv_video] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists_rdv = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists_rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Récupérer le RDV via requête SQL directe pour vérifier les permissions
        rdv_query = text(f"SELECT conseiller_id FROM {schema_name}.rendez_vous WHERE id = :rdv_id")
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if current_user.role not in ["administrateur", "coordinateur"] and rdv_result.conseiller_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation")
        
        # Mettre à jour le statut via UPDATE SQL
        now = datetime.now(timezone.utc)
        update_query = text(f"""
            UPDATE {schema_name}.rendez_vous
            SET statut = :statut, fin = :fin
        """)
        params = {"statut": StatutRDV.TERMINE.value, "fin": now, "rdv_id": rdv_id}
        if notes:
            update_query = text(f"""
                UPDATE {schema_name}.rendez_vous
                SET statut = :statut, fin = :fin, notes = :notes
                WHERE id = :rdv_id
            """)
            params["notes"] = notes
        else:
            update_query = text(f"""
                UPDATE {schema_name}.rendez_vous
                SET statut = :statut, fin = :fin
                WHERE id = :rdv_id
            """)
        session.exec(update_query.bindparams(**params))
        session.commit()
        
        logger.info(f"✅ RDV vidéo terminé pour RDV {rdv_id}")
        
        return {
            "status": "success",
            "message": "Rendez-vous vidéo terminé avec succès"
        }
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans terminer_rdv_video: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur inattendue dans terminer_rdv_video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/video-rdv/{rdv_id}/notes", name="recuperer_notes")
def recuperer_notes(
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupérer les notes d'un RDV vidéo"""
    try:
        rdv = session.get(RendezVous, rdv_id)
        if not rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        return {
            "notes": rdv.notes or ""
        }
        
    except Exception as e:
        logger.error(f"💥 Erreur dans recuperer_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/notes", name="sauvegarder_notes")
def sauvegarder_notes(
    request: Request,
    rdv_id: int,
    notes: str = Form(...),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Sauvegarder les notes d'un RDV vidéo"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        if settings.DEBUG:
            logger.debug(f"🔍 [sauvegarder_notes] Schéma configuré: {schema_name}")
        
        # Vérifier que la table rendez_vous existe dans le schéma
        table_exists_rdv = table_exists_anywhere("rendez_vous", session, schema_name)
        if not table_exists_rdv:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé dans ce programme")
        
        # Mettre à jour les notes via UPDATE SQL
        update_query = text(f"""
            UPDATE {schema_name}.rendez_vous
            SET notes = :notes
            WHERE id = :rdv_id
        """)
        session.exec(update_query.bindparams(notes=notes, rdv_id=rdv_id))
        session.commit()
        
        logger.info(f"✅ Notes sauvegardées pour RDV {rdv_id}")
        
        return {
            "status": "success",
            "message": "Notes sauvegardées avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Erreur dans sauvegarder_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/video-rdv/{rdv_id}/envoyer-invitation", name="envoyer_invitation_email")
def envoyer_invitation_email(
    request: Request,
    rdv_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Envoyer l'invitation vidéo par email avec lien Jitsi"""
    try:
        # Récupérer et configurer le schéma
        schema_name = get_schema_from_request(request) or 'acd'
        schema_routing_service.set_schema(schema_name)
        
        # Récupérer le RDV via requête SQL directe
        rdv_query = text(f"""
            SELECT id, candidat_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes, meet_link
            FROM {schema_name}.rendez_vous
            WHERE id = :rdv_id
        """)
        rdv_result = session.exec(rdv_query.bindparams(rdv_id=rdv_id)).first()
        if not rdv_result:
            raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
        
        # Vérifier les permissions
        if rdv_result.conseiller_id and rdv_result.conseiller_id != current_user.id and current_user.role not in ["administrateur", "coordinateur"]:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation d'envoyer cette invitation")
        
        # Récupérer le candidat via requête SQL directe
        candidat_query = text(f"""
            SELECT id, nom, prenom, email
            FROM {schema_name}.candidat
            WHERE id = :candidat_id
        """)
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=rdv_result.candidat_id)).first()
        if not candidat_result:
            raise HTTPException(status_code=404, detail="Candidat non trouvé")
        
        # Récupérer le conseiller si assigné
        conseiller_nom = "Conseiller non assigné"
        if rdv_result.conseiller_id:
            conseiller = session.get(User, rdv_result.conseiller_id)
            if conseiller:
                conseiller_nom = conseiller.nom_complet or f"{conseiller.email}"
        
        # Récupérer le nom du programme depuis le schéma
        programme_nom = schema_name.upper() if schema_name and schema_name != 'public' else 'ACD'
        
        # Envoyer l'email d'invitation avec le lien Jitsi
        rdv_date = rdv_result.debut.strftime("%d/%m/%Y à %H:%M") if rdv_result.debut else "Non définie"
        success = EmailUtils.send_video_invitation(
            to_email=candidat_result.email,
            candidat_nom=candidat_result.nom or "",
            candidat_prenom=candidat_result.prenom or "",
            rdv_id=rdv_id,
            rdv_date=rdv_date,
            candidat_id=candidat_result.id,
            programme_nom=programme_nom,
            conseiller_nom=conseiller_nom
        )
        
        if success:
            logger.info(f"✅ Invitation vidéo envoyée avec succès à {candidat_result.email} pour RDV {rdv_id}")
            return {
                "status": "success",
                "message": "Invitation vidéo envoyée avec succès au candidat"
            }
        else:
            logger.error(f"❌ Échec envoi invitation vidéo à {candidat_result.email} pour RDV {rdv_id}")
            raise HTTPException(status_code=500, detail="Erreur lors de l'envoi de l'email")
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException dans envoyer_invitation_email: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"💥 Erreur dans envoyer_invitation_email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/jitsi-proxy/{path:path}", name="jitsi_proxy")
async def jitsi_proxy(
    path: str,
    request: Request
):
    """
    Proxy pour servir les fichiers Jitsi depuis le même port que FastAPI.
    Évite les problèmes CORS entre localhost:8000 et localhost:8001.
    """
    try:
        # Construire l'URL Jitsi complète
        jitsi_url = settings.JITSI_URL_ACTIVE
        jitsi_domain = settings.JITSI_DOMAIN_ACTIVE
        target_url = f"{jitsi_url}/{path}"
        
        # Ajouter les query params si présents
        if request.query_params:
            query_string = str(request.query_params)
            target_url = f"{target_url}?{query_string}"
        
        logger.info(f"🔗 Proxy Jitsi - Tentative de connexion à: {target_url}")
        logger.info(f"🔗 Proxy Jitsi - Domaine configuré: {jitsi_domain}, URL active: {jitsi_url}")
        
        # Faire la requête vers Jitsi avec gestion d'erreur améliorée
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(target_url)
                
                # Vérifier le statut de la réponse
                if response.status_code >= 400:
                    logger.error(f"❌ Proxy Jitsi - Erreur HTTP {response.status_code} pour {target_url}")
                    logger.error(f"❌ Proxy Jitsi - Réponse: {response.text[:500]}")
                    raise HTTPException(
                        status_code=502, 
                        detail=f"Le serveur Jitsi a retourné une erreur {response.status_code}. Vérifiez que Jitsi est démarré et accessible à {jitsi_url}"
                    )
                
                # Déterminer le content-type
                content_type = response.headers.get("content-type", "application/javascript")
                
                logger.info(f"✅ Proxy Jitsi - Succès pour {path} (Content-Type: {content_type})")
                
                # Retourner la réponse avec les bons headers
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type=content_type,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "public, max-age=3600"
                    }
                )
            except httpx.ConnectError as e:
                logger.error(f"❌ Proxy Jitsi - Erreur de connexion: {str(e)}")
                logger.error(f"❌ Proxy Jitsi - Impossible de se connecter à {jitsi_url}")
                logger.error(f"❌ Proxy Jitsi - Vérifiez que le serveur Jitsi est démarré et accessible")
                raise HTTPException(
                    status_code=502, 
                    detail=f"Impossible de se connecter au serveur Jitsi à {jitsi_url}. Vérifiez que Jitsi est démarré et accessible."
                )
            except httpx.TimeoutException as e:
                logger.error(f"❌ Proxy Jitsi - Timeout: {str(e)}")
                raise HTTPException(
                    status_code=504, 
                    detail=f"Timeout lors de la connexion au serveur Jitsi ({jitsi_url}). Le serveur met trop de temps à répondre."
                )
            except httpx.HTTPError as e:
                logger.error(f"❌ Proxy Jitsi - Erreur HTTP: {str(e)}")
                raise HTTPException(
                    status_code=502, 
                    detail=f"Erreur HTTP lors de la connexion au serveur Jitsi: {str(e)}"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Proxy Jitsi - Erreur inattendue: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=502, 
            detail=f"Erreur lors du proxy vers Jitsi: {str(e)}. Vérifiez la configuration JITSI_URL_ACTIVE dans vos paramètres."
        )

