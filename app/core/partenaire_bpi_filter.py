# app/core/partenaire_bpi_filter.py
"""
Helper pour filtrer les données par partenaire_bpi dans les requêtes SQL.
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import text
from sqlmodel import Session
from ..models.base import User


def add_partenaire_bpi_filter(
    user: Optional[User],
    where_conditions: List[str],
    params: Dict[str, Any],
    table_alias: str = ""
) -> None:
    """
    Ajoute une condition WHERE pour filtrer par partenaire_bpi si l'utilisateur est un partenaire BPI.
    
    Args:
        user: L'utilisateur connecté
        where_conditions: Liste des conditions WHERE (sera modifiée en place)
        params: Dictionnaire des paramètres SQL (sera modifié en place)
        table_alias: Alias de la table (ex: "c." pour candidat, "e." pour entreprise, etc.)
                    Si vide, on suppose que la colonne est directement accessible
    """
    if not user:
        return
    
    partenaire_bpi = getattr(user, 'partenaire_bpi', None)
    if not partenaire_bpi:
        return
    
    # Si l'utilisateur a un partenaire_bpi, filtrer les données
    prefix = f"{table_alias}." if table_alias else ""
    where_conditions.append(f"{prefix}partenaire_bpi = :partenaire_bpi")
    params["partenaire_bpi"] = partenaire_bpi


def add_partenaire_bpi_filter_to_query(
    user: Optional[User],
    base_query: str,
    where_clause: str = "",
    params: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Ajoute une condition WHERE pour filtrer par partenaire_bpi à une requête SQL existante.
    
    Args:
        user: L'utilisateur connecté
        base_query: La requête SQL de base
        where_clause: La clause WHERE existante (peut être vide)
        params: Dictionnaire des paramètres SQL existants
    
    Returns:
        Tuple (query_with_filter, updated_params)
    """
    if params is None:
        params = {}
    
    partenaire_bpi = getattr(user, 'partenaire_bpi', None) if user else None
    if not partenaire_bpi:
        return base_query, params
    
    # Ajouter la condition WHERE
    if where_clause:
        where_clause += " AND partenaire_bpi = :partenaire_bpi"
    else:
        where_clause = "WHERE partenaire_bpi = :partenaire_bpi"
    
    params["partenaire_bpi"] = partenaire_bpi
    
    # Insérer la clause WHERE dans la requête (avant ORDER BY, LIMIT, etc.)
    query_lower = base_query.lower()
    order_by_pos = query_lower.find(" order by ")
    limit_pos = query_lower.find(" limit ")
    group_by_pos = query_lower.find(" group by ")
    
    # Trouver la position d'insertion
    insert_pos = len(base_query)
    for pos in [order_by_pos, limit_pos, group_by_pos]:
        if pos != -1 and pos < insert_pos:
            insert_pos = pos
    
    # Insérer la clause WHERE
    if insert_pos < len(base_query):
        base_query = base_query[:insert_pos] + " " + where_clause + " " + base_query[insert_pos:]
    else:
        base_query += " " + where_clause
    
    return base_query, params


def should_filter_by_partenaire_bpi(user: Optional[User]) -> bool:
    """
    Détermine si les données doivent être filtrées par partenaire_bpi.
    
    Args:
        user: L'utilisateur connecté
    
    Returns:
        True si le filtrage doit être appliqué, False sinon
    """
    if not user:
        return False
    
    partenaire_bpi = getattr(user, 'partenaire_bpi', None)
    return partenaire_bpi is not None and partenaire_bpi != ""


def add_partenaire_bpi_to_union_query(
    user: Optional[User],
    union_query_part: str,
    table_alias: str = ""
) -> str:
    """
    Ajoute une condition WHERE pour filtrer par partenaire_bpi dans une partie d'une requête UNION ALL.
    
    Args:
        user: L'utilisateur connecté
        union_query_part: La partie de la requête UNION (sans le SELECT initial)
        table_alias: Alias de la table (ex: "c." pour candidat, "e." pour entreprise, etc.)
                    Si vide, on suppose que la colonne est directement accessible
    
    Returns:
        La requête modifiée avec le filtre partenaire_bpi si nécessaire
    """
    if not should_filter_by_partenaire_bpi(user):
        return union_query_part
    
    partenaire_bpi = getattr(user, 'partenaire_bpi', None)
    if not partenaire_bpi:
        return union_query_part
    
    prefix = f"{table_alias}." if table_alias else ""
    condition = f"{prefix}partenaire_bpi = '{partenaire_bpi}'"
    
    # Ajouter la condition à la clause WHERE existante ou créer une nouvelle clause WHERE
    if "WHERE" in union_query_part.upper():
        # Remplacer le WHERE existant pour ajouter la condition
        union_query_part = union_query_part.replace("WHERE ", f"WHERE {condition} AND ", 1)
    else:
        # Ajouter une nouvelle clause WHERE avant ORDER BY, GROUP BY, ou à la fin
        where_pos = len(union_query_part)
        for keyword in ["ORDER BY", "GROUP BY", "LIMIT"]:
            pos = union_query_part.upper().find(keyword)
            if pos != -1 and pos < where_pos:
                where_pos = pos
        
        union_query_part = union_query_part[:where_pos].rstrip() + f" WHERE {condition} " + union_query_part[where_pos:].lstrip()
    
    return union_query_part

