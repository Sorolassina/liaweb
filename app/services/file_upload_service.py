"""
Service optimisé de gestion des uploads de fichiers avec accès aux chemins montés
"""
import os
import re
import uuid
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import aiofiles
from fastapi import UploadFile, HTTPException
from fastapi.responses import FileResponse

from ..core.config import settings
from ..core.path_config import path_config


class FileUploadService:
    """
    Service optimisé de gestion des uploads de fichiers avec accès aux chemins montés.
    
    Fonctionnalités :
    - Upload sécurisé avec validation
    - Gestion des montures centralisées
    - Nettoyage automatique des noms de fichiers
    - Support asynchrone
    - Gestion d'erreurs robuste
    """
    
    # === CONFIGURATION DES TYPES DE FICHIERS ===
    ALLOWED_EXTENSIONS = {
        'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
        'document': ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt', '.rtf', '.odt', '.ods', '.html'],
        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.tiff'],
        'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'lien': []  # Pas de fichiers pour les liens
    }
    
    # Tailles maximales par type (en MB)
    MAX_FILE_SIZES = {
        'video': 500,    # 500 MB
        'document': 50,  # 50 MB
        'audio': 100,    # 100 MB
        'image': 10,     # 10 MB
        'archive': 200,  # 200 MB
        'lien': 0
    }
    
    # Types MIME autorisés par extension
    MIME_TYPES = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
    }
    
    # === MÉTHODES DE CONFIGURATION ===
    
    @classmethod
    def get_allowed_extensions(cls, resource_type: str) -> List[str]:
        """Obtenir les extensions autorisées pour un type de ressource"""
        return cls.ALLOWED_EXTENSIONS.get(resource_type, [])
    
    @classmethod
    def get_max_file_size(cls, resource_type: str) -> int:
        """Obtenir la taille maximale pour un type de ressource (en MB)"""
        return cls.MAX_FILE_SIZES.get(resource_type, 0)
    
    @classmethod
    def is_extension_allowed(cls, extension: str, resource_type: str) -> bool:
        """Vérifier si une extension est autorisée pour un type de ressource"""
        return extension.lower() in cls.get_allowed_extensions(resource_type)
    
    # === MÉTHODES DE VALIDATION ===
    
    @classmethod
    def validate_file(cls, file: UploadFile, resource_type: str) -> Dict[str, Any]:
        """
        Valider un fichier uploadé de manière optimisée
        
        Args:
            file: Fichier à valider
            resource_type: Type de ressource attendu
            
        Returns:
            Dict avec les informations de validation
            
        Raises:
            HTTPException: Si le fichier n'est pas valide
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="Aucun fichier sélectionné")
        
        # Vérifier le type de ressource
        if resource_type not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Type de ressource non supporté: {resource_type}. Types disponibles: {list(cls.ALLOWED_EXTENSIONS.keys())}"
            )
        
        # Extraire l'extension
        file_ext = Path(file.filename).suffix.lower()
        
        # Vérifier l'extension
        if not cls.is_extension_allowed(file_ext, resource_type):
            allowed_exts = ', '.join(cls.get_allowed_extensions(resource_type))
            raise HTTPException(
                status_code=400, 
                detail=f"Extension '{file_ext}' non autorisée pour {resource_type}. Extensions autorisées: {allowed_exts}"
            )
        
        # Vérifier la taille (si disponible)
        file_size_mb = 0
        if hasattr(file, 'size') and file.size:
            file_size_mb = file.size / (1024 * 1024)
            max_size = cls.get_max_file_size(resource_type)
            if file_size_mb > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Fichier trop volumineux ({file_size_mb:.1f} MB). Taille maximale pour {resource_type}: {max_size} MB"
                )
        
        return {
            "filename": file.filename,
            "extension": file_ext,
            "size_mb": file_size_mb,
            "resource_type": resource_type,
            "valid": True
        }
    
    # === MÉTHODES DE NETTOYAGE DES NOMS DE FICHIERS ===
    
    @staticmethod
    def clean_filename(filename: str, max_length: int = 50) -> str:
        """
        Nettoyer le nom de fichier pour la sécurité et la lisibilité
        
        Args:
            filename: Nom de fichier original
            max_length: Longueur maximale du nom (sans extension)
            
        Returns:
            Nom de fichier nettoyé
        """
        if not filename:
            return "fichier"
        
        # Séparer nom et extension
        name, ext = os.path.splitext(filename)
        
        # Nettoyer le nom : garder seulement lettres, chiffres, tirets et underscores
        clean_name = re.sub(r'[^\w\-_\s]', '_', name)
        
        # Remplacer les espaces par des underscores
        clean_name = clean_name.replace(' ', '_')
        
        # Supprimer les underscores multiples
        clean_name = re.sub(r'_+', '_', clean_name)
        
        # Supprimer les underscores en début/fin
        clean_name = clean_name.strip('_')
        
        # Limiter la longueur
        clean_name = clean_name[:max_length]
        
        # Si le nom est vide après nettoyage, utiliser un nom par défaut
        if not clean_name:
            clean_name = "fichier"
        
        return clean_name + ext
    
    @staticmethod
    def generate_unique_filename(original_filename: str, file_ext: str, use_timestamp: bool = True) -> str:
        """
        Générer un nom de fichier unique et lisible
        
        Args:
            original_filename: Nom de fichier original
            file_ext: Extension du fichier
            use_timestamp: Utiliser un timestamp au lieu d'UUID
            
        Returns:
            Nom de fichier unique
        """
        # Nettoyer le nom original
        clean_name = FileUploadService.clean_filename(original_filename)
        name_without_ext = os.path.splitext(clean_name)[0]
        
        if use_timestamp:
            # Utiliser un timestamp pour l'unicité
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = f"{timestamp}_{uuid.uuid4().hex[:4]}"
        else:
            # Utiliser un UUID court
            unique_id = str(uuid.uuid4()).replace('-', '')[:8]
        
        return f"{name_without_ext}_{unique_id}{file_ext}"
    
    # === MÉTHODES DE GESTION DES MONTURES ===
    
    @classmethod
    def get_mount_url(cls, mount_name: str, file_path: str) -> str:
        """Obtenir l'URL complète d'un fichier via une monture"""
        return path_config.get_file_url(mount_name, file_path)
    
    @classmethod
    def get_mount_physical_path(cls, mount_name: str, file_path: str) -> Path:
        """Obtenir le chemin physique d'un fichier via une monture"""
        return path_config.get_physical_path(mount_name, file_path)
    
    @classmethod
    def ensure_mount_directory(cls, mount_name: str) -> Path:
        """S'assurer qu'un répertoire de monture existe"""
        return path_config.ensure_directory_exists(mount_name)
    
    @classmethod
    async def save_to_mount_async(cls, mount_name: str, file_path: str, content: bytes) -> str:
        """
        Sauvegarder du contenu dans une monture de manière asynchrone
        
        Args:
            mount_name: Nom de la monture
            file_path: Chemin du fichier dans la monture
            content: Contenu à sauvegarder
            
        Returns:
            URL du fichier sauvegardé
        """
        # Obtenir le chemin physique
        physical_path = cls.get_mount_physical_path(mount_name, file_path)
        
        # Créer le répertoire parent si nécessaire
        physical_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Sauvegarder le fichier de manière asynchrone
        async with aiofiles.open(physical_path, 'wb') as f:
            await f.write(content)
        
        # Retourner l'URL
        return cls.get_mount_url(mount_name, file_path)
    
    @classmethod
    def save_to_mount(cls, mount_name: str, file_path: str, content: bytes) -> str:
        """Sauvegarder du contenu dans une monture (version synchrone)"""
        physical_path = cls.get_mount_physical_path(mount_name, file_path)
        physical_path.parent.mkdir(parents=True, exist_ok=True)
        physical_path.write_bytes(content)
        return cls.get_mount_url(mount_name, file_path)
    
    @classmethod
    async def get_file_from_mount_async(cls, mount_name: str, file_path: str) -> Optional[bytes]:
        """Récupérer le contenu d'un fichier depuis une monture (version asynchrone)"""
        physical_path = cls.get_mount_physical_path(mount_name, file_path)
        
        if physical_path.exists():
            async with aiofiles.open(physical_path, 'rb') as f:
                return await f.read()
        return None
    
    @classmethod
    def get_file_from_mount(cls, mount_name: str, file_path: str) -> Optional[bytes]:
        """Récupérer le contenu d'un fichier depuis une monture (version synchrone)"""
        physical_path = cls.get_mount_physical_path(mount_name, file_path)
        
        if physical_path.exists():
            return physical_path.read_bytes()
        return None
    
    @classmethod
    def delete_from_mount(cls, mount_name: str, file_path: str) -> bool:
        """Supprimer un fichier d'une monture"""
        physical_path = cls.get_mount_physical_path(mount_name, file_path)
        
        if physical_path.exists():
            physical_path.unlink()
            return True
        return False
    
    @classmethod
    def list_mount_files(cls, mount_name: str, subdirectory: str = "", recursive: bool = False) -> List[str]:
        """
        Lister les fichiers dans une monture
        
        Args:
            mount_name: Nom de la monture
            subdirectory: Sous-répertoire à lister
            recursive: Lister récursivement
            
        Returns:
            Liste des noms de fichiers
        """
        mount_dir = path_config.ensure_directory_exists(mount_name)
        
        if subdirectory:
            target_dir = mount_dir / subdirectory
        else:
            target_dir = mount_dir
            
        if not target_dir.exists():
            return []
        
        if recursive:
            return [str(f.relative_to(mount_dir)) for f in target_dir.rglob('*') if f.is_file()]
        else:
            return [f.name for f in target_dir.iterdir() if f.is_file()]
    
    # === MÉTHODES SPÉCIALISÉES POUR CHAQUE MONTURE ===
    
    @classmethod
    async def save_document_to_files_async(cls, filename: str, content: bytes) -> str:
        """Sauvegarder un document dans la monture /files (version asynchrone)"""
        return await cls.save_to_mount_async("files", filename, content)
    
    @classmethod
    def save_document_to_files(cls, filename: str, content: bytes) -> str:
        """Sauvegarder un document dans la monture /files"""
        return cls.save_to_mount("files", filename, content)
    
    @classmethod
    async def save_image_to_media_async(cls, filename: str, content: bytes) -> str:
        """Sauvegarder une image dans la monture /media (version asynchrone)"""
        return await cls.save_to_mount_async("media", filename, content)
    
    @classmethod
    def save_image_to_media(cls, filename: str, content: bytes) -> str:
        """Sauvegarder une image dans la monture /media"""
        return cls.save_to_mount("media", filename, content)
    
    @classmethod
    async def save_map_to_maps_async(cls, filename: str, content: bytes) -> str:
        """Sauvegarder une carte dans la monture /maps (version asynchrone)"""
        return await cls.save_to_mount_async("maps", filename, content)
    
    @classmethod
    def save_map_to_maps(cls, filename: str, content: bytes) -> str:
        """Sauvegarder une carte dans la monture /maps"""
        return cls.save_to_mount("maps", filename, content)
    
    @classmethod
    def get_document_url(cls, filename: str) -> str:
        """Obtenir l'URL d'un document depuis /files"""
        return cls.get_mount_url("files", filename)
    
    @classmethod
    def get_image_url(cls, filename: str) -> str:
        """Obtenir l'URL d'une image depuis /media"""
        return cls.get_mount_url("media", filename)
    
    @classmethod
    def get_map_url(cls, filename: str) -> str:
        """Obtenir l'URL d'une carte depuis /maps"""
        return cls.get_mount_url("maps", filename)
    
    # === MÉTHODES D'UPLOAD PRINCIPALES ===
    
    @classmethod
    async def save_file_async(
        cls, 
        file: UploadFile, 
        resource_type: str, 
        folder_name: str = "uploads", 
        programme_code: Optional[str] = None,  # Code du programme pour isoler les fichiers
        subfolder_id: Optional[int] = None,
        use_mount: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sauvegarder un fichier uploadé de manière asynchrone et optimisée
        
        Args:
            file: Fichier à uploader
            resource_type: Type de ressource
            folder_name: Nom du dossier principal
            programme_code: Code du programme pour isoler les fichiers par programme
            subfolder_id: ID du sous-dossier
            use_mount: Utiliser une monture spécifique au lieu du système d'upload classique
            
        Returns:
            Dict avec les informations du fichier sauvegardé
        """
        # Valider le fichier
        validation = cls.validate_file(file, resource_type)
        
        # Générer un nom de fichier unique
        file_ext = validation["extension"]
        unique_filename = cls.generate_unique_filename(file.filename, file_ext)
        
        # Lire le contenu du fichier
        content = await file.read()
        
        # Vérifier la taille réelle
        actual_size_mb = len(content) / (1024 * 1024)
        max_size = cls.get_max_file_size(resource_type)
        
        if actual_size_mb > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"Fichier trop volumineux ({actual_size_mb:.1f} MB). Taille maximale pour {resource_type}: {max_size} MB"
            )
        
        # Sauvegarder selon la méthode choisie
        if use_mount:
            # Utiliser une monture spécifique
            file_url = await cls.save_to_mount_async(use_mount, unique_filename, content)
            relative_path = unique_filename
        else:
            # Utiliser le système d'upload classique
            upload_path = path_config.UPLOAD_DIR
            main_path = upload_path / folder_name / resource_type
            
            # Ajouter le sous-dossier programme si fourni
            if programme_code:
                main_path = main_path / programme_code.lower()
            
            main_path.mkdir(parents=True, exist_ok=True)
            
            if subfolder_id:
                subfolder_path = main_path / f"id_{subfolder_id}"
                subfolder_path.mkdir(exist_ok=True)
                file_path = subfolder_path / unique_filename
                if programme_code:
                    relative_path = f"{folder_name}/{resource_type}/{programme_code.lower()}/id_{subfolder_id}/{unique_filename}"
                else:
                    relative_path = f"{folder_name}/{resource_type}/id_{subfolder_id}/{unique_filename}"
            else:
                file_path = main_path / unique_filename
                if programme_code:
                    relative_path = f"{folder_name}/{resource_type}/{programme_code.lower()}/{unique_filename}"
                else:
                    relative_path = f"{folder_name}/{resource_type}/{unique_filename}"
            
            # Sauvegarder le fichier
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            file_url = f"/uploads/{relative_path}"
        
        # Retourner les informations du fichier
        return {
            "original_filename": file.filename,
            "saved_filename": unique_filename,
            "file_url": file_url,
            "relative_path": relative_path,
            "size_bytes": len(content),
            "size_mb": round(actual_size_mb, 2),
            "upload_date": datetime.now().isoformat(),
            "folder_name": folder_name,
            "resource_type": resource_type,
            "programme_code": programme_code,
            "subfolder_id": subfolder_id,
            "mount_used": use_mount
        }
    
    @classmethod
    async def save_file(
        cls, 
        file: UploadFile, 
        resource_type: str, 
        folder_name: str = "uploads", 
        programme_code: Optional[str] = None,  # Code du programme pour isoler les fichiers
        subfolder_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Version synchrone de save_file_async (pour compatibilité)"""
        return await cls.save_file_async(file, resource_type, folder_name, programme_code, subfolder_id)
    
    @classmethod
    async def save_media_file(
        cls,
        file: UploadFile,
        media_type: str,  # Ex: "profile_image", "video", "audio"
        programme_code: Optional[str] = None,  # Code du programme pour isoler les fichiers
        subfolder_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sauvegarder un fichier média (image, vidéo, audio) dans media/
        
        Args:
            file: Fichier à uploader
            media_type: Type de média (ex: "profile_image", "video", "audio")
            programme_code: Code du programme pour isoler les fichiers par programme
            subfolder_id: ID optionnel pour créer un sous-dossier (ex: id_95)
            
        Returns:
            Dict avec les informations du fichier sauvegardé
        """
        # Valider le fichier
        # Déterminer le type de ressource selon le media_type
        if media_type.startswith("image") or media_type.startswith("profile") or media_type == "qpv_map":
            resource_type = "image"
        elif media_type.startswith("video"):
            resource_type = "video"
        elif media_type.startswith("audio"):
            resource_type = "audio"
        else:
            # Par défaut, essayer de détecter depuis l'extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.tiff']:
                resource_type = "image"
            elif file_ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv']:
                resource_type = "video"
            elif file_ext in ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac']:
                resource_type = "audio"
            else:
                resource_type = "image"  # Par défaut pour les médias
        
        validation = cls.validate_file(file, resource_type)
        
        # Générer un nom de fichier unique
        file_ext = validation["extension"]
        unique_filename = cls.generate_unique_filename(file.filename, file_ext)
        
        # Lire le contenu du fichier
        content = await file.read()
        
        # Vérifier la taille réelle
        actual_size_mb = len(content) / (1024 * 1024)
        max_size = cls.get_max_file_size(resource_type)
        
        if actual_size_mb > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"Fichier trop volumineux ({actual_size_mb:.1f} MB). Taille maximale pour {media_type}: {max_size} MB"
            )
        
        # Utiliser MEDIA_DIR au lieu de UPLOAD_DIR
        media_path = path_config.MEDIA_DIR
        main_path = media_path / media_type
        
        # Ajouter le sous-dossier programme si fourni
        if programme_code:
            main_path = main_path / programme_code.lower()
        
        main_path.mkdir(parents=True, exist_ok=True)
        
        if subfolder_id:
            subfolder_path = main_path / f"id_{subfolder_id}"
            subfolder_path.mkdir(exist_ok=True)
            file_path = subfolder_path / unique_filename
            if programme_code:
                relative_path = f"{media_type}/{programme_code.lower()}/id_{subfolder_id}/{unique_filename}"
            else:
                relative_path = f"{media_type}/id_{subfolder_id}/{unique_filename}"
        else:
            file_path = main_path / unique_filename
            if programme_code:
                relative_path = f"{media_type}/{programme_code.lower()}/{unique_filename}"
            else:
                relative_path = f"{media_type}/{unique_filename}"
        
        # Sauvegarder le fichier
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        file_url = f"/media/{relative_path}"
        
        # Retourner les informations du fichier
        return {
            "original_filename": file.filename,
            "saved_filename": unique_filename,
            "file_url": file_url,
            "relative_path": relative_path,
            "size_bytes": len(content),
            "size_mb": round(actual_size_mb, 2),
            "upload_date": datetime.now().isoformat(),
            "media_type": media_type,
            "programme_code": programme_code,
            "subfolder_id": subfolder_id
        }
    
    @classmethod
    def serve_media_file(cls, file_path: str) -> Union[FileResponse, HTTPException]:
        """
        Servir un fichier média depuis media/ de manière optimisée
        
        Args:
            file_path: Chemin relatif du fichier (ex: "profile_image/acd/id_95/filename.png")
            
        Returns:
            FileResponse ou HTTPException
        """
        # Normaliser les séparateurs de chemin (Windows utilise \ mais on stocke avec /)
        file_path = file_path.replace('\\', '/').strip()
        
        # Supprimer les slashes en début si présents (pour éviter les doublons)
        file_path = file_path.lstrip('/')
        
        # Construire le chemin complet dans MEDIA_DIR
        full_path = path_config.MEDIA_DIR / file_path
        
        # Debug: afficher les chemins
        if settings.DEBUG:
            print(f"🔍 [MEDIA] Chemin recherché: {file_path}")
            print(f"🔍 [MEDIA] Chemin complet: {full_path}")
            print(f"🔍 [MEDIA] Chemin absolu résolu: {full_path.resolve()}")
            print(f"🔍 [MEDIA] MEDIA_DIR: {path_config.MEDIA_DIR}")
            print(f"🔍 [MEDIA] MEDIA_DIR résolu: {path_config.MEDIA_DIR.resolve()}")
            print(f"🔍 [MEDIA] Fichier existe: {full_path.exists()}")
            if not full_path.exists():
                # Lister les fichiers dans le dossier parent pour debug
                parent_dir = full_path.parent
                if parent_dir.exists():
                    print(f"🔍 [MEDIA] Fichiers dans {parent_dir}: {list(parent_dir.iterdir())}")
        
        # Vérifier que le fichier existe
        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"Fichier non trouvé: {full_path}")
        
        # Vérifier la sécurité
        try:
            resolved_path = full_path.resolve()
            media_dir_resolved = path_config.MEDIA_DIR.resolve()
            if not str(resolved_path).startswith(str(media_dir_resolved)):
                raise HTTPException(status_code=403, detail="Accès non autorisé")
        except ValueError:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        
        # Déterminer le type MIME
        mime_type = cls.MIME_TYPES.get(full_path.suffix.lower())
        if not mime_type:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(full_path))
            mime_type = mime_type or "application/octet-stream"
        
        # Retourner le fichier avec les bonnes informations
        return FileResponse(
            path=str(full_path.resolve()),
            media_type=mime_type,
            filename=full_path.name,
            headers={"Content-Disposition": f"inline; filename={full_path.name}"}
        )
    
    # === MÉTHODES DE GESTION DES FICHIERS ===
    
    @classmethod
    def delete_file(cls, file_path: str) -> bool:
        """Supprimer un fichier"""
        try:
            full_path = path_config.UPLOAD_DIR / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    @classmethod
    def get_file_info(cls, file_path: str) -> Optional[Dict[str, Any]]:
        """Obtenir les informations détaillées d'un fichier"""
        try:
            full_path = path_config.UPLOAD_DIR / file_path
            if full_path.exists():
                stat = full_path.stat()
                return {
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "is_file": full_path.is_file(),
                    "is_directory": full_path.is_dir()
                }
            return None
        except Exception:
            return None
    
    @classmethod
    def serve_file(cls, file_path: str) -> Union[FileResponse, HTTPException]:
        """
        Servir un fichier uploadé de manière optimisée
        
        Args:
            file_path: Chemin relatif du fichier
            
        Returns:
            FileResponse ou HTTPException
        """
        # Construire le chemin complet
        full_path = path_config.UPLOAD_DIR / file_path
        
        # Vérifier que le fichier existe
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Fichier non trouvé")
        
        # Vérifier la sécurité
        try:
            full_path.resolve().relative_to(path_config.UPLOAD_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        
        # Déterminer le type MIME
        mime_type = cls.MIME_TYPES.get(full_path.suffix.lower())
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(full_path))
            mime_type = mime_type or "application/octet-stream"
        
        # Retourner le fichier avec les bonnes informations
        return FileResponse(
            path=str(full_path),
            media_type=mime_type,
            filename=full_path.name,
            headers={"Content-Disposition": f"inline; filename={full_path.name}"}
        )
    
    # === MÉTHODES UTILITAIRES ===
    @staticmethod
    def encode_file_to_base64(file_path: str) -> str:
        import base64
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
            
    @classmethod
    def get_file_stats(cls, directory: str = "") -> Dict[str, Any]:
        """Obtenir des statistiques sur les fichiers uploadés"""
        upload_dir = path_config.UPLOAD_DIR
        if directory:
            target_dir = upload_dir / directory
        else:
            target_dir = upload_dir
        
        if not target_dir.exists():
            return {"total_files": 0, "total_size_mb": 0, "files_by_type": {}}
        
        total_files = 0
        total_size = 0
        files_by_type = {}
        
        for file_path in target_dir.rglob('*'):
            if file_path.is_file():
                total_files += 1
                file_size = file_path.stat().st_size
                total_size += file_size
                
                ext = file_path.suffix.lower()
                files_by_type[ext] = files_by_type.get(ext, 0) + 1
        
        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files_by_type": files_by_type
        }