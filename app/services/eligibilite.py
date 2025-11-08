# app/services/eligibilite.py
from datetime import date, datetime, timezone
from typing import Optional, Tuple
from fastapi import Request
from sqlmodel import Session, select
from sqlalchemy import text
import logging

from .service_qpv import verif_qpv
from ..models.base import Programme
from ..models.preinscription import Eligibilite

def entreprise_age_annees(date_creation: Optional[date]) -> Optional[float]:
    if not date_creation:
        return None
    today = date.today()
    delta = today.year - date_creation.year - ((today.month, today.day) < (date_creation.month, date_creation.day))
    return float(delta)

def parse_ca_intervalle(ca_string: Optional[str]) -> Optional[dict]:
    """
    Parse un intervalle de CA (ex: "10 000 - 50 000 €") et retourne les bornes min/max.
    Retourne None si impossible à parser.
    """
    if not ca_string or not ca_string.strip():
        return None
    
    try:
        # Nettoyer la chaîne (enlever €, espaces, etc.)
        ca_clean = ca_string.replace('€', '').replace(',', '').strip()
        
        # Chercher un intervalle (format: "min - max")
        if ' - ' in ca_clean:
            parts = ca_clean.split(' - ')
            if len(parts) == 2:
                min_val = float(parts[0].strip().replace(' ', ''))
                max_val = float(parts[1].strip().replace(' ', ''))
                return {"min": min_val, "max": max_val, "type": "intervalle"}
        
        # Chercher un seul nombre
        elif ca_clean.replace('.', '').replace('-', '').isdigit():
            val = float(ca_clean.replace(' ', ''))
            return {"min": val, "max": val, "type": "valeur_unique"}
        
        return None
    except (ValueError, AttributeError):
        return None

def compare_ca_intervalles(ca_declare: Optional[str], ca_min_prog: Optional[float], ca_max_prog: Optional[float]) -> bool:
    """
    Compare l'intervalle de CA déclaré avec les seuils du programme.
    Retourne True si l'intervalle déclaré est compatible avec les critères du programme.
    """
    if not ca_declare:
        return True  # Pas de CA déclaré = pas de contrainte
    
    ca_parsed = parse_ca_intervalle(ca_declare)
    if not ca_parsed:
        return True  # Impossible à parser = pas de contrainte
    
    ca_declare_min = ca_parsed["min"]
    ca_declare_max = ca_parsed["max"]
    
    # Si le programme n'a pas de seuils, tout est accepté
    if ca_min_prog is None and ca_max_prog is None:
        return True
    
    # Vérifier la compatibilité des intervalles
    # L'intervalle déclaré doit chevaucher avec l'intervalle accepté par le programme
    
    # Cas 1: Seuil minimum seulement
    if ca_min_prog is not None and ca_max_prog is None:
        return ca_declare_max >= ca_min_prog  # Le max déclaré doit être >= seuil min
    
    # Cas 2: Seuil maximum seulement  
    if ca_min_prog is None and ca_max_prog is not None:
        return ca_declare_min <= ca_max_prog  # Le min déclaré doit être <= seuil max
    
    # Cas 3: Intervalle complet (min et max)
    if ca_min_prog is not None and ca_max_prog is not None:
        # Il faut qu'il y ait un chevauchement entre les intervalles
        return ca_declare_min <= ca_max_prog and ca_declare_max >= ca_min_prog
    
    return True

async def evaluate_eligibilite(
    adresse_perso: Optional[str],
    adresse_entreprise: Optional[str],
    chiffre_affaires: Optional[str],
    anciennete_annees: Optional[int],
    programme_id: int,
    session: Session,
    request: Request,
    preinscription_id: Optional[int] = None,
    schema_name: Optional[str] = None
) -> Tuple[str, dict]:
    """
    Retourne (verdict, details) avec verdict in {"ok","attention","ko"}.
    La règle illustrative :
      - QPV OK si l'une des deux adresses est QPV (vérifié avec verif_qpv)
      - CA dans [min, max] si min/max définis dans le programme
      - Ancienneté >= seuil si défini dans le programme
      - "ok" si tout est bon, "attention" si partiel, "ko" sinon
    
    Si preinscription_id et schema_name sont fournis, enregistre automatiquement
    l'éligibilité dans la table si elle n'existe pas déjà.
    
    Args:
        adresse_perso: Adresse personnelle du candidat
        adresse_entreprise: Adresse de l'entreprise
        chiffre_affaires: Chiffre d'affaires déclaré (string, peut être un intervalle)
        anciennete_annees: Ancienneté de l'entreprise en années
        programme_id: ID du programme (table programme dans schéma public)
        session: Session SQLModel pour accéder à la base de données
        request: Request FastAPI pour verif_qpv
        preinscription_id: ID de la préinscription (optionnel, pour enregistrement automatique)
        schema_name: Nom du schéma où enregistrer l'éligibilité (optionnel, ex: "acd", "act")
    """
    # Récupérer le programme depuis la base de données
    programme = session.get(Programme, programme_id)
    if not programme:
        raise ValueError(f"Programme avec id {programme_id} introuvable")
    
    # Utiliser les seuils du programme
    ca_min = programme.ca_seuil_min
    ca_max = programme.ca_seuil_max
    anciennete_min_annees = programme.anciennete_min_annees
    anciennete_max_annees = programme.anciennete_max_annees
    
    # Initialiser les variables QPV
    qpv_nom = "Aucun QPV"
    qpv_ok_result = False
    qpv_carte_url = None
    qpv_image_url = None
    
    if adresse_perso:
        try:
            logging.info(f"🔍 [QPV] Vérification QPV pour adresse personnelle: {adresse_perso}")
            # Extraire programme_code depuis schema_name si disponible
            programme_code_for_qpv = schema_name.upper() if schema_name and schema_name != "public" else None
            result_qpv_perso = await verif_qpv(
                {"address": adresse_perso}, 
                request,
                programme_code=programme_code_for_qpv,
                subfolder_id=preinscription_id
            )
            logging.info(f"📦 [QPV] Résultat complet QPV adresse personnelle: {result_qpv_perso}")
            
            # Vérifier s'il y a une erreur dans le résultat
            if result_qpv_perso and "error" in result_qpv_perso:
                logging.warning(f"⚠️ [QPV] Erreur dans le résultat QPV adresse personnelle: {result_qpv_perso.get('error')}")
            elif result_qpv_perso:
                nom_qp = result_qpv_perso.get("nom_qp", "")
                logging.info(f"🏘️ [QPV] nom_qp extrait (adresse personnelle): '{nom_qp}' (type: {type(nom_qp)})")
                
                # Vérifier si nom_qp commence par "QPV" ou "QPV limit"
                if nom_qp:
                    # Le format peut être "QPV:Nom" ou "QPV limit:Nom" ou "Aucun QPV"
                    if nom_qp.startswith("QPV"):
                        qpv_nom = nom_qp
                        qpv_ok_result = True
                        # Extraire les URLs de la première adresse QPV trouvée
                        qpv_carte_url = result_qpv_perso.get("carte", "")
                        qpv_image_url = result_qpv_perso.get("image_url", "")
                        logging.info(f"✅ [QPV] QPV trouvé pour adresse personnelle: {qpv_nom}, Carte: {qpv_carte_url}, Image: {qpv_image_url}")
                    else:
                        logging.info(f"ℹ️ [QPV] Pas de QPV pour adresse personnelle (nom_qp: '{nom_qp}')")
                else:
                    logging.warning(f"⚠️ [QPV] nom_qp vide pour adresse personnelle")
            else:
                logging.warning(f"⚠️ [QPV] Résultat QPV vide pour adresse personnelle")
        except Exception as e:
            logging.error(f"❌ [QPV] Erreur lors de la vérification QPV adresse personnelle: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    if not qpv_ok_result and adresse_entreprise:
        try:
            logging.info(f"🔍 [QPV] Vérification QPV pour adresse entreprise: {adresse_entreprise}")
            # Extraire programme_code depuis schema_name si disponible
            programme_code_for_qpv = schema_name.upper() if schema_name and schema_name != "public" else None
            result_qpv_entreprise = await verif_qpv(
                {"address": adresse_entreprise}, 
                request,
                programme_code=programme_code_for_qpv,
                subfolder_id=preinscription_id
            )
            logging.info(f"📦 [QPV] Résultat complet QPV adresse entreprise: {result_qpv_entreprise}")
            
            # Vérifier s'il y a une erreur dans le résultat
            if result_qpv_entreprise and "error" in result_qpv_entreprise:
                logging.warning(f"⚠️ [QPV] Erreur dans le résultat QPV adresse entreprise: {result_qpv_entreprise.get('error')}")
            elif result_qpv_entreprise:
                nom_qp = result_qpv_entreprise.get("nom_qp", "")
                logging.info(f"🏘️ [QPV] nom_qp extrait (adresse entreprise): '{nom_qp}' (type: {type(nom_qp)})")
                
                # Vérifier si nom_qp commence par "QPV" ou "QPV limit"
                if nom_qp:
                    # Le format peut être "QPV:Nom" ou "QPV limit:Nom" ou "Aucun QPV"
                    if nom_qp.startswith("QPV"):
                        qpv_nom = nom_qp
                        qpv_ok_result = True
                        # Extraire les URLs de la première adresse QPV trouvée
                        qpv_carte_url = result_qpv_entreprise.get("carte", "")
                        qpv_image_url = result_qpv_entreprise.get("image_url", "")
                        logging.info(f"✅ [QPV] QPV trouvé pour adresse entreprise: {qpv_nom}, Carte: {qpv_carte_url}, Image: {qpv_image_url}")
                    else:
                        logging.info(f"ℹ️ [QPV] Pas de QPV pour adresse entreprise (nom_qp: '{nom_qp}')")
                else:
                    logging.warning(f"⚠️ [QPV] nom_qp vide pour adresse entreprise")
            else:
                logging.warning(f"⚠️ [QPV] Résultat QPV vide pour adresse entreprise")
        except Exception as e:
            logging.error(f"❌ [QPV] Erreur lors de la vérification QPV adresse entreprise: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    logging.info(f"📊 [QPV] Résultat final QPV: nom='{qpv_nom}', ok={qpv_ok_result}, carte_url={qpv_carte_url}, image_url={qpv_image_url}")

    # Comparer les intervalles de CA
    try:
        ca_ok = compare_ca_intervalles(chiffre_affaires, ca_min, ca_max)
    except Exception as e:
        logging.warning(f"Erreur lors de la comparaison des intervalles de CA: {e}")
        ca_ok = False
    
    # Parser le CA pour l'affichage (garder l'intervalle original)
    try:
        ca_parsed = parse_ca_intervalle(chiffre_affaires)
    except Exception as e:
        logging.warning(f"Erreur lors du parsing du CA: {e}")
        ca_parsed = None

    anc_ok = True
    # Vérifier l'ancienneté
    try:
        if anciennete_min_annees and anciennete_max_annees:
            anc_ok = (anciennete_annees or 0) >= anciennete_min_annees and (anciennete_annees or 0) <= anciennete_max_annees
        elif anciennete_min_annees:
            anc_ok = (anciennete_annees or 0) >= anciennete_min_annees
    except Exception as e:
        logging.warning(f"Erreur lors de la vérification de l'ancienneté: {e}")
        anc_ok = False

    score = sum([1 if qpv_ok_result else 0, 1 if ca_ok else 0, 1 if anc_ok else 0])
    verdict = "ok" if score == 3 else ("attention" if score == 2 else "ko")

    # Construire les chaînes de condition pour le stockage
    ca_condition_str = None
    if ca_parsed:
        ca_declare_min = ca_parsed["min"]
        ca_declare_max = ca_parsed["max"]
        
        # Pour un intervalle, on prend la valeur min pour la condition
        ca_declare_val = ca_declare_min
        
        if ca_min is not None and ca_max is not None and ca_declare_val >= ca_min and ca_declare_val <= ca_max:
            ca_condition_str = f"{ca_min} <= {ca_declare_val:.0f} <= {ca_max}"
        elif ca_min is not None and ca_declare_val >= ca_min:
            ca_condition_str = f"{ca_declare_val:.0f} >= {ca_min}"
        elif ca_max is not None and ca_declare_val <= ca_max:
            ca_condition_str = f"{ca_declare_val:.0f} <= {ca_max}"
        else:
            ca_condition_str = f"{ca_declare_val:.0f}"
    elif chiffre_affaires:
        ca_condition_str = chiffre_affaires  # Stocker la valeur originale si pas de seuils

    anciennete_condition_str = None
    if anciennete_annees is not None:
        if anciennete_min_annees is not None and anciennete_max_annees is not None and anciennete_annees >= anciennete_min_annees and anciennete_annees <= anciennete_max_annees:
            anciennete_condition_str = f"{anciennete_min_annees} <= {anciennete_annees} <= {anciennete_max_annees}"
        elif anciennete_min_annees is not None and anciennete_annees >= anciennete_min_annees:
            anciennete_condition_str = f"{anciennete_annees} >= {anciennete_min_annees}"
        elif anciennete_max_annees is not None and anciennete_annees <= anciennete_max_annees:
            anciennete_condition_str = f"{anciennete_annees} <= {anciennete_max_annees}"
        else:
            anciennete_condition_str = str(anciennete_annees)

    details = {
        "qpv_ok": qpv_nom,  # Stocker le texte nom_qp au lieu du booléen
        "qpv_ok_bool": qpv_ok_result,  # Garder le booléen pour le calcul du score
        "ca_ok": ca_ok,
        "anciennete_ok": anc_ok,
        "ca_decl": chiffre_affaires,  # Intervalle original
        "ca_parsed": ca_parsed,  # Données parsées (min, max, type)
        "anciennete_annees": anciennete_annees,
        "ca_condition": ca_condition_str,  # Condition CA formatée
        "anciennete_condition": anciennete_condition_str  # Condition ancienneté formatée
    }
    
    # Enregistrer automatiquement dans la table si preinscription_id et schema_name sont fournis
    if preinscription_id and schema_name:
        try:
            # Vérifier si une éligibilité existe déjà pour cette préinscription
            # Utiliser une requête SQL directe avec le schéma explicite
            check_query = text(f"""
                SELECT id FROM {schema_name}.eligibilite 
                WHERE preinscription_id = :preinscription_id
            """)
            existing = session.execute(check_query.bindparams(preinscription_id=preinscription_id)).first()
            
            if not existing:
                # Convertir les booléens en strings pour correspondre au modèle Eligibilite
                ca_seuil_ok_str = "true" if ca_ok else "false"
                anciennete_ok_str = "true" if anc_ok else "false"
                
                # Insérer l'éligibilité dans le schéma du programme
                insert_query = text(f"""
                    INSERT INTO {schema_name}.eligibilite 
                    (preinscription_id, ca_seuil_ok, ca_score, qpv_ok, qpv_carte_url, qpv_image_url, anciennete_ok, anciennete_annees, verdict, calcule_le) 
                    VALUES (:preinscription_id, :ca_seuil_ok, :ca_score, :qpv_ok, :qpv_carte_url, :qpv_image_url, :anciennete_ok, :anciennete_annees, :verdict, :calcule_le)
                """)
                session.execute(insert_query.bindparams(
                    preinscription_id=preinscription_id,
                    ca_seuil_ok=ca_seuil_ok_str,
                    ca_score=ca_condition_str,  # Stocker la condition CA (ex: "50000 <= 75000 <= 100000")
                    qpv_ok=details.get("qpv_ok"),
                    qpv_carte_url=qpv_carte_url,
                    qpv_image_url=qpv_image_url,
                    anciennete_ok=anciennete_ok_str,
                    anciennete_annees=anciennete_condition_str,  # Stocker la condition ancienneté (ex: "2 >= 3" ou "2 <= 5")
                    verdict=verdict,
                    calcule_le=datetime.now(timezone.utc)
                ))
                session.commit()
                logging.info(f"✅ Éligibilité enregistrée avec succès pour preinscription_id: {preinscription_id}")
            else:
                # Mettre à jour l'éligibilité existante avec les nouvelles valeurs calculées
                ca_seuil_ok_str = "true" if ca_ok else "false"
                anciennete_ok_str = "true" if anc_ok else "false"
                
                update_query = text(f"""
                    UPDATE {schema_name}.eligibilite 
                    SET ca_seuil_ok = :ca_seuil_ok,
                        ca_score = :ca_score,
                        qpv_ok = :qpv_ok,
                        qpv_carte_url = :qpv_carte_url,
                        qpv_image_url = :qpv_image_url,
                        anciennete_ok = :anciennete_ok,
                        anciennete_annees = :anciennete_annees,
                        verdict = :verdict,
                        calcule_le = :calcule_le
                    WHERE preinscription_id = :preinscription_id
                """)
                session.execute(update_query.bindparams(
                    preinscription_id=preinscription_id,
                    ca_seuil_ok=ca_seuil_ok_str,
                    ca_score=ca_condition_str,
                    qpv_ok=details.get("qpv_ok"),
                    qpv_carte_url=qpv_carte_url,
                    qpv_image_url=qpv_image_url,
                    anciennete_ok=anciennete_ok_str,
                    anciennete_annees=anciennete_condition_str,
                    verdict=verdict,
                    calcule_le=datetime.now(timezone.utc)
                ))
                session.commit()
                logging.info(f"✅ Éligibilité mise à jour avec succès pour preinscription_id: {preinscription_id}")
        except Exception as e:
            # Ne pas faire échouer la fonction si l'enregistrement échoue
            # Les erreurs seront loggées mais la fonction retournera quand même les résultats
            logging.error(f"❌ Erreur lors de l'enregistrement automatique de l'éligibilité (preinscription_id={preinscription_id}, schema={schema_name}): {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    return verdict, details
