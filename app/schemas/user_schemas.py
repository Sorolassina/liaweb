"""
Schémas Pydantic pour les utilisateurs
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app_lia_web.app.models.enums import UserRole, TypeUtilisateur


class UserBase(BaseModel):
    email: EmailStr
    nom_complet: str
    telephone: Optional[str] = None
    role: str  # Utilise la valeur string de l'enum UserRole
    type_utilisateur: TypeUtilisateur = TypeUtilisateur.INTERNE


class UserCreate(UserBase):
    mot_de_passe: str = Field(..., min_length=8, description="Mot de passe d'au moins 8 caractères")


class UserUpdate(BaseModel):
    nom_complet: Optional[str] = None
    telephone: Optional[str] = None
    actif: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    actif: bool
    derniere_connexion: Optional[datetime] = None
    cree_le: datetime

    class Config:
        from_attributes = True
