# app/services/eligibilite.py
from datetime import date
from typing import Optional, Tuple

# On consomme TA fonction (exemple: import depuis app.domain.rules)
# from app.domain.rules import is_qpv_address
def is_qpv_address(addr: Optional[str]) -> bool:
    # Placeholder si tu veux tester sans ta lib:
    return False

def entreprise_age_annees(date_creation: Optional[date]) -> Optional[float]:
    if not date_creation:
        return None
    today = date.today()
    delta = today.year - date_creation.year - ((today.month, today.day) < (date_creation.month, date_creation.day))
    return float(delta)

def parse_ca_intervalle(ca_string: Optional[str]) -> Optional[dict]:
    """
    Parse un intervalle de CA (ex: "10 000 - 50 000 €") et retourne les bornes min/max.
    Retourne None si impossible à parser.
    """
    if not ca_string or not ca_string.strip():
        return None
    
    try:
        # Nettoyer la chaîne (enlever €, espaces, etc.)
        ca_clean = ca_string.replace('€', '').replace(',', '').strip()
        
        # Chercher un intervalle (format: "min - max")
        if ' - ' in ca_clean:
            parts = ca_clean.split(' - ')
            if len(parts) == 2:
                min_val = float(parts[0].strip().replace(' ', ''))
                max_val = float(parts[1].strip().replace(' ', ''))
                return {"min": min_val, "max": max_val, "type": "intervalle"}
        
        # Chercher un seul nombre
        elif ca_clean.replace('.', '').replace('-', '').isdigit():
            val = float(ca_clean.replace(' ', ''))
            return {"min": val, "max": val, "type": "valeur_unique"}
        
        return None
    except (ValueError, AttributeError):
        return None

def compare_ca_intervalles(ca_declare: Optional[str], ca_min_prog: Optional[float], ca_max_prog: Optional[float]) -> bool:
    """
    Compare l'intervalle de CA déclaré avec les seuils du programme.
    Retourne True si l'intervalle déclaré est compatible avec les critères du programme.
    """
    if not ca_declare:
        return True  # Pas de CA déclaré = pas de contrainte
    
    ca_parsed = parse_ca_intervalle(ca_declare)
    if not ca_parsed:
        return True  # Impossible à parser = pas de contrainte
    
    ca_declare_min = ca_parsed["min"]
    ca_declare_max = ca_parsed["max"]
    
    # Si le programme n'a pas de seuils, tout est accepté
    if ca_min_prog is None and ca_max_prog is None:
        return True
    
    # Vérifier la compatibilité des intervalles
    # L'intervalle déclaré doit chevaucher avec l'intervalle accepté par le programme
    
    # Cas 1: Seuil minimum seulement
    if ca_min_prog is not None and ca_max_prog is None:
        return ca_declare_max >= ca_min_prog  # Le max déclaré doit être >= seuil min
    
    # Cas 2: Seuil maximum seulement  
    if ca_min_prog is None and ca_max_prog is not None:
        return ca_declare_min <= ca_max_prog  # Le min déclaré doit être <= seuil max
    
    # Cas 3: Intervalle complet (min et max)
    if ca_min_prog is not None and ca_max_prog is not None:
        # Il faut qu'il y ait un chevauchement entre les intervalles
        return ca_declare_min <= ca_max_prog and ca_declare_max >= ca_min_prog
    
    return True

def evaluate_eligibilite(
    adresse_perso: Optional[str],
    adresse_entreprise: Optional[str],
    chiffre_affaires: Optional[str],  # Changé de float à str pour les intervalles
    anciennete_annees: Optional[float],
    ca_min: Optional[float], ca_max: Optional[float],
    anciennete_min_annees: Optional[int]
) -> Tuple[str, dict]:
    """
    Retourne (verdict, details) avec verdict in {"ok","attention","ko"}.
    La règle illustrative :
      - QPV OK si l'une des deux adresses est QPV
      - CA dans [min, max] si min/max définis
      - Ancienneté >= seuil si défini
      - "ok" si tout est bon, "attention" si partiel, "ko" sinon
    """
    qpv_ok = is_qpv_address(adresse_perso) or is_qpv_address(adresse_entreprise)

    # Comparer les intervalles de CA
    ca_ok = compare_ca_intervalles(chiffre_affaires, ca_min, ca_max)
    
    # Parser le CA pour l'affichage (garder l'intervalle original)
    ca_parsed = parse_ca_intervalle(chiffre_affaires)

    anc_ok = True
    if anciennete_min_annees is not None:
        anc_ok = (anciennete_annees or 0) >= anciennete_min_annees

    score = sum([1 if qpv_ok else 0, 1 if ca_ok else 0, 1 if anc_ok else 0])
    verdict = "ok" if score == 3 else ("attention" if score == 2 else "ko")

    details = {
        "qpv_ok": qpv_ok,
        "ca_ok": ca_ok,
        "anciennete_ok": anc_ok,
        "ca_decl": chiffre_affaires,  # Intervalle original
        "ca_parsed": ca_parsed,  # Données parsées (min, max, type)
        "anciennete_annees": anciennete_annees
    }
    return verdict, details
