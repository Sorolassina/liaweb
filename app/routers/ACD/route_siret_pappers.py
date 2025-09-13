from fastapi import APIRouter, Request, HTTPException
import time

from app_lia_web.app.schemas.ACD.schema_siret import SiretRequest
from app_lia_web.app.services.ACD.service_siret_pappers import get_entreprise_process

router = APIRouter()

@router.post("inscriptions/siret-check")
async def check_siret(siret_request: SiretRequest, request: Request):
    """
    Vérifier les informations d'une entreprise via son SIRET/SIREN
    
    Args:
        siret_request: Objet SiretRequest contenant le numéro SIRET/SIREN
        request: Requête FastAPI pour récupérer l'URL de base
        
    Returns:
        dict: Informations de l'entreprise avec données CSV
    """
    print(f"🚀 [ROUTE SIRET] Début du traitement")
    print(f"📝 [ROUTE SIRET] SIRET reçu: {siret_request.numero_siret}")
    
    start_time = time.time()
    data = siret_request.model_dump()
    
    # Validation du format SIRET/SIREN
    numero_siret = data.get("numero_siret", "").strip()
    print(f"🔍 [ROUTE SIRET] Validation format: {numero_siret}")
    
    if not numero_siret or not numero_siret.isdigit():
        print("❌ [ROUTE SIRET] Format SIRET invalide")
        raise HTTPException(
            status_code=400,
            detail="Le numéro SIRET/SIREN doit contenir uniquement des chiffres"
        )
    
    if len(numero_siret) not in [9, 14]:
        print("❌ [ROUTE SIRET] Longueur SIRET invalide")
        raise HTTPException(
            status_code=400,
            detail="Le numéro doit faire 9 chiffres (SIREN) ou 14 chiffres (SIRET)"
        )
    
    # Extraction du SIREN (9 premiers chiffres)
    siren = numero_siret[:9]
    print(f"🔢 [ROUTE SIRET] SIREN extrait: {siren}")

    try:
        # Appel du service Pappers
        result = await get_entreprise_process(siren, request)
        
        duration = round(time.time() - start_time, 2)
        print(f"✅ [ROUTE SIRET] Traitement terminé en {duration}s")
        
        return result
        
    except HTTPException:
        # Re-lever les HTTPException du service
        raise
    except Exception as e:
        print(f"❌ [ROUTE SIRET] Erreur inattendue: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la vérification SIRET: {str(e)}"
        )
    