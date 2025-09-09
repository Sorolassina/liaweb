#!/usr/bin/env python3
"""
Script pour créer des données de test pour les rendez-vous
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent))

from core.database import get_session
from models.base import RendezVous, Inscription, User
from models.enums import TypeRDV, StatutRDV, UserRole
from sqlmodel import Session, select

def create_test_rendez_vous():
    """Créer des rendez-vous de test"""
    try:
        print("🚀 Création de rendez-vous de test...")
        
        with get_session() as session:
            # Récupérer quelques inscriptions
            inscriptions = session.exec(select(Inscription).limit(3)).all()
            if not inscriptions:
                print("❌ Aucune inscription trouvée. Créez d'abord des inscriptions.")
                return False
            
            # Récupérer un conseiller
            conseiller = session.exec(
                select(User).where(User.role == UserRole.CONSEILLER).limit(1)
            ).first()
            
            if not conseiller:
                print("❌ Aucun conseiller trouvé. Créez d'abord un utilisateur avec le rôle conseiller.")
                return False
            
            # Créer quelques rendez-vous de test
            rendez_vous_test = [
                {
                    "inscription_id": inscriptions[0].id,
                    "conseiller_id": conseiller.id,
                    "type_rdv": TypeRDV.ENTRETIEN,
                    "statut": StatutRDV.PLANIFIE,
                    "debut": datetime.now() + timedelta(days=1),
                    "fin": datetime.now() + timedelta(days=1, hours=1),
                    "lieu": "Bureau 101",
                    "notes": "Premier entretien de suivi"
                },
                {
                    "inscription_id": inscriptions[1].id if len(inscriptions) > 1 else inscriptions[0].id,
                    "conseiller_id": conseiller.id,
                    "type_rdv": TypeRDV.SUIVI,
                    "statut": StatutRDV.PLANIFIE,
                    "debut": datetime.now() + timedelta(days=2),
                    "fin": datetime.now() + timedelta(days=2, hours=1),
                    "lieu": "Salle de réunion A",
                    "notes": "Session de suivi mensuel"
                },
                {
                    "inscription_id": inscriptions[2].id if len(inscriptions) > 2 else inscriptions[0].id,
                    "conseiller_id": conseiller.id,
                    "type_rdv": TypeRDV.COACHING,
                    "statut": StatutRDV.TERMINE,
                    "debut": datetime.now() - timedelta(days=1),
                    "fin": datetime.now() - timedelta(days=1, hours=1),
                    "lieu": "Bureau 102",
                    "notes": "Session de coaching terminée"
                }
            ]
            
            for rdv_data in rendez_vous_test:
                rdv = RendezVous(**rdv_data)
                session.add(rdv)
            
            session.commit()
            print(f"✅ {len(rendez_vous_test)} rendez-vous de test créés avec succès")
            return True
            
    except Exception as e:
        print(f"❌ Erreur lors de la création des rendez-vous de test: {e}")
        return False

if __name__ == "__main__":
    success = create_test_rendez_vous()
    sys.exit(0 if success else 1)
