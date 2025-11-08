from datetime import datetime, date

def parse_date_flexible(date_str):
    """
    Parse une date au format ISO (YYYY-MM-DD), français (DD-MM-YYYY ou DD/MM/YYYY), ou lève une erreur sinon.
    """
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Format de date non reconnu : {date_str}")

def format_milliers(val):
    """
    Formate un nombre en milliers avec espace comme séparateur et virgule pour les décimales.
    Ex : 12345.67 -> '12 345,67'
    """
    try:
        return f"{float(val):,.2f}".replace(",", " ").replace(".", ",")
    except Exception:
        return str(val)

def diff_date_humaine(date_debut, date_fin=None, unite='auto'):
    """
    Calcule la différence entre deux dates et renvoie la valeur en années, mois ou jours.
    - date_debut : str ou date/datetime
    - date_fin : str ou date/datetime (défaut : aujourd'hui)
    - unite : 'auto', 'jours', 'mois', 'annees'
    Retourne une chaîne comme '2 ans', '5 mois', '12 jours'.
    """
    if date_fin is None:
        date_fin = date.today()
    if isinstance(date_debut, str):
        date_debut = parse_date_flexible(date_debut)
    if isinstance(date_fin, str):
        date_fin = parse_date_flexible(date_fin)
    delta = date_fin - date_debut
    jours = delta.days
    mois = jours // 30
    annees = mois // 12
    if unite == 'jours':
        return f"{jours} jour{'s' if jours > 1 else ''}"
    elif unite == 'mois':
        return f"{mois} mois"
    elif unite == 'annees':
        return f"{annees} an{'s' if annees > 1 else ''}"
    # auto
    if jours < 31:
        return f"{jours} jour{'s' if jours > 1 else ''}"
    if mois < 12:
        return f"{mois} mois"
    return f"{annees} an{'s' if annees > 1 else ''}" 