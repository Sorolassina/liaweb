"""
Router pour l'authentification et les utilisateurs
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from typing import List

from app_lia_web.core.database import get_session
from app_lia_web.core.security import get_current_user, create_access_token, authenticate_user
from app_lia_web.app.models.base import User
from app_lia_web.app.models.enums import UserRole
from app_lia_web.app.schemas import UserCreate, UserUpdate, UserResponse, LoginRequest, TokenResponse
from app_lia_web.app.services import UserService
from app_lia_web.app.templates import templates
from app_lia_web.core.config import settings
from datetime import datetime
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi import Depends

router = APIRouter()


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crée un nouvel utilisateur (admin seulement)"""
    if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    # Vérifier si l'email existe déjà
    existing_user = UserService.get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet email existe déjà"
        )
    
    user = UserService.create_user(session, user_data)
    return UserResponse.from_orm(user)


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Récupère les informations de l'utilisateur connecté"""
    return UserResponse.from_orm(current_user)


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    role: str = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des utilisateurs (admin seulement)"""
    if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    if role:
        users = UserService.get_users_by_role(session, role)
    else:
        users = session.exec(select(User)).all()
    
    return [UserResponse.from_orm(user) for user in users]


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour un utilisateur"""
    # Vérifier les permissions
    if current_user.id != user_id and current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    user = UserService.update_user(session, user_id, user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return UserResponse.from_orm(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprime un utilisateur (admin seulement)"""
    if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    # Empêcher la suppression de son propre compte
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte"
        )
    
    success = UserService.delete_user(session, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return {"message": "Utilisateur supprimé avec succès"}


