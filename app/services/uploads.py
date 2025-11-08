# app/services/uploads.py
from fastapi import UploadFile, HTTPException
from ..core.config import settings

def _file_size(file: UploadFile) -> int:
    """Retourne la taille du fichier UploadFile en octets (en lisant le buffer spooled)."""
    # UploadFile.file est un SpooledTemporaryFile; on mesure sans perdre le curseur
    pos = file.file.tell()
    file.file.seek(0, 2)  # fin
    size = file.file.tell()
    file.file.seek(pos, 0)
    return size

def validate_upload(
    file: UploadFile,
    allowed_mime_types: tuple[str, ...],
    max_mb: int | None = None,
    field_name: str = "file"
) -> None:
    if not file or not getattr(file, "filename", ""):
        raise HTTPException(status_code=400, detail=f"{field_name}: fichier manquant")

    ctype = (file.content_type or "").lower()
    if allowed_mime_types and ctype not in allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name}: type '{ctype}' non autorisé. Autorisés: {', '.join(allowed_mime_types)}"
        )

    if max_mb:
        size = _file_size(file)
        if size > max_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name}: taille {size} octets > limite {max_mb} Mo"
            )
