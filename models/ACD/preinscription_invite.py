from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlmodel import SQLModel, Field

class PreinscriptionInvite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    email: str = Field(index=True)
    programme_id: int = Field(index=True)
    message: Optional[str] = None
    expire_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))  # 30 jours au lieu de 14
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    utilise: bool = Field(default=False)