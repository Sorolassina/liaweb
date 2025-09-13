#!/usr/bin/env python3
"""
Script pour mettre à jour les paramètres de l'administrateur existant
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app_lia_web.core.database import engine
from app_lia_web.app.models.base import User
from app_lia_web.core.security import get_password_hash, verify_password

def update_admin_user():
    """Met à jour les paramètres de l'administrateur"""
    
    # Configuration admin (peut être surchargée par des variables d'environnement)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "sorolassina58@gmail.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMoi#2025")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Soro wangboho lassina")
    
    with Session(engine) as session:
        try:
            print(f"🔍 Recherche de l'administrateur avec l'email: {ADMIN_EMAIL}")
            
            # Chercher l'admin par email
            admin_user = session.exec(select(User).where(User.email == ADMIN_EMAIL)).first()
            
            if not admin_user:
                print(f"❌ Aucun utilisateur trouvé avec l'email: {ADMIN_EMAIL}")
                print("💡 Créez d'abord l'utilisateur admin ou vérifiez l'email")
                return
            
            print(f"✅ Administrateur trouvé: {admin_user.nom_complet}")
            print(f"📧 Email actuel: {admin_user.email}")
            print(f"👤 Nom actuel: {admin_user.nom_complet}")
            print(f"🔑 Rôle actuel: {admin_user.role}")
            print(f"✅ Actif: {admin_user.actif}")
            
            # Vérifier si une mise à jour est nécessaire
            needs_update = False
            updates = []
            
            if admin_user.nom_complet != ADMIN_NAME:
                updates.append(f"Nom: '{admin_user.nom_complet}' → '{ADMIN_NAME}'")
                needs_update = True
            
            if not verify_password(ADMIN_PASSWORD, admin_user.mot_de_passe_hash):
                updates.append("Mot de passe: mis à jour")
                needs_update = True
            
            if admin_user.role != "administrateur":
                updates.append(f"Rôle: '{admin_user.role}' → 'administrateur'")
                needs_update = True
            
            if not admin_user.actif:
                updates.append("Statut: inactif → actif")
                needs_update = True
            
            if not needs_update:
                print("✅ Aucune mise à jour nécessaire")
                return
            
            print(f"\n🔄 Mise à jour nécessaire:")
            for update in updates:
                print(f"   - {update}")
            
            # Demander confirmation
            response = input("\n❓ Voulez-vous procéder à la mise à jour ? (y/N): ")
            if response.lower() != 'y':
                print("❌ Mise à jour annulée")
                return
            
            # Effectuer les mises à jour
            admin_user.nom_complet = ADMIN_NAME
            admin_user.mot_de_passe_hash = get_password_hash(ADMIN_PASSWORD)
            admin_user.role = "administrateur"
            admin_user.actif = True
            
            session.add(admin_user)
            session.commit()
            
            print("✅ Administrateur mis à jour avec succès!")
            print(f"📧 Email: {admin_user.email}")
            print(f"👤 Nom: {admin_user.nom_complet}")
            print(f"🔑 Rôle: {admin_user.role}")
            print(f"✅ Actif: {admin_user.actif}")
            
        except Exception as e:
            print(f"❌ Erreur lors de la mise à jour: {e}")
            session.rollback()
            raise

if __name__ == "__main__":
    update_admin_user()
