"""
Exemples d'utilisation du FileUploadService avec les chemins montés
"""
from app_lia_web.app.services.file_upload_service import FileUploadService

def exemple_utilisation_montures():
    """Exemples d'utilisation des montures dans le service"""
    
    # === EXEMPLE 1: Sauvegarder un document ===
    document_content = b"Contenu du document PDF..."
    document_url = FileUploadService.save_document_to_files("rapport.pdf", document_content)
    print(f"Document sauvegardé: {document_url}")
    # Résultat: http://localhost:8000/files/rapport.pdf
    
    # === EXEMPLE 2: Sauvegarder une image ===
    image_content = b"Contenu de l'image..."
    image_url = FileUploadService.save_image_to_media("photo_profil.jpg", image_content)
    print(f"Image sauvegardée: {image_url}")
    # Résultat: http://localhost:8000/media/photo_profil.jpg
    
    # === EXEMPLE 3: Sauvegarder une carte ===
    map_content = b"Contenu de la carte HTML..."
    map_url = FileUploadService.save_map_to_maps("plan_acd.html", map_content)
    print(f"Carte sauvegardée: {map_url}")
    # Résultat: http://localhost:8000/maps/plan_acd.html
    
    # === EXEMPLE 4: Obtenir des URLs ===
    doc_url = FileUploadService.get_document_url("cv.pdf")
    img_url = FileUploadService.get_image_url("logo.png")
    map_url = FileUploadService.get_map_url("plan_codev.html")
    
    print(f"URLs générées:")
    print(f"  Document: {doc_url}")
    print(f"  Image: {img_url}")
    print(f"  Carte: {map_url}")
    
    # === EXEMPLE 5: Utilisation générique ===
    # Sauvegarder dans n'importe quelle monture
    generic_url = FileUploadService.save_to_mount("media", "uploads/document.pdf", document_content)
    print(f"URL générique: {generic_url}")
    
    # === EXEMPLE 6: Lister les fichiers ===
    files_list = FileUploadService.list_mount_files("files")
    print(f"Fichiers dans /files: {files_list}")
    
    # === EXEMPLE 7: Supprimer un fichier ===
    success = FileUploadService.delete_from_mount("files", "ancien_document.pdf")
    print(f"Suppression réussie: {success}")

if __name__ == "__main__":
    exemple_utilisation_montures()
