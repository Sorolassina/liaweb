"""
Schémas Pydantic pour les statistiques
"""
from pydantic import BaseModel


class StatistiquesResponse(BaseModel):
    candidats_preinscrits: int
    candidats_inscrits: int
    programmes_actifs: int
    jurys_planifies: int
    decisions_en_attente: int
