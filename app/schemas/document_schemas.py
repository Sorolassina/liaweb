"""
Schémas Pydantic pour les documents
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app_lia_web.app.models.enums import TypeDocument


class DocumentBase(BaseModel):
    candidat_id: int
    type_document: TypeDocument
    titre: Optional[str] = None


class DocumentCreate(DocumentBase):
    nom_fichier: str
    chemin_fichier: str
    mimetype: Optional[str] = None
    taille_octets: Optional[int] = None


class DocumentResponse(DocumentBase):
    id: int
    nom_fichier: str
    chemin_fichier: str
    mimetype: Optional[str] = None
    taille_octets: Optional[int] = None
    depose_par_id: Optional[int] = None
    depose_le: datetime

    class Config:
        from_attributes = True
