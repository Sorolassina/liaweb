# app/services/ACD/archive.py
import os
import zipfile
import json
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import shutil

from sqlmodel import Session, select, text
from sqlalchemy import create_engine, MetaData

from ...models.ACD.archive import Archive, TypeArchive, StatutArchive, RegleNettoyage, LogNettoyage
from ...models.base import User
from ...core.config import settings

class ArchiveService:
    """Service de gestion des archives et sauvegardes"""
    
    def __init__(self, session: Session):
        self.session = session
        self.archive_dir = Path("archives")
        self.archive_dir.mkdir(exist_ok=True)
    
    def create_full_backup(self, user: User, description: str = None) -> Optional[Archive]:
        """Crée une sauvegarde complète de la base de données et des fichiers"""
        try:
            # Créer l'enregistrement d'archive
            archive = Archive(
                nom=f"sauvegarde_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type_archive=TypeArchive.SAUVEGARDE_COMPLETE,
                statut=StatutArchive.EN_COURS,
                description=description or "Sauvegarde complète automatique",
                cree_par=user.id
            )
            self.session.add(archive)
            self.session.commit()
            self.session.refresh(archive)
            
            # Créer le fichier d'archive
            archive_path = self.archive_dir / f"{archive.nom}.zip"
            
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Sauvegarder la base de données
                self._backup_database(zipf)
                
                # 2. Sauvegarder les fichiers uploadés
                self._backup_uploaded_files(zipf)
                
                # 3. Sauvegarder la configuration
                self._backup_configuration(zipf)
                
                # 4. Ajouter les métadonnées
                metadata = {
                    "created_at": archive.cree_le.isoformat(),
                    "created_by": user.email,
                    "archive_type": archive.type_archive,
                    "description": archive.description,
                    "database_url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "hidden",
                    "version": "1.0"
                }
                zipf.writestr("metadata.json", json.dumps(metadata, indent=2))
            
            # Mettre à jour l'archive
            archive.chemin_fichier = str(archive_path)
            archive.taille_fichier = archive_path.stat().st_size
            archive.statut = StatutArchive.TERMINE
            archive.termine_le = datetime.now(timezone.utc)
            archive.expire_le = datetime.now(timezone.utc) + timedelta(days=30)  # 30 jours de rétention
            
            self.session.add(archive)
            self.session.commit()
            
            return archive
            
        except Exception as e:
            if 'archive' in locals():
                archive.statut = StatutArchive.ECHEC
                archive.message_erreur = str(e)
                self.session.add(archive)
                self.session.commit()
            print(f"Erreur lors de la création de l'archive: {e}")
            return None
    
    def _backup_database(self, zipf: zipfile.ZipFile):
        """Sauvegarde la base de données en SQL"""
        try:
            # Créer un fichier SQL temporaire
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as sql_file:
                # Utiliser pg_dump pour PostgreSQL
                import subprocess
                result = subprocess.run([
                    'pg_dump', 
                    settings.DATABASE_URL,
                    '--no-password',
                    '--format=plain',
                    '--no-owner',
                    '--no-privileges'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    sql_file.write(result.stdout)
                    sql_file.flush()
                    
                    # Ajouter le fichier SQL à l'archive
                    zipf.write(sql_file.name, "database_backup.sql")
                    
                else:
                    print(f"Erreur pg_dump: {result.stderr}")
                    
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la base: {e}")
    
    def _backup_uploaded_files(self, zipf: zipfile.ZipFile):
        """Sauvegarde les fichiers uploadés"""
        try:
            # Dossier des uploads (à adapter selon votre configuration)
            upload_dirs = [
                Path("static/uploads"),
                Path("uploads"),
                Path("media")
            ]
            
            for upload_dir in upload_dirs:
                if upload_dir.exists():
                    for file_path in upload_dir.rglob("*"):
                        if file_path.is_file():
                            # Préserver la structure des dossiers
                            arcname = f"files/{file_path.relative_to(upload_dir)}"
                            zipf.write(file_path, arcname)
                            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des fichiers: {e}")
    
    def _backup_configuration(self, zipf: zipfile.ZipFile):
        """Sauvegarde la configuration"""
        try:
            config_files = [
                "pyproject.toml",
                "requirements.txt",
                ".env.example"
            ]
            
            for config_file in config_files:
                if Path(config_file).exists():
                    zipf.write(config_file, f"config/{config_file}")
                    
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration: {e}")
    
    def restore_from_backup(self, archive_id: int, user: User) -> bool:
        """Restaure la base de données à partir d'une archive"""
        try:
            archive = self.session.get(Archive, archive_id)
            if not archive or not archive.chemin_fichier:
                return False
            
            archive_path = Path(archive.chemin_fichier)
            if not archive_path.exists():
                return False
            
            # Extraire l'archive dans un dossier temporaire
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(archive_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # Restaurer la base de données
                sql_file = Path(temp_dir) / "database_backup.sql"
                if sql_file.exists():
                    import subprocess
                    result = subprocess.run([
                        'psql',
                        settings.DATABASE_URL,
                        '-f', str(sql_file)
                    ], capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        print(f"Erreur lors de la restauration: {result.stderr}")
                        return False
                
                # Restaurer les fichiers
                files_dir = Path(temp_dir) / "files"
                if files_dir.exists():
                    for file_path in files_dir.rglob("*"):
                        if file_path.is_file():
                            # Restaurer dans le dossier approprié
                            relative_path = file_path.relative_to(files_dir)
                            target_path = Path("static/uploads") / relative_path
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, target_path)
            
            return True
            
        except Exception as e:
            print(f"Erreur lors de la restauration: {e}")
            return False
    
    def cleanup_old_data(self, user: User) -> Dict[str, int]:
        """Nettoie les anciennes données selon les règles définies"""
        cleanup_stats = {}
        
        try:
            rules = self.session.exec(
                select(RegleNettoyage).where(RegleNettoyage.active == True)
            ).all()
            
            for rule in rules:
                try:
                    # Exécuter la requête de suppression
                    result = self.session.exec(
                        text(f"""
                            DELETE FROM {rule.nom_table} 
                            WHERE {rule.condition}
                        """)
                    )
                    
                    deleted_count = result.rowcount
                    
                    # Enregistrer le log
                    log = LogNettoyage(
                        regle_id=rule.id,
                        enregistrements_supprimes=deleted_count,
                        temps_execution=0.0,  # À calculer si nécessaire
                        statut="SUCCES",
                        execute_par=user.id
                    )
                    self.session.add(log)
                    
                    # Mettre à jour la règle
                    rule.derniere_execution = datetime.now(timezone.utc)
                    self.session.add(rule)
                    
                    cleanup_stats[rule.nom_table] = deleted_count
                    
                except Exception as e:
                    # Log de l'erreur
                    log = LogNettoyage(
                        regle_id=rule.id,
                        enregistrements_supprimes=0,
                        temps_execution=0.0,
                        statut="ECHEC",
                        message_erreur=str(e),
                        execute_par=user.id
                    )
                    self.session.add(log)
                    
                    cleanup_stats[rule.nom_table] = 0
            
            self.session.commit()
            return cleanup_stats
            
        except Exception as e:
            self.session.rollback()
            print(f"Erreur lors du nettoyage: {e}")
            return {}
    
    def get_archive_list(self, limit: int = 50) -> List[Archive]:
        """Récupère la liste des archives"""
        return self.session.exec(
            select(Archive)
            .order_by(Archive.cree_le.desc())
            .limit(limit)
        ).all()
    
    def delete_archive(self, archive_id: int, user: User) -> bool:
        """Supprime une archive"""
        try:
            archive = self.session.get(Archive, archive_id)
            if not archive:
                return False
            
            # Supprimer le fichier physique
            if archive.chemin_fichier and Path(archive.chemin_fichier).exists():
                Path(archive.chemin_fichier).unlink()
            
            # Supprimer l'enregistrement
            self.session.delete(archive)
            self.session.commit()
            
            return True
            
        except Exception as e:
            self.session.rollback()
            print(f"Erreur lors de la suppression de l'archive: {e}")
            return False
