"""
Routes de gestion des schémas par programme
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session
from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user
from app_lia_web.app.routers.ACD.admin import admin_required
from app_lia_web.app.services.program_schema_service import ProgramSchemaService
from app_lia_web.app.models.base import Programme, User
from app_lia_web.app.templates import templates
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/admin/schemas", response_class=HTMLResponse)
def admin_schemas(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page d'administration des schémas"""
    admin_required(current_user)
    
    schema_service = ProgramSchemaService(session)
    
    # Récupérer tous les programmes
    programmes = session.exec(
        session.query(Programme).where(Programme.actif == True)
    ).all()
    
    # Récupérer les statistiques de chaque schéma
    schema_stats = {}
    for programme in programmes:
        stats = schema_service.get_schema_stats(programme.code)
        schema_stats[programme.code] = stats
    
    return templates.TemplateResponse("admin/schemas.html", {
        "request": request,
        "programmes": programmes,
        "schema_stats": schema_stats,
        "utilisateur": current_user
    })

@router.post("/admin/schemas/create/{program_code}")
def create_program_schema(
    program_code: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crée un schéma pour un programme"""
    admin_required(current_user)
    
    schema_service = ProgramSchemaService(session)
    
    try:
        success = schema_service.create_program_schema(program_code)
        if success:
            return {"status": "success", "message": f"Schéma {program_code} créé avec succès"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la création du schéma")
            
    except Exception as e:
        logger.error(f"Erreur lors de la création du schéma {program_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/schemas/migrate/{program_code}")
def migrate_program_data(
    program_code: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Migre les données existantes vers le schéma du programme"""
    admin_required(current_user)
    
    schema_service = ProgramSchemaService(session)
    
    try:
        success = schema_service.migrate_existing_data(program_code)
        if success:
            return {"status": "success", "message": f"Données migrées pour {program_code}"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la migration")
            
    except Exception as e:
        logger.error(f"Erreur lors de la migration des données pour {program_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/schemas/backup/{program_code}")
def backup_program_schema(
    program_code: str,
    backup_path: str = "/tmp/backups",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Sauvegarde un schéma en fichiers Excel"""
    admin_required(current_user)
    
    schema_service = ProgramSchemaService(session)
    
    try:
        success = schema_service.backup_schema_to_excel(program_code, backup_path)
        if success:
            return {"status": "success", "message": f"Schéma {program_code} sauvegardé dans {backup_path}"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde")
            
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du schéma {program_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/schemas/drop/{program_code}")
def drop_program_schema(
    program_code: str,
    backup_data: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprime un schéma de programme"""
    admin_required(current_user)
    
    schema_service = ProgramSchemaService(session)
    
    try:
        # Vérifier que le programme existe
        programme = session.get(Programme, program_code)
        if not programme:
            raise HTTPException(status_code=404, detail="Programme non trouvé")
        
        success = schema_service.drop_program_schema(program_code, backup_data)
        if success:
            return {"status": "success", "message": f"Schéma {program_code} supprimé avec succès"}
        else:
            raise HTTPException(status_code=500, detail="Erreur lors de la suppression")
            
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du schéma {program_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/schemas/stats/{program_code}")
def get_schema_stats(
    program_code: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Retourne les statistiques d'un schéma"""
    admin_required(current_user)
    
    schema_service = ProgramSchemaService(session)
    
    try:
        stats = schema_service.get_schema_stats(program_code)
        tables = schema_service.get_schema_tables(program_code)
        
        return {
            "program_code": program_code,
            "tables": tables,
            "stats": stats,
            "total_records": sum(stats.values())
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats du schéma {program_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
