"""
Script d'initialisation des pipelines par défaut
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app_lia_web.core.database import engine
from app_lia_web.app.models.base import Programme, EtapePipeline

# Pipelines par défaut pour chaque programme
PIPELINES_DEFAUT = {
    "ACD": [
        {"code": "accueil", "libelle": "Accueil et présentation", "type_etape": "formation", "ordre": 1},
        {"code": "evaluation_besoins", "libelle": "Évaluation des besoins", "type_etape": "evaluation", "ordre": 2},
        {"code": "plan_action", "libelle": "Plan d'action personnalisé", "type_etape": "accompagnement", "ordre": 3},
        {"code": "accompagnement", "libelle": "Accompagnement individuel", "type_etape": "accompagnement", "ordre": 4},
        {"code": "evaluation_intermediaire", "libelle": "Évaluation intermédiaire", "type_etape": "evaluation", "ordre": 5},
        {"code": "finalisation", "libelle": "Finalisation", "type_etape": "formation", "ordre": 6},
        {"code": "presentation_finale", "libelle": "Présentation finale", "type_etape": "evaluation", "ordre": 7},
        {"code": "suivi_post", "libelle": "Suivi post-formation", "type_etape": "accompagnement", "ordre": 8}
    ],
    "ACI": [
        {"code": "accueil_aci", "libelle": "Accueil et intégration", "type_etape": "formation", "ordre": 1},
        {"code": "diagnostic", "libelle": "Diagnostic initial", "type_etape": "evaluation", "ordre": 2},
        {"code": "formation_theorique", "libelle": "Formation théorique", "type_etape": "formation", "ordre": 3},
        {"code": "ateliers", "libelle": "Ateliers pratiques", "type_etape": "formation", "ordre": 4},
        {"code": "projet_personnel", "libelle": "Projet personnel", "type_etape": "accompagnement", "ordre": 5},
        {"code": "presentation_projet", "libelle": "Présentation du projet", "type_etape": "evaluation", "ordre": 6},
        {"code": "certification", "libelle": "Certification", "type_etape": "evaluation", "ordre": 7}
    ],
    "ACT": [
        {"code": "selection", "libelle": "Sélection et admission", "type_etape": "evaluation", "ordre": 1},
        {"code": "formation_intensive", "libelle": "Formation intensive", "type_etape": "formation", "ordre": 2},
        {"code": "projet_entreprise", "libelle": "Projet d'entreprise", "type_etape": "accompagnement", "ordre": 3},
        {"code": "pitch_final", "libelle": "Pitch final", "type_etape": "evaluation", "ordre": 4},
        {"code": "suivi_post_act", "libelle": "Accompagnement post-formation", "type_etape": "accompagnement", "ordre": 5}
    ]
}

def init_pipelines():
    """Initialise les pipelines par défaut pour tous les programmes"""
    with Session(engine) as session:
        # Récupérer tous les programmes
        programmes = session.exec(select(Programme)).all()
        
        for programme in programmes:
            print(f"Initialisation du pipeline pour {programme.nom} ({programme.code})")
            
            # Vérifier si le pipeline existe déjà
            etapes_existantes = session.exec(
                select(EtapePipeline).where(EtapePipeline.programme_id == programme.id)
            ).all()
            
            if etapes_existantes:
                print(f"  Pipeline déjà existant ({len(etapes_existantes)} étapes), passage au suivant")
                continue
            
            # Récupérer les étapes par défaut pour ce programme
            etapes_defaut = PIPELINES_DEFAUT.get(programme.code, [])
            
            if not etapes_defaut:
                print(f"  Aucun pipeline par défaut trouvé pour {programme.code}")
                continue
            
            # Créer les étapes du pipeline
            for etape_data in etapes_defaut:
                etape = EtapePipeline(
                    programme_id=programme.id,
                    code=etape_data["code"],
                    libelle=etape_data["libelle"],
                    type_etape=etape_data["type_etape"],
                    ordre=etape_data["ordre"],
                    active=True
                )
                session.add(etape)
            
            session.commit()
            print(f"  ✅ Pipeline créé avec {len(etapes_defaut)} étapes")

def afficher_pipelines():
    """Affiche tous les pipelines existants"""
    with Session(engine) as session:
        programmes = session.exec(select(Programme)).all()
        
        for programme in programmes:
            print(f"\n📋 Pipeline {programme.nom} ({programme.code}):")
            
            etapes = session.exec(
                select(EtapePipeline)
                .where(EtapePipeline.programme_id == programme.id)
                .order_by(EtapePipeline.ordre)
            ).all()
            
            if not etapes:
                print("  Aucune étape configurée")
                continue
            
            for etape in etapes:
                statut = "✅" if etape.active else "❌"
                print(f"  {statut} {etape.ordre}. {etape.libelle} ({etape.code})")
                if etape.type_etape:
                    print(f"      Type: {etape.type_etape}")

if __name__ == "__main__":
    print("🚀 Initialisation des pipelines par défaut")
    print("=" * 50)
    
    # Initialiser les pipelines
    init_pipelines()
    
    print("\n" + "=" * 50)
    print("📊 État des pipelines après initialisation:")
    afficher_pipelines()
    
    print("\n✅ Initialisation terminée !")
