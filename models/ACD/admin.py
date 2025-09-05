from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class AppSetting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    value: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))