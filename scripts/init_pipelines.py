"""
Script d'initialisation des pipelines par défaut
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app_lia_web.core.database import engine
from app_lia_web.app.models.base import Programme, EtapePipeline

# Pipelines par défaut pour chaque programme
PIPELINES_DEFAUT = {
    "ACD": [
        {"nom": "Accueil et présentation", "description": "Présentation du programme et des objectifs", "duree_estimee": 1, "ordre": 1},
        {"nom": "Évaluation des besoins", "description": "Analyse des besoins spécifiques du candidat", "duree_estimee": 2, "ordre": 2},
        {"nom": "Plan d'action personnalisé", "description": "Élaboration du plan d'action", "duree_estimee": 3, "ordre": 3},
        {"nom": "Accompagnement individuel", "description": "Sessions de coaching individuelles", "duree_estimee": 30, "ordre": 4},
        {"nom": "Évaluation intermédiaire", "description": "Bilan à mi-parcours", "duree_estimee": 2, "ordre": 5},
        {"nom": "Finalisation", "description": "Préparation de la présentation finale", "duree_estimee": 5, "ordre": 6},
        {"nom": "Présentation finale", "description": "Présentation devant le jury", "duree_estimee": 1, "ordre": 7},
        {"nom": "Suivi post-formation", "description": "Accompagnement post-formation", "duree_estimee": 90, "ordre": 8}
    ],
    "ACI": [
        {"nom": "Accueil et intégration", "description": "Présentation du programme ACI", "duree_estimee": 1, "ordre": 1},
        {"nom": "Diagnostic initial", "description": "Évaluation des compétences actuelles", "duree_estimee": 2, "ordre": 2},
        {"nom": "Formation théorique", "description": "Modules de formation théorique", "duree_estimee": 20, "ordre": 3},
        {"nom": "Ateliers pratiques", "description": "Mise en pratique des concepts", "duree_estimee": 15, "ordre": 4},
        {"nom": "Projet personnel", "description": "Développement du projet personnel", "duree_estimee": 30, "ordre": 5},
        {"nom": "Présentation du projet", "description": "Présentation devant le jury", "duree_estimee": 1, "ordre": 6},
        {"nom": "Certification", "description": "Obtention de la certification", "duree_estimee": 1, "ordre": 7}
    ],
    "ACT": [
        {"nom": "Sélection et admission", "description": "Processus de sélection", "duree_estimee": 5, "ordre": 1},
        {"nom": "Formation intensive", "description": "Formation accélérée", "duree_estimee": 60, "ordre": 2},
        {"nom": "Projet d'entreprise", "description": "Développement du projet d'entreprise", "duree_estimee": 45, "ordre": 3},
        {"nom": "Pitch final", "description": "Présentation du projet d'entreprise", "duree_estimee": 1, "ordre": 4},
        {"nom": "Accompagnement post-formation", "description": "Suivi et accompagnement", "duree_estimee": 180, "ordre": 5}
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
                    nom=etape_data["nom"],
                    description=etape_data["description"],
                    duree_estimee=etape_data["duree_estimee"],
                    ordre=etape_data["ordre"],
                    active=True,
                    conditions=None
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
                print(f"  {statut} {etape.ordre}. {etape.nom} ({etape.duree_estimee} jours)")
                if etape.description:
                    print(f"      {etape.description}")

if __name__ == "__main__":
    print("🚀 Initialisation des pipelines par défaut")
    print("=" * 50)
    
    # Initialiser les pipelines
    init_pipelines()
    
    print("\n" + "=" * 50)
    print("📊 État des pipelines après initialisation:")
    afficher_pipelines()
    
    print("\n✅ Initialisation terminée !")
