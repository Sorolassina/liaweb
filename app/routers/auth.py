"""
Router pour l'authentification et les utilisateurs
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from typing import List, Optional
from pathlib import Path
import os
from datetime import datetime, timezone

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


# ===== ROUTES PROFIL UTILISATEUR =====

@router.get("/profil", response_class=HTMLResponse, name="profil")
async def profil_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Page de profil utilisateur - permet à l'utilisateur de voir et modifier ses informations"""
    return templates.TemplateResponse("profil.html", {
        "request": request,
        "utilisateur": current_user,
        "current_user": current_user,
        "timestamp": int(datetime.now(timezone.utc).timestamp())
    })


@router.post("/profil/update", name="profil_update")
async def profil_update(
    request: Request,
    nom_complet: str = Form(...),
    email: str = Form(...),
    telephone: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Met à jour les informations du profil utilisateur"""
    try:
        # Vérifier si l'email est déjà utilisé par un autre utilisateur
        existing_user = session.exec(
            select(User).where(User.email == email, User.id != current_user.id)
        ).first()
        
        if existing_user:
            return RedirectResponse(
                url=f"/auth/profil?error=email_exists", 
                status_code=303
            )
        
        # Mettre à jour les informations
        current_user.nom_complet = nom_complet
        current_user.email = email
        current_user.telephone = telephone
        current_user.modifie_le = datetime.now(timezone.utc)
        
        session.commit()
        
        return RedirectResponse(
            url=f"/auth/profil?success=profile_updated", 
            status_code=303
        )
        
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour du profil: {e}")
        return RedirectResponse(
            url=f"/auth/profil?error=update_failed", 
            status_code=303
        )


@router.post("/profil/change-password", name="profil_change_password")
async def profil_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Change le mot de passe de l'utilisateur"""
    try:
        # Vérifier que les nouveaux mots de passe correspondent
        if new_password != confirm_password:
            return RedirectResponse(
                url=f"/auth/profil?error=password_mismatch", 
                status_code=303
            )
        
        # Vérifier l'ancien mot de passe
        if not authenticate_user(session, current_user.email, current_password):
            return RedirectResponse(
                url=f"/auth/profil?error=wrong_current_password", 
                status_code=303
            )
        
        # Mettre à jour le mot de passe
        from app_lia_web.core.security import get_password_hash
        current_user.password_hash = get_password_hash(new_password)
        current_user.modifie_le = datetime.now(timezone.utc)
        
        session.commit()
        
        return RedirectResponse(
            url=f"/auth/profil?success=password_changed", 
            status_code=303
        )
        
    except Exception as e:
        print(f"❌ Erreur lors du changement de mot de passe: {e}")
        return RedirectResponse(
            url=f"/auth/profil?error=password_change_failed", 
            status_code=303
        )


@router.post("/profil/photo", name="profil_photo")
async def profil_photo(
    request: Request,
    photo_profil: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Change la photo de profil de l'utilisateur"""
    try:
        # Vérifier le type de fichier
        if not photo_profil.content_type or not photo_profil.content_type.startswith('image/'):
            return RedirectResponse(
                url=f"/auth/profil?error=invalid_file_type", 
                status_code=303
            )
        
        # Sauvegarder l'ancienne photo pour la supprimer après
        old_photo_path = current_user.photo_profil
        
        # Générer un nom de fichier unique
        ext = os.path.splitext(photo_profil.filename)[1].lower() or ".jpg"
        filename = f"user_{current_user.id}_profile{ext}"
        
        # Sauvegarder le fichier
        from app_lia_web.core.path_config import path_config
        upload_dir = path_config.UPLOAD_DIR / "profiles"
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / filename
        
        with open(file_path, "wb") as buffer:
            content = await photo_profil.read()
            buffer.write(content)
        
        # Mettre à jour le chemin dans la base
        relative_path = f"/profiles/{filename}"
        current_user.photo_profil = relative_path
        current_user.modifie_le = datetime.now(timezone.utc)
        
        session.commit()
        
        # Supprimer l'ancienne photo si elle existe
        if old_photo_path:
            try:
                old_path = Path("." + old_photo_path)
                if old_path.exists():
                    old_path.unlink()
            except Exception as e:
                print(f"⚠️ Impossible de supprimer l'ancienne photo: {e}")
        
        return RedirectResponse(
            url=f"/auth/profil?success=photo_updated", 
            status_code=303
        )
        
    except Exception as e:
        print(f"❌ Erreur lors du changement de photo: {e}")
        return RedirectResponse(
            url=f"/auth/profil?error=photo_update_failed", 
            status_code=303
        )
