from datetime import datetime, date, timezone
from typing import Union, Optional

def parse_date_string(date_str: str) -> datetime:
    """
    Parse une chaîne de date dans différents formats.
    
    Formats supportés:
    - ISO: "2025-06-24T10:00:00" ou "2025-06-24"
    - Français: "24/06/2025" ou "24/06/2025 10:00"
    - Anglais: "06/24/2025" ou "06/24/2025 10:00"
    
    Args:
        date_str: Chaîne de date à parser
        
    Returns:
        datetime object
        
    Raises:
        ValueError: Si le format n'est pas reconnu
    """
    if not date_str:
        raise ValueError("La chaîne de date ne peut pas être vide")
    
    print(f"\n🔍 Parsing de la date: {date_str}")
    
    # Essayer le format ISO d'abord
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        print(f"✅ Format ISO détecté: {dt}")
        return dt
    except ValueError:
        pass
    
    # Essayer le format français DD/MM/YYYY
    try:
        if ' ' in date_str:
            # Avec heure: "24/06/2025 10:00"
            date_part, time_part = date_str.split(' ', 1)
            day, month, year = map(int, date_part.split('/'))
            hour, minute = map(int, time_part.split(':'))
            dt = datetime(year, month, day, hour, minute)
        else:
            # Sans heure: "24/06/2025"
            day, month, year = map(int, date_str.split('/'))
            dt = datetime(year, month, day)
        print(f"✅ Format français détecté: {dt}")
        return dt
    except (ValueError, IndexError):
        pass
    
    # Essayer le format anglais MM/DD/YYYY
    try:
        if ' ' in date_str:
            # Avec heure: "06/24/2025 10:00"
            date_part, time_part = date_str.split(' ', 1)
            month, day, year = map(int, date_part.split('/'))
            hour, minute = map(int, time_part.split(':'))
            dt = datetime(year, month, day, hour, minute)
        else:
            # Sans heure: "06/24/2025"
            month, day, year = map(int, date_str.split('/'))
            dt = datetime(year, month, day)
        print(f"✅ Format anglais détecté: {dt}")
        return dt
    except (ValueError, IndexError):
        pass
    
    # Si aucun format n'est reconnu
    raise ValueError(f"Format de date non reconnu: {date_str}. Formats supportés: ISO (2025-06-24), Français (24/06/2025), Anglais (06/24/2025)")

async def ensure_utc(dt: Optional[Union[datetime, date]]) -> Optional[datetime]:
    """
    Convertit une date ou datetime en datetime UTC.
    Si c'est une date simple, la convertit en datetime à minuit UTC.
    
    Args:
        dt: Date ou datetime à convertir, peut être None
        
    Returns:
        datetime en UTC ou None si dt est None
    """
    if dt is None:
        return None
        
    print(f"\n📅 Conversion de la date: {dt}")
    print(f"  - Type: {type(dt)}")
    
    # Si c'est une date simple (sans heure)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        print("  - Conversion d'une date simple en datetime UTC")
        # Créer un datetime à minuit UTC
        dt = datetime.combine(dt, datetime.min.time(), tzinfo=timezone.utc)
        print(f"  - Résultat: {dt} (UTC)")
        return dt
        
    # Si c'est déjà un datetime
    if isinstance(dt, datetime):
        print(f"  - TZ info: {dt.tzinfo}")
        
        # Si pas de fuseau horaire, supposer UTC
        if dt.tzinfo is None:
            print("  - Pas de fuseau horaire, conversion en UTC")
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Si déjà en UTC, retourner tel quel
            if dt.tzinfo == timezone.utc:
                print("  - Déjà en UTC")
                return dt
            # Sinon convertir en UTC
            print(f"  - Conversion de {dt.tzinfo} vers UTC")
            dt = dt.astimezone(timezone.utc)
            
        print(f"  - Résultat: {dt} (UTC)")
        return dt