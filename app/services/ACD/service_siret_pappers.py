from fastapi import Request, HTTPException
import csv
import os
import requests

from app_lia_web.core.config import settings
from app_lia_web.app.services.file_upload_service import FileUploadService

FileUploadService = FileUploadService()
      
async def get_entreprise_process(numero_siret: str, request: Request):
    base_url = settings.get_base_url(request)
    print(f"🚀 [SERVICE] Début get_entreprise_process pour SIRET: {numero_siret}")
    print(f"🔑 [SERVICE] Utilisation de l'API key: {settings.PAPPERS_API_KEY[:5]}...")
 
    url = f"https://api.pappers.fr/v2/entreprise?siren={numero_siret}&api_token={settings.PAPPERS_API_KEY}"
    print(f"🌐 [SERVICE] Appel API Pappers: {url}")

    try:
        print("📡 [SERVICE] Envoi de la requête à l'API Pappers...")
        response = requests.get(url)
        print(f"📥 [SERVICE] Réponse reçue - Status: {response.status_code}")
        
        if response.status_code == 404:
            print("❌ [SERVICE] Entreprise non trouvée (404)")
            return {
                "message": "Entreprise non trouvée",
                "entreprise_data": None,
                "status_code": 404
            }
            
        response.raise_for_status()
        data = response.json()
        
        # Ajout de logs détaillés pour la réponse
        print("🔍 [SERVICE] Réponse brute de l'API Pappers:")
        print(f"📄 [SERVICE] SIREN: {data.get('siren')}")
        print(f"📄 [SERVICE] Nom entreprise: {data.get('nom_entreprise')}")
        print(f"📄 [SERVICE] Dénomination: {data.get('denomination')}")
        print(f"📄 [SERVICE] Forme juridique: {data.get('forme_juridique')}")
        print(f"📄 [SERVICE] Date création: {data.get('date_creation')}")
        print(f"📄 [SERVICE] Code NAF: {data.get('code_naf')}")
        print(f"📄 [SERVICE] Siège: {data.get('siege')}")
        print(f"✅ [SERVICE] Données JSON reçues: {bool(data)}")
               
        if not data.get("siren"):
            print("❌ [SERVICE] Entreprise non trouvée dans la réponse")
            return {
                "message": "Entreprise non trouvée dans la réponse",
                "entreprise_data": None,
                "status_code": 404
            }

        # Vérification de la diffusion des données
        if not data.get("diffusable", True):
            print("⚠️ [SERVICE] Données non diffusables")
            return {
                "message": "Les données de cette entreprise ne sont pas diffusables",
                "entreprise_data": None,
                "status_code": 403
            }


    except requests.exceptions.HTTPError as e:
        print(f"❌ [SERVICE] Erreur HTTP: {str(e)}")
        return {
            "message": f"Erreur API Pappers : {str(e)}",
            "entreprise_data": None,
            "status_code": response.status_code
        }

    except requests.exceptions.RequestException as e:
        print(f"❌ [SERVICE] Erreur de connexion: {str(e)}")
        return {
            "message": f"Erreur de connexion à Pappers : {str(e)}",
            "entreprise_data": None,
            "status_code": 500
        }

    try:
        
        print(f"🌐 [SERVICE] URL de base: {base_url}")
        csv_url = os.path.join(settings.FICHIERS_DIR, "entreprise_data.csv")
        print(f"📁 [SERVICE] Chemin du fichier CSV: {csv_url}")

        print("📊 [SERVICE] Traitement des données comptables...")
        comptes = data.get("comptes", [])
        print(f"📈 [SERVICE] Nombre total de comptes trouvés: {len(comptes)}")
        
        comptes_disponibles = [
            compte for compte in comptes if compte.get("nom_fichier_pdf") is not None
        ]
        print(f"📊 [SERVICE] Nombre de comptes avec PDF disponibles: {len(comptes_disponibles)}")

        print("📝 [SERVICE] Génération du fichier CSV...")
        with open(csv_url, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            writer.writerow([
                "Nom Entreprise", "Siret", "Adresse", "Effectif",
                "Date Création", "Code NAF", "Activité",
                "Année clôture", "Date dépôt", "Type comptes",
                "Nom fichier PDF", "Tokens"
            ])

            for compte in comptes_disponibles:
                writer.writerow([
                    data.get("nom_entreprise", "N/A"),
                    data["siege"].get("siret", "Adresse non disponible"),
                    data["siege"].get("adresse", "Adresse non disponible"),
                    data.get("effectif", "Non renseigné"),
                    data.get("date_creation", "N/A"),
                    data.get("code_naf", "N/A"),
                    data.get("activite", "N/A"),
                    compte.get("annee_cloture", "N/A"),
                    compte.get("date_depot_formate", "N/A"),
                    compte.get("type_comptes", "N/A"),
                    compte.get("nom_fichier_pdf", "N/A"),
                    compte.get("token", "N/A")
                ])
        print("✅ [SERVICE] Fichier CSV généré avec succès")

        print("🔍 [SERVICE] Vérification de l'existence du fichier CSV...")
        if os.path.exists(csv_url):
            print("📄 [SERVICE] Encodage du fichier CSV en base64...")
            csv_base64 = FileUploadService.encode_file_to_base64(csv_url)
            print("✅ [SERVICE] Encodage CSV terminé")
        else:
            print("⚠️ [SERVICE] Fichier CSV non trouvé")
            csv_base64 = None

        pdf_path = f"{base_url}/fichiers/entreprise_data.csv"
        print(f"🔗 [SERVICE] URL de téléchargement générée: {pdf_path}")
       
        print("✨ [SERVICE] Préparation de la réponse finale...")
        
        # Vérification des données avant construction de la réponse
        print("🔍 [SERVICE] Vérification des données avant construction de la réponse:")
        for key in ["nom_entreprise", "denomination", "forme_juridique", "date_creation", "code_naf"]:
            print(f"📊 [SERVICE] {key}: {data.get(key)}")
        
        entreprise_info = {
            "siren": data.get("siren"),
            "siren_formate": data.get("siren_formate"),
            "nom_entreprise": data.get("nom_entreprise"),
            "denomination": data.get("denomination"),
            "forme_juridique": data.get("forme_juridique"),
            "date_creation": data.get("date_creation"),
            "date_creation_formate": data.get("date_creation_formate"),
            "capital": data.get("capital"),
            "capital_formate": data.get("capital_formate"),
            "code_naf": data.get("code_naf"),
            "libelle_code_naf": data.get("libelle_code_naf"),
            "activite": data.get("objet_social"),
            "effectif": data.get("effectif"),
            "effectif_min": data.get("effectif_min"),
            "effectif_max": data.get("effectif_max"),
            "annee_effectif": data.get("annee_effectif"),
            "tranche_effectif": data.get("tranche_effectif"),
            
            # Informations sur la radiation
            "entreprise_cessee": data.get("entreprise_cessee"),
            "date_cessation": data.get("date_cessation"),
            "date_cessation_formate": data.get("date_cessation_formate"),
            "statut_consolide": data.get("statut_consolide"),
            
            # Informations SIRENE
            "derniere_mise_a_jour_sirene": data.get("derniere_mise_a_jour_sirene"),
            "dernier_traitement": data.get("dernier_traitement"),
            "diffusable": data.get("diffusable"),
            "opposition_utilisation_commerciale": data.get("opposition_utilisation_commerciale"),
            
            # Informations RCS
            "statut_rcs": data.get("statut_rcs"),
            "greffe": data.get("greffe"),
            "numero_rcs": data.get("numero_rcs"),
            "date_immatriculation_rcs": data.get("date_immatriculation_rcs"),
            "date_radiation_rcs": data.get("date_radiation_rcs"),
            
            # Informations RNE
            "statut_rne": data.get("statut_rne"),
            "date_immatriculation_rne": data.get("date_immatriculation_rne"),
            "date_radiation_rne": data.get("date_radiation_rne"),
            
            # Informations TVA
            "numero_tva_intracommunautaire": data.get("numero_tva_intracommunautaire"),
            
            # Informations du siège
            "siege": {
                "adresse": data.get("siege", {}).get("adresse_ligne_1"),
                "code_postal": data.get("siege", {}).get("code_postal"),
                "ville": data.get("siege", {}).get("ville"),
                "siret": data.get("siege", {}).get("siret"),
                "siret_formate": data.get("siege", {}).get("siret_formate"),
                "type_etablissement": data.get("siege", {}).get("type_etablissement"),
                "date_de_creation": data.get("siege", {}).get("date_de_creation"),
                "etablissement_cesse": data.get("siege", {}).get("etablissement_cesse"),
                "date_cessation": data.get("siege", {}).get("date_cessation"),
                "latitude": data.get("siege", {}).get("latitude"),
                "longitude": data.get("siege", {}).get("longitude")
            },
            
            # Autres informations importantes
            "representants": data.get("representants", []),
            "beneficiaires_effectifs": data.get("beneficiaires_effectifs", []),
            "derniers_statuts": data.get("derniers_statuts"),
            "extrait_immatriculation": data.get("extrait_immatriculation"),
            "publications_bodacc": data.get("publications_bodacc", []),
            "depots_actes": data.get("depots_actes", []),
            "conventions_collectives": data.get("conventions_collectives", []),
            "comptes": comptes_disponibles,
            
            # Documents disponibles
            "documents_disponibles": {
                "comptes": comptes_disponibles,
                "statuts": data.get("derniers_statuts"),
                "extrait_immatriculation": data.get("extrait_immatriculation"),
                "publications_bodacc": data.get("publications_bodacc", []),
                "depots_actes": data.get("depots_actes", [])
            },
            
            # Informations supplémentaires
            "economie_sociale_solidaire": data.get("economie_sociale_solidaire"),
            "societe_a_mission": data.get("societe_a_mission"),
            "associe_unique": data.get("associe_unique"),
            "duree_personne_morale": data.get("duree_personne_morale"),
            "date_debut_activite": data.get("date_debut_activite"),
            "date_debut_premiere_activite": data.get("date_debut_premiere_activite"),
            "prochaine_date_cloture_exercice": data.get("prochaine_date_cloture_exercice"),
            "prochaine_date_cloture_exercice_formate": data.get("prochaine_date_cloture_exercice_formate")
        }
        
        print("📊 [SERVICE] Données de l'entreprise extraites avec succès")
        
        # Vérification de l'opposition à l'utilisation commerciale
        if data.get("opposition_utilisation_commerciale", False):
            print("⚠️ [SERVICE] Opposition à l'utilisation commerciale")
            return {
                "message": "Cette entreprise s'oppose à l'utilisation commerciale de ses données. Les informations affichées sont limitées.",
                "entreprise_data": entreprise_info,
                "status_code": 200,
                "opposition_commerciale": True
            }
        
        return {
            "message": "Données extraites avec succès",
            "entreprise_data": entreprise_info,
            "status_code": 200
        }

    except Exception as e:
        print(f"❌ [SERVICE] Erreur lors du traitement: {str(e)}")
        return {
            "message": f"Erreur lors du traitement des données : {str(e)}",
            "entreprise_data": None,
            "status_code": 500
        }


