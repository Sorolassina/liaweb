"""
Exemple d'utilisation du système de schémas consolidé
"""
from fastapi import APIRouter, Request, Depends
from sqlmodel import Session
from app_lia_web.core.database import get_session
from app_lia_web.core.program_schema_integration import (
    SchemaRoutingService, 
    get_schema_aware_session,
    create_schema_aware_query,
    get_current_schema
)
from app_lia_web.app.models.base import Candidat

router = APIRouter()

# Exemple 1: Route simple avec routage automatique
@router.get("/candidats")
async def get_candidats(
    request: Request,
    routing_service: SchemaRoutingService = Depends(get_schema_aware_session)
):
    """Récupère tous les candidats du schéma actuel"""
    
    # Méthode 1: Requête SQL directe avec routage automatique
    sql = "SELECT * FROM candidats ORDER BY nom, prenom"
    result = routing_service.execute_in_schema(sql)
    candidats_data = result.fetchall()
    
    # Méthode 2: Requête construite avec filtres
    sql_with_filters = create_schema_aware_query(
        routing_service, 
        Candidat, 
        filters={"statut": "EN_COURS"}
    )
    result_filtered = routing_service.execute_in_schema(sql_with_filters)
    candidats_filtered = result_filtered.fetchall()
    
    return {
        "candidats": candidats_data,
        "candidats_en_cours": candidats_filtered,
        "schema_actuel": routing_service.get_schema()
    }

# Exemple 2: Route avec paramètres de schéma explicites
@router.get("/candidats/{candidat_id}")
async def get_candidat(
    candidat_id: int,
    request: Request,
    routing_service: SchemaRoutingService = Depends(get_schema_aware_session)
):
    """Récupère un candidat spécifique du schéma actuel"""
    
    sql = "SELECT * FROM candidats WHERE id = :candidat_id"
    result = routing_service.execute_in_schema(sql, {"candidat_id": candidat_id})
    candidat = result.fetchone()
    
    if not candidat:
        return {"error": "Candidat non trouvé"}
    
    return {
        "candidat": candidat,
        "schema_actuel": routing_service.get_schema()
    }

# Exemple 3: Route avec création de données
@router.post("/candidats")
async def create_candidat(
    request: Request,
    routing_service: SchemaRoutingService = Depends(get_schema_aware_session)
):
    """Crée un nouveau candidat dans le schéma actuel"""
    
    # Récupérer les données du formulaire
    form_data = await request.form()
    
    sql = """
        INSERT INTO candidats (nom, prenom, email, telephone, statut)
        VALUES (:nom, :prenom, :email, :telephone, :statut)
        RETURNING id
    """
    
    params = {
        "nom": form_data.get("nom"),
        "prenom": form_data.get("prenom"),
        "email": form_data.get("email"),
        "telephone": form_data.get("telephone"),
        "statut": "EN_ATTENTE"
    }
    
    result = routing_service.execute_in_schema(sql, params)
    candidat_id = result.fetchone()[0]
    
    return {
        "message": "Candidat créé avec succès",
        "candidat_id": candidat_id,
        "schema_actuel": routing_service.get_schema()
    }

# Exemple 4: Route avec jointures entre schémas
@router.get("/candidats-with-programme")
async def get_candidats_with_programme(
    request: Request,
    routing_service: SchemaRoutingService = Depends(get_schema_aware_session)
):
    """Récupère les candidats avec les informations du programme (jointure entre schémas)"""
    
    sql = """
        SELECT 
            c.id, c.nom, c.prenom, c.email, c.statut,
            p.nom as programme_nom, p.code as programme_code
        FROM candidats c
        JOIN preinscriptions pr ON pr.candidat_id = c.id
        JOIN public.programmes p ON p.id = pr.programme_id
        ORDER BY c.nom, c.prenom
    """
    
    result = routing_service.execute_in_schema(sql)
    candidats_with_programme = result.fetchall()
    
    return {
        "candidats_with_programme": candidats_with_programme,
        "schema_actuel": routing_service.get_schema()
    }

# Exemple 5: Route avec gestion d'erreur et fallback
@router.get("/candidats-stats")
async def get_candidats_stats(
    request: Request,
    routing_service: SchemaRoutingService = Depends(get_schema_aware_session)
):
    """Récupère les statistiques des candidats du schéma actuel"""
    
    try:
        # Statistiques par statut
        sql_stats = """
            SELECT 
                statut,
                COUNT(*) as count
            FROM candidats
            GROUP BY statut
            ORDER BY count DESC
        """
        
        result = routing_service.execute_in_schema(sql_stats)
        stats_by_status = result.fetchall()
        
        # Total des candidats
        sql_total = "SELECT COUNT(*) as total FROM candidats"
        result_total = routing_service.execute_in_schema(sql_total)
        total_candidats = result_total.fetchone()[0]
        
        return {
            "total_candidats": total_candidats,
            "stats_by_status": stats_by_status,
            "schema_actuel": routing_service.get_schema()
        }
        
    except Exception as e:
        return {
            "error": f"Erreur lors de la récupération des statistiques: {str(e)}",
            "schema_actuel": routing_service.get_schema()
        }

# Exemple 6: Route avec schéma explicite
@router.get("/candidats-from-schema/{schema_name}")
async def get_candidats_from_specific_schema(
    schema_name: str,
    request: Request,
    session: Session = Depends(get_session)
):
    """Récupère les candidats d'un schéma spécifique"""
    
    routing_service = SchemaRoutingService(session)
    routing_service.set_schema(schema_name)
    
    sql = "SELECT * FROM candidats ORDER BY nom, prenom"
    result = routing_service.execute_in_schema(sql)
    candidats = result.fetchall()
    
    return {
        "candidats": candidats,
        "schema_utilise": schema_name
    }
