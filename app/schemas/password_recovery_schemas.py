"""
Schémas pour le système de récupération de mot de passe
"""
import sys
import os
# Ajouter le répertoire parent au path pour les imports
#sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional


class PasswordRecoveryRequest(BaseModel):
    """Demande de récupération de mot de passe"""
    email: EmailStr = Field(..., description="Email de l'utilisateur")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "utilisateur@example.com"
            }
        }


class PasswordRecoveryVerify(BaseModel):
    """Vérification du code de récupération"""
    email: EmailStr = Field(..., description="Email de l'utilisateur")
    code: str = Field(..., min_length=6, max_length=6, description="Code de récupération à 6 chiffres")
    
    @validator('code')
    def validate_code(cls, v):
        if not v.isdigit():
            raise ValueError('Le code doit contenir uniquement des chiffres')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "utilisateur@example.com",
                "code": "123456"
            }
        }


class PasswordReset(BaseModel):
    """Réinitialisation du mot de passe"""
    email: EmailStr = Field(..., description="Email de l'utilisateur")
    code: str = Field(..., min_length=6, max_length=6, description="Code de récupération à 6 chiffres")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe (minimum 8 caractères)")
    confirm_password: str = Field(..., description="Confirmation du nouveau mot de passe")
    
    @validator('code')
    def validate_code(cls, v):
        if not v.isdigit():
            raise ValueError('Le code doit contenir uniquement des chiffres')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Les mots de passe ne correspondent pas')
        return v
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        
        # Vérifier qu'il y a au moins une majuscule, une minuscule et un chiffre
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule, une minuscule et un chiffre')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "utilisateur@example.com",
                "code": "123456",
                "new_password": "NouveauMotDePasse123",
                "confirm_password": "NouveauMotDePasse123"
            }
        }


class PasswordRecoveryResponse(BaseModel):
    """Réponse pour les opérations de récupération"""
    success: bool = Field(..., description="Indique si l'opération a réussi")
    message: str = Field(..., description="Message de retour")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Code de récupération envoyé par email"
            }
        }
