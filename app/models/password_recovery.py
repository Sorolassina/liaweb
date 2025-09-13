"""
Modèles pour le système de récupération de mot de passe
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
import secrets
import string


class PasswordRecoveryCode(SQLModel, table=True):
    """Code de récupération de mot de passe"""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    code: str = Field(max_length=6)  # Code à 6 chiffres
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    used_at: Optional[datetime] = None
    ip_address: Optional[str] = None  # Pour la sécurité
    
    @staticmethod
    def generate_code() -> str:
        """Génère un code de 6 chiffres"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    @staticmethod
    def create_recovery_code(email: str, ip_address: Optional[str] = None) -> "PasswordRecoveryCode":
        """Crée un nouveau code de récupération"""
        code = PasswordRecoveryCode.generate_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)  # 15 minutes de validité
        
        return PasswordRecoveryCode(
            email=email,
            code=code,
            expires_at=expires_at,
            ip_address=ip_address
        )
    
    def is_valid(self) -> bool:
        """Vérifie si le code est encore valide"""
        return (
            not self.used and 
            datetime.now(timezone.utc) < self.expires_at
        )
    
    def mark_as_used(self):
        """Marque le code comme utilisé"""
        self.used = True
        self.used_at = datetime.now(timezone.utc)
