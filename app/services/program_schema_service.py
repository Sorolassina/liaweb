"""
Service de gestion des schémas par programme
Ce fichier est maintenant un simple wrapper qui importe depuis program_schema_integration
"""
from ..core.program_schema_integration import ProgramSchemaService

# Exporter la classe pour la compatibilité
__all__ = ['ProgramSchemaService']
