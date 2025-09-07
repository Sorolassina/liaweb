#!/usr/bin/env python3
"""
Script pour migrer les documents existants vers la nouvelle structure par candidat.
Ce script réorganise les documents dans des dossiers spécifiques par candidat.
"""

import os
import sys
import shutil
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import create_engine, Session, select
from models.base import Document
from core.config import settings

def migrate_documents_structure():
    """Migre les documents vers la nouvelle structure par candidat."""
    print("🔄 Début de la migration des documents vers la structure par candidat...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    with Session(engine) as session:
        # Récupérer tous les documents
        documents = session.exec(select(Document)).all()
        
        if not documents:
            print("ℹ️ Aucun document à migrer.")
            return
        
        print(f"📄 {len(documents)} documents trouvés à migrer.")
        
        # Grouper par candidat
        candidats_docs = {}
        for doc in documents:
            if doc.candidat_id not in candidats_docs:
                candidats_docs[doc.candidat_id] = []
            candidats_docs[doc.candidat_id].append(doc)
        
        print(f"👥 {len(candidats_docs)} candidats avec des documents.")
        
        # Créer les dossiers et migrer les fichiers
        for candidat_id, docs in candidats_docs.items():
            print(f"\n👤 Migration des documents du candidat {candidat_id}...")
            
            # Créer le dossier du candidat
            candidat_dir = settings.FICHIERS_DIR / "documents" / f"candidat_{candidat_id}"
            candidat_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Dossier créé: {candidat_dir}")
            
            # Migrer chaque document
            for doc in docs:
                if not doc.chemin_fichier:
                    print(f"⚠️ Document {doc.id} sans chemin de fichier, ignoré.")
                    continue
                
                old_path = Path(doc.chemin_fichier)
                if not old_path.exists():
                    print(f"⚠️ Fichier {old_path} introuvable, ignoré.")
                    continue
                
                # Nouveau nom de fichier
                file_ext = old_path.suffix.lower() or ".pdf"
                new_filename = f"{doc.type_document.value.lower()}_{candidat_id}{file_ext}"
                new_path = candidat_dir / new_filename
                
                # Gérer les doublons
                counter = 1
                while new_path.exists():
                    name_without_ext = f"{doc.type_document.value.lower()}_{candidat_id}"
                    new_filename = f"{name_without_ext}_{counter}{file_ext}"
                    new_path = candidat_dir / new_filename
                    counter += 1
                
                try:
                    # Déplacer le fichier
                    shutil.move(str(old_path), str(new_path))
                    
                    # Mettre à jour le chemin en base
                    doc.chemin_fichier = str(new_path)
                    session.add(doc)
                    
                    print(f"✅ Migré: {old_path.name} → {new_filename}")
                    
                except Exception as e:
                    print(f"❌ Erreur lors de la migration de {old_path}: {e}")
        
        # Sauvegarder les changements
        session.commit()
        print(f"\n🎉 Migration terminée ! {len(documents)} documents migrés.")
        
        # Nettoyer les anciens dossiers vides
        documents_root = settings.FICHIERS_DIR / "documents"
        for item in documents_root.iterdir():
            if item.is_dir() and not any(item.iterdir()):
                print(f"🗑️ Suppression du dossier vide: {item}")
                item.rmdir()

if __name__ == "__main__":
    migrate_documents_structure()
