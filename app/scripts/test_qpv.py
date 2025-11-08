#!/usr/bin/env python3
"""
Script simple pour tester le service QPV
Usage: python scripts/test_qpv.py "adresse complète"
"""
import sys
import requests
from geopy.distance import geodesic
from shapely.geometry import Point, Polygon

# Configuration
DISTANCE_QPV_LIMITE = 300  # Distance en mètres pour considérer un QPV limitrophe


def test_qpv(address: str):
    """
    Teste si une adresse est dans un QPV
    Retourne un dictionnaire avec les résultats
    """
    print(f"\n{'='*60}")
    print(f"🔍 TEST QPV")
    print(f"{'='*60}")
    print(f"📍 Adresse: {address}")
    print(f"{'='*60}\n")
    
    # Validation de l'adresse
    if not address or len(address) < 5 or len(address.split()) < 3:
        result = {
            "error": "Adresse invalide",
            "nom_qp": "Aucun QPV",
            "is_qpv": False
        }
        print(f"❌ Erreur: {result['error']}\n")
        return result
    
    # Géocodage
    print("⏳ Géocodage en cours...")
    url = f"https://api-adresse.data.gouv.fr/search/?q={address.replace(' ', '+')}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("features"):
            result = {
                "error": "Aucune coordonnée GPS trouvée",
                "nom_qp": "Aucun QPV",
                "is_qpv": False
            }
            print(f"❌ Erreur: {result['error']}\n")
            return result
        
        coords = data["features"][0]["geometry"]["coordinates"]
        lat = coords[1]
        lon = coords[0]
        print(f"✅ Coordonnées trouvées: {lat}, {lon}")
        
    except Exception as e:
        result = {
            "error": f"Erreur API géocodage: {str(e)}",
            "nom_qp": "Aucun QPV",
            "is_qpv": False
        }
        print(f"❌ Erreur: {result['error']}\n")
        return result
    
    # Vérification QPV
    print(f"⏳ Recherche QPV dans un rayon de 0.3km...")
    urlqpv = f"https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/quartiers-prioritaires-de-la-politique-de-la-ville-qpv/records?where=within_distance(geo_shape, geom'POINT({lon} {lat})', 0.3km)"
    
    try:
        response = requests.get(urlqpv, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        records = data.get("results", [])
        if not records:
            result = {
                "address": address,
                "nom_qp": "Aucun QPV",
                "is_qpv": False,
                "lat": lat,
                "lon": lon
            }
            print(f"✅ Aucun QPV trouvé\n")
            return result
        
        print(f"✅ {len(records)} QPV trouvé(s)")
        
        # Vérifier si le point est dans le polygone QPV
        record = records[0]
        if "geo_shape" in record and "geometry" in record["geo_shape"]:
            coord_qpv = record["geo_shape"]["geometry"]["coordinates"][0]
            
            # Extraire le nom du QPV (structure de l'API OpenDataSoft)
            qpv_name = "QPV"
            # L'API OpenDataSoft retourne les données dans record.fields
            if "record" in record:
                fields = record.get("record", {}).get("fields", {})
                if "nom_qp" in fields:
                    qpv_name = fields["nom_qp"]
            # Sinon chercher directement dans le record
            elif "fields" in record and "nom_qp" in record["fields"]:
                qpv_name = record["fields"]["nom_qp"]
            elif "nom_qp" in record:
                qpv_name = record["nom_qp"]
            
            print(f"   Nom du QPV extrait: {qpv_name}")
            
            if coord_qpv and isinstance(coord_qpv, list) and len(coord_qpv) > 2:
                point_coords = (lat, lon)
                address_point = Point(point_coords[::-1])  # Shapely utilise (lon, lat)
                polygon = Polygon(coord_qpv)
                
                # Si le point est dans le polygone, c'est un QPV
                if polygon.contains(address_point):
                    result = {
                        "address": address,
                        "nom_qp": f"QPV:{qpv_name}",
                        "is_qpv": True,
                        "lat": lat,
                        "lon": lon,
                        "distance_m": 0
                    }
                    print(f"✅ Point dans le QPV\n")
                    return result
                
                # Si le point est proche (dans la limite de distance), considérer comme QPV
                nearest_point = polygon.exterior.interpolate(polygon.exterior.project(address_point))
                nearest_coords = (nearest_point.y, nearest_point.x)
                distance_km = geodesic(point_coords, nearest_coords).kilometers
                distance_m = round(distance_km * 1000)
                
                if distance_m <= DISTANCE_QPV_LIMITE:
                    result = {
                        "address": address,
                        "nom_qp": f"QPV limit:{qpv_name}",
                        "is_qpv": True,
                        "lat": lat,
                        "lon": lon,
                        "distance_m": distance_m
                    }
                    print(f"✅ QPV limitrophe à {distance_m}m\n")
                    return result
        
        result = {
            "address": address,
            "nom_qp": "Aucun QPV",
            "is_qpv": False,
            "lat": lat,
            "lon": lon
        }
        print(f"✅ Aucun QPV (trop loin)\n")
        return result
        
    except Exception as e:
        result = {
            "error": f"Erreur API QPV: {str(e)}",
            "nom_qp": "Aucun QPV",
            "is_qpv": False
        }
        print(f"❌ Erreur: {result['error']}\n")
        return result


def main():
    """Point d'entrée"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_qpv.py \"adresse complète\"")
        print("\nExemple:")
        print('  python scripts/test_qpv.py "15 bis rue Paul cezanne, 93600 Aulnay-sous-bois"')
        sys.exit(1)
    
    address = sys.argv[1]
    result = test_qpv(address)
    
    # Afficher les résultats
    print(f"{'='*60}")
    print("📊 RÉSULTATS")
    print(f"{'='*60}\n")
    
    if "error" in result:
        print(f"❌ Erreur: {result['error']}")
    else:
        print(f"📍 Adresse: {result.get('address', 'N/A')}")
        
        if result.get('lat') and result.get('lon'):
            print(f"🗺️  Coordonnées: {result['lat']}, {result['lon']}")
        
        nom_qp = result.get('nom_qp', '')
        print(f"🏘️  Quartier Prioritaire: {nom_qp}")
        
        if result.get('distance_m') is not None:
            print(f"📏 Distance: {result.get('distance_m')} mètres")
        
        # Résultat final
        if result.get('is_qpv'):
            print(f"\n✅ RÉSULTAT: C'EST UN QPV")
            if ':' in nom_qp:
                qpv_name = nom_qp.split(':', 1)[1]
                print(f"   Nom: {qpv_name}")
            if result.get('distance_m', 0) > 0:
                print(f"   (QPV limitrophe à {result['distance_m']} mètres)")
        else:
            print(f"\n❌ RÉSULTAT: Ce n'est PAS un QPV")
    
    print(f"\n{'='*60}\n")
    
    # Afficher le JSON brut
    print("📄 JSON retourné:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    sys.exit(0 if not result.get('error') else 1)


if __name__ == "__main__":
    main()
