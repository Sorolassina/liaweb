# app/services/file_upload_service.py
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import UploadFile, HTTPException
import aiofiles
from datetime import datetime
from app_lia_web.core.config import settings


class FileUploadService:
    base_upload_path = Path(settings.UPLOAD_DIR)
    
    # Configuration des types de fichiers autorisés
    ALLOWED_EXTENSIONS = {
        'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
        'document': ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt', '.rtf'],
        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.aac'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'],
        'lien': []  # Pas de fichiers pour les liens
    }
    
    # Tailles maximales par type (en MB)
    MAX_FILE_SIZES = {
        'video': 500,  # 500 MB
        'document': 50,  # 50 MB
        'audio': 100,  # 100 MB
        'image': 10,  # 10 MB
        'lien': 0
    }
    
   
    
    @classmethod
    def get_upload_path(cls, resource_type: str) -> Path:
        """Obtenir le chemin d'upload pour un type de ressource"""
        upload_path = cls.BASE_UPLOAD_PATH / resource_type
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path
    
    @classmethod
    def validate_file(cls, file: UploadFile, resource_type: str) -> Dict[str, Any]:
        """Valider un fichier uploadé"""
        if not file.filename:
            raise HTTPException(status_code=400, detail="Aucun fichier sélectionné")
        
        # Vérifier l'extension
        file_ext = Path(file.filename).suffix.lower()
        if resource_type not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Type de ressource non supporté: {resource_type}")
        
        if file_ext not in cls.ALLOWED_EXTENSIONS[resource_type]:
            allowed_exts = ', '.join(cls.ALLOWED_EXTENSIONS[resource_type])
            raise HTTPException(
                status_code=400, 
                detail=f"Extension non autorisée. Extensions autorisées pour {resource_type}: {allowed_exts}"
            )
        
        # Vérifier la taille (approximative)
        file_size_mb = 0
        if hasattr(file, 'size') and file.size:
            file_size_mb = file.size / (1024 * 1024)
        
        max_size = cls.MAX_FILE_SIZES[resource_type]
        if file_size_mb > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"Fichier trop volumineux. Taille maximale pour {resource_type}: {max_size} MB"
            )
        
        return {
            "filename": file.filename,
            "extension": file_ext,
            "size_mb": file_size_mb,
            "valid": True
        }
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """Nettoyer le nom de fichier pour la sécurité et la lisibilité"""
        import re
        
        # Supprimer l'extension pour la traiter séparément
        name, ext = os.path.splitext(filename)
        
        # Nettoyer le nom : garder seulement lettres, chiffres, tirets et underscores
        clean_name = re.sub(r'[^\w\-_\s]', '_', name)
        
        # Remplacer les espaces par des underscores
        clean_name = clean_name.replace(' ', '_')
        
        # Supprimer les underscores multiples
        clean_name = re.sub(r'_+', '_', clean_name)
        
        # Supprimer les underscores en début/fin
        clean_name = clean_name.strip('_')
        
        # Limiter la longueur (max 50 caractères)
        clean_name = clean_name[:50]
        
        # Si le nom est vide après nettoyage, utiliser un nom par défaut
        if not clean_name:
            clean_name = "fichier"
        
        return clean_name + ext
    
    @staticmethod
    def generate_readable_filename(original_filename: str, file_ext: str) -> str:
        """Générer un nom de fichier lisible avec UUID court"""
        # Nettoyer le nom original
        clean_name = FileUploadService.clean_filename(original_filename)
        
        # Générer un UUID court (8 caractères)
        short_uuid = str(uuid.uuid4()).replace('-', '')[:8]
        
        # Construire le nom final
        name_without_ext = os.path.splitext(clean_name)[0]
        return f"{name_without_ext}_{short_uuid}{file_ext}"
    
    @classmethod
    async def save_file(cls, file: UploadFile, resource_type: str, folder_name: str = "uploads", subfolder_id: Optional[int] = None) -> Dict[str, Any]:
        """Sauvegarder un fichier uploadé
        
        Args:
            file: Fichier à uploader
            resource_type: Type de ressource (video, document, audio, image, etc.)
            folder_name: Nom du dossier principal (ex: "elearning", "documents", "media")
            subfolder_id: ID du sous-dossier (ex: module_id, user_id, etc.)
        """
        # Valider le fichier
        validation = cls.validate_file(file, resource_type)
        
        # Générer un nom de fichier lisible et unique
        file_ext = validation["extension"]
        unique_filename = cls.generate_readable_filename(file.filename, file_ext)
        
        # Obtenir le chemin d'upload
        from pathlib import Path
        upload_path = Path(settings.UPLOAD_DIR)
        
        # Créer la structure : upload_path/folder_name/resource_type/[subfolder_id/]
        main_path = upload_path / folder_name / resource_type
        main_path.mkdir(parents=True, exist_ok=True)
        
        # Créer un sous-dossier par ID si spécifié
        if subfolder_id:
            subfolder_path = main_path / f"id_{subfolder_id}"
            subfolder_path.mkdir(exist_ok=True)
            file_path = subfolder_path / unique_filename
        else:
            file_path = main_path / unique_filename
        
        # Sauvegarder le fichier
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde: {str(e)}")
        
        # Calculer le chemin relatif pour la base de données
        if subfolder_id:
            relative_path = f"{folder_name}/{resource_type}/id_{subfolder_id}/{unique_filename}"
        else:
            relative_path = f"{folder_name}/{resource_type}/{unique_filename}"
        
        # Retourner les informations du fichier
        return {
            "original_filename": file.filename,
            "saved_filename": unique_filename,
            "file_path": str(file_path),
            "relative_path": relative_path,
            "size_bytes": len(content),
            "size_mb": round(len(content) / (1024 * 1024), 2),
            "upload_date": datetime.now().isoformat(),
            "folder_name": folder_name,
            "resource_type": resource_type,
            "subfolder_id": subfolder_id
        }
    
    @classmethod
    def delete_file(cls, file_path: str) -> bool:
        """Supprimer un fichier"""
        try:
            full_path = settings.UPLOAD_DIR / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    @classmethod
    def get_file_info(cls, file_path: str) -> Optional[Dict[str, Any]]:
        """Obtenir les informations d'un fichier"""
        try:
            full_path = settings.UPLOAD_DIR / file_path
            if full_path.exists():
                stat = full_path.stat()
                return {
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            return None
        except Exception:
            return None
    
    @classmethod
    def get_allowed_extensions(cls, resource_type: str) -> list:
        """Obtenir les extensions autorisées pour un type de ressource"""
        return cls.ALLOWED_EXTENSIONS.get(resource_type, [])
    
    @classmethod
    def get_max_file_size(cls, resource_type: str) -> int:
        """Obtenir la taille maximale pour un type de ressource"""
        return cls.MAX_FILE_SIZES.get(resource_type, 0)
    
    @classmethod
    def serve_file(cls, file_path: str):
        """Servir un fichier uploadé
        
        Args:
            file_path: Chemin relatif du fichier (ex: "uploads/elearning/video/fichier.mp4")
            
        Returns:
            FileResponse ou HTTPException
        """
        from fastapi.responses import FileResponse
        from fastapi import HTTPException
        import mimetypes
        
        # Construire le chemin complet
        full_path = Path(settings.UPLOAD_DIR) / file_path
        
        # Vérifier que le fichier existe
        if not full_path.exists():
            print(f"🔍 Fichier non trouvé: {full_path}")
            raise HTTPException(status_code=404, detail="Fichier non trouvé")
        
        # Vérifier la sécurité (le fichier doit être dans le dossier uploads)
        try:
            full_path.resolve().relative_to(Path(settings.UPLOAD_DIR).resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        
        # Déterminer le type MIME
        mime_type, _ = mimetypes.guess_type(str(full_path))
        
        # Retourner le fichier
        return FileResponse(
            path=str(full_path),
            media_type=mime_type or "application/octet-stream",
            filename=full_path.name
        )
