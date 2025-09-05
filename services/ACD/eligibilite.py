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

def evaluate_eligibilite(
    adresse_perso: Optional[str],
    adresse_entreprise: Optional[str],
    chiffre_affaires: Optional[float],
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

    ca_ok = True
    if ca_min is not None and (chiffre_affaires or 0) < ca_min:
        ca_ok = False
    if ca_max is not None and chiffre_affaires is not None and chiffre_affaires > ca_max:
        ca_ok = False

    anc_ok = True
    if anciennete_min_annees is not None:
        anc_ok = (anciennete_annees or 0) >= anciennete_min_annees

    score = sum([1 if qpv_ok else 0, 1 if ca_ok else 0, 1 if anc_ok else 0])
    verdict = "ok" if score == 3 else ("attention" if score == 2 else "ko")

    details = {
        "qpv_ok": qpv_ok,
        "ca_ok": ca_ok,
        "anciennete_ok": anc_ok,
        "ca_decl": chiffre_affaires,
        "anciennete_annees": anciennete_annees
    }
    return verdict, details
