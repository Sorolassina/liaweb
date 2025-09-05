"""
Router pour la gestion des documents
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional
import os
import shutil
from datetime import datetime, timezone

from ..core.database import get_session
from ..core.security import get_current_user
from ..core.utils import FileUtils
from ..models.base import User, Document, Candidat
from ..models.enums import UserRole, TypeDocument
from ..schemas import DocumentResponse
from ..core.config import settings

router = APIRouter()


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    candidat_id: int,
    type_document: TypeDocument,
    titre: Optional[str] = None,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Upload un document pour un candidat"""
    # Vérifier les permissions
    if current_user.role not in [UserRole.CONSEILLER, UserRole.RESPONSABLE_PROGRAMME, UserRole.ADMINISTRATEUR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    # Vérifier que le candidat existe
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidat non trouvé"
        )
    
    # Vérifier le type de fichier
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
    if not FileUtils.is_allowed_file(file.filename, allowed_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type de fichier non autorisé. Types autorisés: PDF, JPG, PNG, DOC, DOCX"
        )
    
    # Vérifier la taille du fichier (max 10MB)
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier trop volumineux. Taille maximum: 10MB"
        )
    
    # Créer le répertoire d'upload s'il n'existe pas
    upload_dir = FileUtils.ensure_upload_dir()
    
    # Générer un nom de fichier unique
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = FileUtils.get_file_extension(file.filename)
    unique_filename = f"doc_{candidat_id}_{timestamp}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Sauvegarder le fichier
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde du fichier: {str(e)}"
        )
    
    # Créer l'enregistrement en base
    document = Document(
        candidat_id=candidat_id,
        type_document=type_document,
        titre=titre or file.filename,
        nom_fichier=file.filename,
        chemin_fichier=file_path,
        mimetype=file.content_type,
        taille_octets=file.size,
        depose_par_id=current_user.id,
        depose_le=datetime.now(timezone.utc)
    )
    
    session.add(document)
    session.commit()
    session.refresh(document)
    
    return DocumentResponse.from_orm(document)


@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    candidat_id: Optional[int] = Query(None, description="Filtrer par candidat"),
    type_document: Optional[TypeDocument] = Query(None, description="Filtrer par type de document"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des documents"""
    query = select(Document)
    
    # Appliquer les filtres
    if candidat_id:
        query = query.where(Document.candidat_id == candidat_id)
    
    if type_document:
        query = query.where(Document.type_document == type_document)
    
    documents = session.exec(query.order_by(Document.depose_le.desc())).all()
    return [DocumentResponse.from_orm(doc) for doc in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère un document par ID"""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    return DocumentResponse.from_orm(document)


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Télécharge un document"""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Vérifier que le fichier existe
    if not os.path.exists(document.chemin_fichier):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier non trouvé sur le serveur"
        )
    
    return FileResponse(
        path=document.chemin_fichier,
        filename=document.nom_fichier,
        media_type=document.mimetype
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Supprime un document"""
    # Vérifier les permissions
    if current_user.role not in [UserRole.CONSEILLER, UserRole.RESPONSABLE_PROGRAMME, UserRole.ADMINISTRATEUR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Supprimer le fichier physique
    if os.path.exists(document.chemin_fichier):
        try:
            os.remove(document.chemin_fichier)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de la suppression du fichier: {str(e)}"
            )
    
    # Supprimer l'enregistrement en base
    session.delete(document)
    session.commit()
    
    return {"message": "Document supprimé avec succès"}


@router.put("/documents/{document_id}")
async def update_document(
    document_id: int,
    titre: Optional[str] = None,
    type_document: Optional[TypeDocument] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Met à jour les métadonnées d'un document"""
    # Vérifier les permissions
    if current_user.role not in [UserRole.CONSEILLER, UserRole.RESPONSABLE_PROGRAMME, UserRole.ADMINISTRATEUR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Mettre à jour les champs
    if titre is not None:
        document.titre = titre
    
    if type_document is not None:
        document.type_document = type_document
    
    session.add(document)
    session.commit()
    session.refresh(document)
    
    return DocumentResponse.from_orm(document)


@router.get("/candidats/{candidat_id}/documents")
async def get_candidat_documents(
    candidat_id: int,
    type_document: Optional[TypeDocument] = Query(None, description="Filtrer par type de document"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère les documents d'un candidat"""
    # Vérifier que le candidat existe
    candidat = session.get(Candidat, candidat_id)
    if not candidat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidat non trouvé"
        )
    
    query = select(Document).where(Document.candidat_id == candidat_id)
    
    if type_document:
        query = query.where(Document.type_document == type_document)
    
    documents = session.exec(query.order_by(Document.depose_le.desc())).all()
    return [DocumentResponse.from_orm(doc).dict() for doc in documents]
