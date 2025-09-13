from fastapi import APIRouter, Request, HTTPException
import time

from app_lia_web.app.schemas.ACD.schema_qpv import Adresse
from app_lia_web.app.services.ACD.service_qpv import verif_qpv

router = APIRouter()

@router.post("inscriptions/qpv-check")
async def check_qpv(address: Adresse, request: Request):
    """
    Vérifier le statut QPV d'une adresse
    
    Args:
        address: Objet Adresse contenant l'adresse à vérifier
        request: Requête FastAPI pour récupérer l'URL de base
        
    Returns:
        dict: Résultat de la vérification QPV avec cartes et images
    """
    start_time = time.time()
    data = address.model_dump()

    print("✅ [ROUTE QPV] Adresse validée:", address)

    # Vérification des données d'entrée
    if not data.get("address") or not data["address"].strip():
        return {
            "address": "Adresse vide",
            "nom_qp": "Aucun QPV",
            "distance_m": "N/A",
            "carte": "",
            "image_url": "",
            "image_encoded": ""
        }
    
    # Validation basique du format d'adresse
    adresse = data["address"].strip()
    if len(adresse) < 5 or adresse.isdigit():
        return {
            "address": "Format d'adresse invalide",
            "nom_qp": "Aucun QPV", 
            "distance_m": "N/A",
            "carte": "",
            "image_url": "",
            "image_encoded": ""
        }

    try:
        # Appel du service de vérification QPV
        result = await verif_qpv(data, request)
        
        duration = round(time.time() - start_time, 2)
        print(f"✅ [ROUTE QPV] Vérification terminée en {duration}s")
        
        return result
        
    except Exception as e:
        print(f"❌ [ROUTE QPV] Erreur lors de la vérification: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la vérification QPV: {str(e)}"
        )
