from pydantic import BaseModel, Field
from typing import Optional


class QPVResponse(BaseModel):
    """
    Modèle de réponse pour la vérification QPV
    """
    address: str = Field(
        ...,
        description="Adresse analysée",
        example="10 Rue de la Paix, 75001 Paris"
    )
    
    nom_qp: str = Field(
        ...,
        description="Nom du quartier prioritaire ou statut",
        example="QPV: Quartier de la Paix"
    )
    
    distance_m: int = Field(
        ...,
        description="Distance en mètres par rapport au QPV le plus proche",
        example=0
    )
    
    carte: str = Field(
        ...,
        description="URL de la carte interactive",
        example="https://example.com/static/maps/map_10_Rue_de_la_Paix_75001_Paris.html"
    )
    
    image_url: str = Field(
        ...,
        description="URL de l'image de la carte",
        example="https://example.com/static/images/map_10_Rue_de_la_Paix_75001_Paris.png"
    )
    
    image_encoded: str = Field(
        ...,
        description="Image encodée en base64",
        example="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    )
    
    etat_qpv: Optional[str] = Field(
        None,
        description="État QPV (QPV, QPV limit, ou hors QPV)",
        example="QPV"
    )
    
    latitude: Optional[float] = Field(
        None,
        description="Latitude de l'adresse",
        example=48.8566
    )
    
    longitude: Optional[float] = Field(
        None,
        description="Longitude de l'adresse",
        example=2.3522
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "address": "10 Rue de la Paix, 75001 Paris",
                "nom_qp": "QPV: Quartier de la Paix",
                "distance_m": 0,
                "carte": "https://example.com/static/maps/map_10_Rue_de_la_Paix_75001_Paris.html",
                "image_url": "https://example.com/static/images/map_10_Rue_de_la_Paix_75001_Paris.png",
                "image_encoded": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                "etat_qpv": "QPV",
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        }


class QPVErrorResponse(BaseModel):
    """
    Modèle de réponse d'erreur pour la vérification QPV
    """
    error: str = Field(
        ...,
        description="Message d'erreur",
        example="Aucune coordonnée GPS trouvée pour cette adresse"
    )
    
    address: Optional[str] = Field(
        None,
        description="Adresse qui a causé l'erreur",
        example="Adresse invalide"
    )
    
    code: Optional[str] = Field(
        None,
        description="Code d'erreur",
        example="INVALID_ADDRESS"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Aucune coordonnée GPS trouvée pour cette adresse",
                "address": "Adresse invalide",
                "code": "INVALID_ADDRESS"
            }
        }
    