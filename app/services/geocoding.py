# app/services/geocoding.py
from __future__ import annotations
import httpx, asyncio, urllib.parse
from typing import Optional, Tuple
from sqlmodel import Session, select
from app_lia_web.app.models.base import Entreprise

BAN_ENDPOINT = "https://api-adresse.data.gouv.fr/search/"  # search?q=... (voir doc) :contentReference[oaicite:2]{index=2}

async def geocode_one(address: str, timeout: float = 6.0) -> Optional[Tuple[float, float]]:
    if not address:
        return None
    q = urllib.parse.urlencode({"q": address, "limit": 1})
    url = f"{BAN_ENDPOINT}?{q}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url)
        r.raise_for_status()
        js = r.json()
        feats = js.get("features") or []
        if not feats:
            return None
        coords = feats[0]["geometry"]["coordinates"]  # [lng, lat]
        return (float(coords[1]), float(coords[0])) #lat, lng

async def enrich_missing_latlng(session: Session, batch_limit: int = 200):
    """Géocode les entreprises sans lat/lng (adresse + territoire)."""
    rows = session.exec(
        select(Entreprise).where(
            (Entreprise.lat.is_(None)) | (Entreprise.lng.is_(None))
        ).limit(batch_limit)
    ).all()
    tasks = []
    for e in rows:
        # On concatène adresse + territoire si disponible
        addr = " ".join([p for p in [e.adresse, e.territoire] if p])
        tasks.append(geocode_one(addr))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    updated = 0
    for e, res in zip(rows, results):
        if isinstance(res, Exception) or res is None:
            continue
        lat, lng = res
        e.lat, e.lng = lat, lng
        updated += 1
    if updated:
        session.commit()
    return updated
