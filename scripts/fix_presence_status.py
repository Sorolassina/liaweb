#!/usr/bin/env python3
"""
Script pour corriger les statuts de présence incorrects
"""
from sqlmodel import Session, select, create_engine
from app_lia_web.app.models.seminaire import PresenceSeminaire
from app_lia_web.app.models.enums import StatutPresence
from datetime import datetime, timezone

# Connexion à la base
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, echo=True)

def fix_presence_status():
    """Corriger les statuts de présence incorrects"""
    with Session(engine) as session:
        # Récupérer toutes les présences qui ont des signatures mais le statut ABSENT
        query = select(PresenceSeminaire).where(
            PresenceSeminaire.presence == StatutPresence.ABSENT
        )
        presences = session.exec(query).all()
        
        print(f"=== CORRECTION DES STATUTS DE PRÉSENCE ===")
        print(f"Trouvé {len(presences)} présences avec statut ABSENT")
        
        corrected_count = 0
        
        for presence in presences:
            should_be_present = False
            
            # Vérifier si la présence a des signatures ou une heure d'arrivée
            if presence.signature_digitale or presence.signature_manuelle or presence.heure_arrivee:
                should_be_present = True
                print(f"Présence ID {presence.id}:")
                print(f"  - Signature digitale: {'OUI' if presence.signature_digitale else 'NON'}")
                print(f"  - Signature manuelle: {'OUI' if presence.signature_manuelle else 'NON'}")
                print(f"  - Heure d'arrivée: {presence.heure_arrivee}")
                print(f"  - Méthode: {presence.methode_signature}")
            
            if should_be_present:
                # Corriger le statut
                presence.presence = StatutPresence.PRESENT
                presence.modifie_le = datetime.now(timezone.utc)
                session.add(presence)
                corrected_count += 1
                print(f"  ✅ Statut corrigé vers PRESENT")
            else:
                print(f"Présence ID {presence.id}: Statut ABSENT correct (pas de signature)")
        
        if corrected_count > 0:
            session.commit()
            print(f"\n🎉 {corrected_count} présences corrigées avec succès!")
        else:
            print(f"\n✅ Aucune correction nécessaire")

if __name__ == "__main__":
    print("🔧 Correction des statuts de présence...")
    fix_presence_status()
    print("✅ Script terminé.")
