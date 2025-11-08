import requests
import folium
from datetime import date
from geopy.distance import geodesic
from shapely.geometry import Point, Polygon
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from PIL import Image
from folium.features import DivIcon
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi import Request

from ..core.config import settings
from .file_upload_service import FileUploadService
from ..schemas.preinscription_schemas import Adresse
from typing import Optional
from pathlib import Path
import tempfile
import base64

def _encode_file_to_base64(file_path: str) -> str:
    """Helper function pour encoder un fichier en base64"""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

async def verif_qpv(
    address_coords, 
    request: Request,
    programme_code: Optional[str] = None,
    subfolder_id: Optional[int] = None
):

    base_url = settings.get_base_url(request)  # Récupérer l'URL dynamique
    print("✅ Adresse validée au niveau du service :", address_coords)
    # 🔐 Protection : accepte Pydantic OU dict
    if isinstance(address_coords, Adresse):
        address_dict = address_coords.model_dump()
    elif isinstance(address_coords, dict):
        address_dict = address_coords
    else:
        raise ValueError("❌ Format non reconnu pour address_coords")
    
    address = address_dict.get("address")

    address = str(address) if address is not None else ""
    
    print(f"🔍 Envoi du payload à verif_qpv : {address}")

    # 🔒 Vérification de la qualité du champ avant appel API
    if (
        not address or
        len(address) < 5 or
        len(address.split()) < 3
    ) :
        return {
            "address": f"Adresse incorrecte{address}",
            "nom_qp": "",
            "distance_m": "",
            "carte": "",
            "image_url": "",
            "image_encoded": ""
        }

    url = f"https://api-adresse.data.gouv.fr/search/?q={address.replace(' ', '+')}" 
    
    nouvel_adre=address.replace(" ", "_").replace(",", "_").replace(".", "_").replace("-", "_").replace("'", "_")
        
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lève une erreur si la requête échoue
        data = response.json() # Vérifier si la réponse est bien un JSON
    
        # Vérifier s'il y a des résultats
        if not data.get("features"):
            return {
                "error": "❌ Aucune coordonnée GPS trouvée pour cette adresse. Vérifiez l'adresse saisie."
            }

        coords = data["features"][0]["geometry"]["coordinates"]
        lat = coords[1]
        lon = coords[0]
                                
    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur API : {str(e)}"}
    
    # ✅ Définir `m` au début pour éviter l'erreur
    point_coords = (lat, lon)
    m = folium.Map(location=point_coords, zoom_start=14)

    # URL de l'API Open Data Soft pour récupérer les QPV
    urlqpv = f"https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/quartiers-prioritaires-de-la-politique-de-la-ville-qpv/records?where=within_distance(geo_shape, geom'POINT({lon} {lat})', 0.3km)"

    try:
        response = requests.get(urlqpv)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur API : {str(e)}"}
    
    # Vérifier que des résultats existent
    records = data.get("results", [])

    if records and "geo_shape" in records[0] and "geometry" in records[0]["geo_shape"]:
        # Extraction des données du QPV
        coord_qpv = records[0]["geo_shape"]["geometry"]["coordinates"][0]  # Coordonnées du polygone
        qpv_name = records[0]["nom_qp"]  # Nom du QPV
    else:
        coord_qpv = None
        qpv_name = None

    # Vérifier si un QPV a été trouvé
    if coord_qpv and isinstance(coord_qpv, list) and len(coord_qpv) > 2:
        
        point_coords = (lat, lon)
        address_point = Point(point_coords[::-1])  # Shapely utilise (lon, lat)
        polygon = Polygon(coord_qpv)
        
        # Générer la carte avec Folium
        folium.PolyLine([(y, x) for x, y in coord_qpv], color="blue", fill=True,fill_color="lightblue",
                        weight=2.5, fill_opacity=0.6).add_to(m)
        
        # Ajouter le point de l'adresse à notre carte
        folium.Marker(
            location=(lat, lon),
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)

        
        # Déterminer l'état du QPV
        if polygon.contains(address_point):
            etat_qpv = "QPV"
            distance_m=0
        else:
            # Calcul de la distance
            nearest_point = polygon.exterior.interpolate(polygon.exterior.project(address_point))
            nearest_coords = (nearest_point.y, nearest_point.x)
            distance_km = geodesic(point_coords, nearest_coords).kilometers
            distance_m = round(distance_km * 1000) # On calcul en mètres
            
            if distance_m <= settings.DISTANCE_QPV_LIMITE:
                etat_qpv = "QPV limit"
            else:
                etat_qpv = f"Adresse à plus de {settings.DISTANCE_QPV_LIMITE:.0f} m du qpv"

        # 🔥 Ajouter une couche de texte (affichage permanent)
        info_text = f"""
            <div style="
                background-color: rgba(255, 255, 255, 0.8);
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
                width: 400px;">
                📅 Aujourd'hui : {date.today().strftime("%d/%m/%Y")}<br>
                📍 <b>{address}</b><br>
                ✅ {etat_qpv} : {qpv_name}<br>
                📏 Distance : {distance_m} mètres <br>
                🔗 <a href="https://public.opendatasoft.com/api/explore/v2.1/console" target="_blank" style="color:blue; text-decoration:none;">
                    Source OpenDataSoft
                    </a>
            </div>
        """
        # Ajouter le texte comme un "marqueur invisible" sur la carte
        folium.Marker(
            location=(lat, lon),  # Position sur la carte
            icon=DivIcon(
                icon_size=(350, 50),  # Taille de l'affichage
                icon_anchor=(0, 0),  # Ancrage en haut à gauche
                html=info_text,  # Contenu HTML
            ),
        ).add_to(m)
        
        # Créer des fichiers temporaires pour la génération
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_map_file = os.path.join(temp_dir, f"map_{nouvel_adre}.html")
            temp_image_file = os.path.join(temp_dir, f"map_{nouvel_adre}.png")
            
            # Sauvegarde HTML et image dans le répertoire temporaire
            m.save(temp_map_file)
            save_map_as_image(temp_map_file, temp_image_file)
            
            # Sauvegarder via FileUploadService si programme_code et subfolder_id sont fournis
            maps_url = None
            img_url = None
            encoded_image = None
            
            if programme_code and subfolder_id:
                try:
                    # Sauvegarder la carte HTML
                    from fastapi import UploadFile
                    from io import BytesIO
                    
                    # Lire le fichier HTML
                    with open(temp_map_file, 'rb') as f:
                        html_content = f.read()
                    html_file = UploadFile(
                        filename=f"map_{nouvel_adre}.html",
                        file=BytesIO(html_content)
                    )
                    
                    # Sauvegarder la carte HTML dans uploads/ (document)
                    map_info = await FileUploadService.save_file_async(
                        file=html_file,
                        resource_type="document",
                        folder_name="QPV",
                        programme_code=programme_code,
                        subfolder_id=subfolder_id
                    )
                    maps_url = map_info.get("file_url", "")
                    
                    # Lire l'image PNG
                    with open(temp_image_file, 'rb') as f:
                        image_content = f.read()
                    image_file = UploadFile(
                        filename=f"map_{nouvel_adre}.png",
                        file=BytesIO(image_content)
                    )
                    
                    # Sauvegarder l'image via save_media_file
                    image_info = await FileUploadService.save_media_file(
                        file=image_file,
                        media_type="qpv_map",
                        programme_code=programme_code,
                        subfolder_id=subfolder_id
                    )
                    img_url = image_info.get("file_url", "")
                    
                    # Encoder l'image en base64 pour la réponse (utilisé ailleurs dans l'application)
                    encoded_image = _encode_file_to_base64(temp_image_file)
                    
                except Exception as e:
                    print(f"⚠️ [QPV] Erreur lors de la sauvegarde via FileUploadService: {e}")
                    # Fallback vers l'ancien système si erreur
                    maps_url = f"/static/maps/map_{nouvel_adre}.html"
                    img_url = f"/static/images/map_{nouvel_adre}.png"
                    if os.path.exists(temp_image_file):
                        encoded_image = _encode_file_to_base64(temp_image_file)
            else:
                # Fallback vers l'ancien système si pas de programme_code/subfolder_id
                map_file = os.path.join(settings.STATIC_MAPS_DIR, f"map_{nouvel_adre}.html")
                image_file = os.path.join(settings.STATIC_IMAGES_DIR, f"map_{nouvel_adre}.png")
                
                # Créer les répertoires s'ils n'existent pas
                os.makedirs(os.path.dirname(map_file), exist_ok=True)
                os.makedirs(os.path.dirname(image_file), exist_ok=True)
                
                # Copier les fichiers temporaires vers les répertoires statiques
                import shutil
                shutil.copy2(temp_map_file, map_file)
                shutil.copy2(temp_image_file, image_file)
                
                maps_url = f"/static/maps/map_{nouvel_adre}.html"
                img_url = f"/static/images/map_{nouvel_adre}.png"
                
                if os.path.exists(image_file):
                    encoded_image = _encode_file_to_base64(image_file)

        return {
            "address": address,
            "nom_qp": f'{etat_qpv}:{qpv_name}' if qpv_name else f'{etat_qpv}:',
            "distance_m": distance_m,
            "carte": maps_url if maps_url else "",  # Chemin relatif seulement (ex: /uploads/QPV/... ou /media/...)
            "image_url": img_url if img_url else "",  # Chemin relatif seulement (ex: /media/qpv_map/...)
            "image_encoded": f"data:image/png;base64,{encoded_image}" if encoded_image else ""  # Base64 pour utilisation ailleurs
        }
    
    else:
        
        # 🔥 Ajouter une couche de texte (affichage permanent)
        info_text = f"""
            <div style="
                background-color: rgba(255, 255, 255, 0.8);
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
                width: 400px;">
                📅 Aujourd'hui : {date.today().strftime("%d/%m/%Y")}<br>
                📍 <b>{address}</b><br>
                🚫 Quartier Prioritaire : Aucun QPV trouvé <br>
                🔗 <a href="https://public.opendatasoft.com/api/explore/v2.1/console" target="_blank" style="color:blue; text-decoration:none;">
                    Source OpenDataSoft
                    </a>
            </div>
        """
         # Ajouter le point de l'adresse à notre carte
        folium.Marker(
            location=(lat, lon),  # Position sur la carte
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)

        # Ajouter le texte comme un "marqueur invisible" sur la carte
        folium.Marker(
            location=(lat, lon),  # Position sur la carte
            icon=DivIcon(
                icon_size=(350, 50),  # Taille de l'affichage
                icon_anchor=(0, 0),  # Ancrage en haut à gauche
                html=info_text,  # Contenu HTML
            ),
        ).add_to(m)

        # Créer des fichiers temporaires pour la génération
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_map_file = os.path.join(temp_dir, f"map_{nouvel_adre}.html")
            temp_image_file = os.path.join(temp_dir, f"map_{nouvel_adre}.png")
            
            # Sauvegarde HTML et image dans le répertoire temporaire
            m.save(temp_map_file)
            save_map_as_image(temp_map_file, temp_image_file)
            
            # Sauvegarder via FileUploadService si programme_code et subfolder_id sont fournis
            maps_url = None
            img_url = None
            encoded_image = None
            
            if programme_code and subfolder_id:
                try:
                    # Sauvegarder la carte HTML
                    from fastapi import UploadFile
                    from io import BytesIO
                    
                    # Lire le fichier HTML
                    with open(temp_map_file, 'rb') as f:
                        html_content = f.read()
                    html_file = UploadFile(
                        filename=f"map_{nouvel_adre}.html",
                        file=BytesIO(html_content)
                    )
                    
                    # Sauvegarder la carte HTML dans uploads/ (document)
                    map_info = await FileUploadService.save_file_async(
                        file=html_file,
                        resource_type="document",
                        folder_name="QPV",
                        programme_code=programme_code,
                        subfolder_id=subfolder_id
                    )
                    maps_url = map_info.get("file_url", "")
                    
                    # Lire l'image PNG
                    with open(temp_image_file, 'rb') as f:
                        image_content = f.read()
                    image_file = UploadFile(
                        filename=f"map_{nouvel_adre}.png",
                        file=BytesIO(image_content)
                    )
                    
                    # Sauvegarder l'image via save_media_file dans media/
                    image_info = await FileUploadService.save_media_file(
                        file=image_file,
                        media_type="qpv_map",
                        programme_code=programme_code,
                        subfolder_id=subfolder_id
                    )
                    img_url = image_info.get("file_url", "")
                    
                    # Encoder l'image en base64 pour la réponse (utilisé ailleurs dans l'application)
                    encoded_image = _encode_file_to_base64(temp_image_file)
                    
                except Exception as e:
                    print(f"⚠️ [QPV] Erreur lors de la sauvegarde via FileUploadService: {e}")
                    # Fallback vers l'ancien système si erreur
                    maps_url = f"/static/maps/map_{nouvel_adre}.html"
                    img_url = f"/static/images/map_{nouvel_adre}.png"
                    if os.path.exists(temp_image_file):
                        encoded_image = _encode_file_to_base64(temp_image_file)
            else:
                # Fallback vers l'ancien système si pas de programme_code/subfolder_id
                map_file = os.path.join(settings.STATIC_MAPS_DIR, f"map_{nouvel_adre}.html")
                image_file = os.path.join(settings.STATIC_IMAGES_DIR, f"map_{nouvel_adre}.png")
                
                # Créer les répertoires s'ils n'existent pas
                os.makedirs(os.path.dirname(map_file), exist_ok=True)
                os.makedirs(os.path.dirname(image_file), exist_ok=True)
                
                # Copier les fichiers temporaires vers les répertoires statiques
                import shutil
                shutil.copy2(temp_map_file, map_file)
                shutil.copy2(temp_image_file, image_file)
                
                maps_url = f"/static/maps/map_{nouvel_adre}.html"
                img_url = f"/static/images/map_{nouvel_adre}.png"
                
                if os.path.exists(image_file):
                    encoded_image = _encode_file_to_base64(image_file)
            
        return {
            "address": address,
            "nom_qp": "Aucun QPV",
            "distance_m": "N/A",
            "carte": maps_url if maps_url else "",  # Chemin relatif seulement (ex: /uploads/QPV/... ou /media/...)
            "image_url": img_url if img_url else "",  # Chemin relatif seulement (ex: /media/qpv_map/...)
            "image_encoded": f"data:image/png;base64,{encoded_image}" if encoded_image else ""  # Base64 pour utilisation ailleurs
        }

def save_map_as_image(map_path, image_path):
    """Capture une image d'une page HTML avec Selenium headless."""
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Exécution sans interface graphique
    options.add_argument("--no-sandbox")  # Évite les erreurs de sandboxing
    options.add_argument("--disable-dev-shm-usage")  # Évite les problèmes de mémoire dans Docker
    options.add_argument("--window-size=800x600")  # Définit une taille fixe pour la capture
    options.add_argument("--disable-gpu")  # Désactive l'accélération GPU
    options.add_argument("--disable-software-rasterizer")  # Évite certains crashs graphiques

    # Installer automatiquement le bon ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        
        driver.get("file://" + os.path.abspath(map_path))  # Charger le fichier HTML

        # Attendre que le corps de la page soit chargé avant la capture
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        time.sleep(2)  # Attendre le rendu de la carte

        # Capture d'écran et enregistrement
        driver.save_screenshot(image_path)

        # Convertir et optimiser l’image avec Pillow
        img = Image.open(image_path)
        img = img.convert("RGB")
        img.save(image_path, "PNG", quality=95)

    except Exception as e:
        print(f"❌ Erreur lors de la capture : {e}")
    finally:
        driver.quit()  # Fermer le navigateur