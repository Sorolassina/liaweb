"""
Utilitaires pour la gestion des adresses décomposées
"""

import json
from typing import Dict, Optional, Tuple

def get_adresse_decomposee_from_json(donnees_brutes_json: str, type_adresse: str = "personnelle") -> Dict[str, Optional[str]]:
    """
    Récupère les champs d'adresse décomposés depuis le JSON des données brutes
    
    Args:
        donnees_brutes_json: JSON string contenant les données de préinscription
        type_adresse: "personnelle" ou "entreprise"
    
    Returns:
        Dict avec les champs décomposés: numero, rue, code_postal, ville
    """
    try:
        data = json.loads(donnees_brutes_json) if donnees_brutes_json else {}
    except (json.JSONDecodeError, TypeError):
        data = {}
    
    prefix = "personnel" if type_adresse == "personnelle" else "entreprise"
    
    return {
        "numero": data.get(f"numero_{prefix}"),
        "rue": data.get(f"rue_{prefix}"),
        "code_postal": data.get(f"code_postal_{prefix}"),
        "ville": data.get(f"ville_{prefix}")
    }

def get_adresse_consolidee_from_decomposee(numero: Optional[str], rue: Optional[str], 
                                         code_postal: Optional[str], ville: Optional[str]) -> str:
    """
    Consolide les champs d'adresse décomposés en une adresse complète
    
    Args:
        numero: Numéro de rue
        rue: Nom de la rue
        code_postal: Code postal
        ville: Nom de la ville
    
    Returns:
        Adresse consolidée
    """
    parts = [numero, rue, code_postal, ville]
    return ", ".join(filter(None, parts))

def validate_adresse_decomposee(numero: Optional[str], rue: Optional[str], 
                               code_postal: Optional[str], ville: Optional[str]) -> Tuple[bool, str]:
    """
    Valide qu'une adresse décomposée est complète
    
    Args:
        numero: Numéro de rue
        rue: Nom de la rue
        code_postal: Code postal
        ville: Nom de la ville
    
    Returns:
        Tuple (is_valid, error_message)
    """
    if not all([numero, rue, code_postal, ville]):
        return False, "Tous les champs d'adresse sont obligatoires (numéro, rue, code postal, ville)"
    
    if not code_postal.isdigit() or len(code_postal) != 5:
        return False, "Le code postal doit contenir exactement 5 chiffres"
    
    return True, ""

def format_adresse_for_display(adresse_consolidee: str, numero: Optional[str] = None, 
                              rue: Optional[str] = None, code_postal: Optional[str] = None, 
                              ville: Optional[str] = None) -> str:
    """
    Formate une adresse pour l'affichage, en privilégiant les champs décomposés si disponibles
    
    Args:
        adresse_consolidee: Adresse consolidée
        numero, rue, code_postal, ville: Champs décomposés optionnels
    
    Returns:
        Adresse formatée pour l'affichage
    """
    if all([numero, rue, code_postal, ville]):
        return f"{numero} {rue}, {code_postal} {ville}"
    return adresse_consolidee or "Adresse non renseignée"
