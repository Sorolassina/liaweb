#!/usr/bin/env python3
"""
Script pour mettre à jour les rôles des utilisateurs existants
de l'ancien format enum vers le nouveau format string
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.base import User
from app.models.enums import UserRole

def update_user_roles():
    """Met à jour les rôles des utilisateurs existants"""
    
    # Mapping des anciens noms d'enum vers les nouvelles valeurs string
    role_mapping = {
        "ADMINISTRATEUR": "administrateur",
        "DIRECTEUR_GENERAL": "directeur_general", 
        "DIRECTEUR_TECHNIQUE": "directeur_technique",
        "RESPONSABLE_PROGRAMME": "responsable_programme",
        "CONSEILLER": "conseiller",
        "COORDINATEUR": "coordinateur",
        "FORMATEUR": "formateur",
        "EVALUATEUR": "evaluateur",
        "ACCOMPAGNATEUR": "accompagnateur",
        "DRH": "drh",
        "RESPONSABLE_STRUCTURE": "responsable_structure",
        "COACH_EXTERNE": "coach_externe",
        "JURY_EXTERNE": "jury_externe",
        "CANDIDAT": "candidat",
        "RESPONSABLE_COMMUNICATION": "responsable_communication",
        "ASSISTANT_COMMUNICATION": "assistant_communication"
    }
    
    with Session(engine) as session:
        # Récupérer tous les utilisateurs
        users = session.exec(select(User)).all()
        
        print(f"🔍 Trouvé {len(users)} utilisateurs à vérifier")
        
        updated_count = 0
        for user in users:
            old_role = user.role
            print(f"👤 Utilisateur: {user.email}, Rôle actuel: {old_role}")
            
            # Vérifier si le rôle est déjà au bon format (string)
            if isinstance(old_role, str) and old_role in role_mapping.values():
                print(f"✅ Rôle déjà au bon format: {old_role}")
                continue
            
            # Vérifier si c'est un nom d'enum à convertir
            if old_role in role_mapping:
                new_role = role_mapping[old_role]
                user.role = new_role
                updated_count += 1
                print(f"🔄 Rôle mis à jour: {old_role} → {new_role}")
            else:
                print(f"⚠️ Rôle inconnu: {old_role}")
        
        if updated_count > 0:
            session.commit()
            print(f"✅ {updated_count} utilisateurs mis à jour avec succès")
        else:
            print("ℹ️ Aucun utilisateur à mettre à jour")

if __name__ == "__main__":
    print("🚀 Démarrage de la mise à jour des rôles utilisateurs...")
    update_user_roles()
    print("✅ Mise à jour terminée")
