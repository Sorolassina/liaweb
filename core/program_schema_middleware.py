"""
Middleware pour le routage automatique vers les schémas par programme
Ce fichier est maintenant un simple wrapper qui importe depuis program_schema_integration
"""
from app_lia_web.core.program_schema_integration import ProgramSchemaMiddleware

# Exporter la classe pour la compatibilité
__all__ = ['ProgramSchemaMiddleware']
