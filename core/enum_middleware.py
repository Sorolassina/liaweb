# app/core/enum_middleware.py
"""
Middleware de validation des enums au démarrage de l'application
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session
from ..core.database import get_session
from ..services.enum_validation import EnumValidationService
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EnumValidationMiddleware:
    """Middleware pour valider les enums au démarrage"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.validation_result: Dict[str, Any] = {}
        self._validate_on_startup()
    
    def _validate_on_startup(self):
        """Valide les enums au démarrage de l'application"""
        try:
            logger.info("🔍 Début de la validation des enums...")
            
            # Obtenir une session de base de données
            session = next(get_session())
            
            # Créer le service de validation
            validation_service = EnumValidationService(session)
            
            # Exécuter la validation
            self.validation_result = validation_service.validate_all_enums()
            
            # Log des résultats
            if self.validation_result["status"] == "success":
                logger.info("✅ Validation des enums réussie")
            else:
                logger.warning("⚠️ Problèmes détectés dans les enums:")
                for validation_name, validation_data in self.validation_result["validations"].items():
                    if validation_data.get("has_errors", False):
                        invalid_values = validation_data.get("invalid_values", [])
                        logger.warning(f"  - {validation_name}: {invalid_values}")
            
            # Log des recommandations
            for recommendation in self.validation_result.get("recommendations", []):
                logger.info(f"💡 Recommandation: {recommendation}")
            
            session.close()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la validation des enums: {e}")
            self.validation_result = {
                "status": "error",
                "error": str(e)
            }
    
    def get_validation_status(self) -> Dict[str, Any]:
        """Retourne le statut de validation"""
        return self.validation_result
    
    def is_validation_ok(self) -> bool:
        """Vérifie si la validation est OK"""
        return self.validation_result.get("status") == "success"

# Fonction pour ajouter le middleware à l'application
def add_enum_validation_middleware(app: FastAPI):
    """Ajoute le middleware de validation des enums"""
    
    # Créer le middleware
    enum_middleware = EnumValidationMiddleware(app)
    
    # Ajouter une route pour consulter le statut
    @app.get("/admin/enum-validation-status")
    async def get_enum_validation_status():
        """Endpoint pour consulter le statut de validation des enums"""
        return enum_middleware.get_validation_status()
    
    # Ajouter une route pour forcer une nouvelle validation
    @app.post("/admin/enum-validation-refresh")
    async def refresh_enum_validation():
        """Endpoint pour forcer une nouvelle validation des enums"""
        try:
            session = next(get_session())
            validation_service = EnumValidationService(session)
            result = validation_service.validate_all_enums()
            session.close()
            return result
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    return enum_middleware
