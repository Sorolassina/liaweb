"""
Schémas Pydantic pour l'authentification
"""
from pydantic import BaseModel, EmailStr
from .user_schemas import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    mot_de_passe: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
