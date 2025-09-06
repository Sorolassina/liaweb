# app/core/permissions.py
from functools import wraps
from typing import Callable, Any
from fastapi import HTTPException, Request
from sqlmodel import Session

from ..models.base import User
from ..models.ACD.permissions import TypeRessource, NiveauPermission
from ..services.ACD.permissions import PermissionService
from ..core.database import get_session

def require_permission(resource: TypeRessource, permission_level: NiveauPermission):
    """
    Décorateur pour vérifier les permissions d'un utilisateur
    
    Usage:
    @require_permission(TypeRessource.UTILISATEURS, NiveauPermission.ECRITURE)
    def create_user(...):
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extraire la session et l'utilisateur des arguments
            session: Session = None
            current_user: User = None
            
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                elif isinstance(arg, User):
                    current_user = arg
            
            for key, value in kwargs.items():
                if isinstance(value, Session):
                    session = value
                elif isinstance(value, User):
                    current_user = value
            
            if not session or not current_user:
                raise HTTPException(status_code=500, detail="Session ou utilisateur non trouvé")
            
            # Vérifier les permissions
            permission_service = PermissionService(session)
            if not permission_service.has_permission(current_user, resource, permission_level):
                raise HTTPException(
                    status_code=403, 
                    detail=f"Permission insuffisante. Requis: {permission_level.value} sur {resource.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def check_permission(user: User, resource: TypeRessource, permission_level: NiveauPermission, session: Session) -> bool:
    """
    Fonction utilitaire pour vérifier une permission spécifique
    """
    permission_service = PermissionService(session)
    return permission_service.has_permission(user, resource, permission_level)

def get_user_permissions(user: User, session: Session) -> dict:
    """
    Récupère toutes les permissions d'un utilisateur
    """
    permission_service = PermissionService(session)
    return permission_service.get_user_permissions(user)
