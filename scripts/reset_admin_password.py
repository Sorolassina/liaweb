#!/usr/bin/env python3
"""
Script pour réinitialiser le mot de passe de l'administrateur
Usage: python scripts/reset_admin_password.py [nouveau_mot_de_passe]
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, text
from app.core.database import engine
from app.core.security import get_password_hash
from app.core.config import settings

# Ne pas importer User pour éviter les problèmes de dépendances circulaires
# On utilisera des requêtes SQL directes

def reset_admin_password(new_password: str = None):
    """Réinitialise le mot de passe de l'administrateur"""
    
    # Utiliser le mot de passe fourni ou celui de la config
    if not new_password:
        new_password = input("Entrez le nouveau mot de passe admin (ou appuyez sur Entrée pour utiliser celui de la config): ").strip()
        if not new_password:
            new_password = settings.PASSWORD_ADMIN
            print(f"🔑 Utilisation du mot de passe de la config: {new_password}")
    
    admin_email = settings.MAIL_ADMIN
    
    if not admin_email:
        print("❌ Erreur: MAIL_ADMIN n'est pas configuré dans settings")
        return False
    
    print(f"👤 Email admin: {admin_email}")
    print(f"🔑 Nouveau mot de passe: {new_password}")
    
    try:
        # Utiliser une requête SQL directe pour éviter les problèmes d'imports de modèles
        with Session(engine) as session:
            # Vérifier si l'admin existe avec une requête SQL directe
            # Utiliser session.execute() au lieu de session.exec() pour les requêtes SQL brutes
            result = session.execute(
                text("SELECT id, email, nom_complet, role, actif, mot_de_passe_hash FROM \"user\" WHERE email = :email"),
                {"email": admin_email}
            ).first()
            
            new_password_hash = get_password_hash(new_password)
            
            if not result:
                print(f"❌ Administrateur non trouvé avec l'email: {admin_email}")
                print("💡 Création d'un nouvel administrateur...")
                
                # Créer un nouvel administrateur avec SQL direct
                session.execute(
                    text("""
                        INSERT INTO "user" (email, nom_complet, mot_de_passe_hash, role, type_utilisateur, actif, cree_le)
                        VALUES (:email, :nom_complet, :password_hash, :role, :type_utilisateur, :actif, NOW())
                    """),
                    {
                        "email": admin_email,
                        "nom_complet": "Administrateur",
                        "password_hash": new_password_hash,
                        "role": "administrateur",
                        "type_utilisateur": "interne",
                        "actif": True
                    }
                )
                session.commit()
                # Récupérer l'ID du nouvel utilisateur créé
                result = session.execute(
                    text("SELECT id, email, nom_complet, role, actif, mot_de_passe_hash FROM \"user\" WHERE email = :email"),
                    {"email": admin_email}
                ).first()
                user_id = result[0] if result else None
                print(f"✅ Nouvel administrateur créé avec succès (ID: {user_id})")
            else:
                # Mettre à jour le mot de passe avec SQL direct
                user_id = result[0]
                session.execute(
                    text("UPDATE \"user\" SET mot_de_passe_hash = :password_hash WHERE id = :user_id"),
                    {
                        "password_hash": new_password_hash,
                        "user_id": user_id
                    }
                )
                session.commit()
                print(f"✅ Mot de passe réinitialisé avec succès pour: {admin_email}")
                print(f"📋 ID utilisateur: {user_id}")
            
            # Vérification finale
            result_check = session.execute(
                text("SELECT id, email, nom_complet, role, actif FROM \"user\" WHERE email = :email"),
                {"email": admin_email}
            ).first()
            
            if result_check:
                user_id, email, nom, role, actif = result_check
                print(f"✅ Vérification: Administrateur trouvé dans la base de données")
                print(f"   - Email: {email}")
                print(f"   - Nom: {nom}")
                print(f"   - Role: {role}")
                print(f"   - Actif: {actif}")
            
            return True
            
    except Exception as e:
        print(f"❌ Erreur lors de la réinitialisation du mot de passe: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Récupérer le nouveau mot de passe depuis les arguments de ligne de commande
    new_password = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("=" * 60)
    print("🔐 RÉINITIALISATION DU MOT DE PASSE ADMINISTRATEUR")
    print("=" * 60)
    print()
    
    success = reset_admin_password(new_password)
    
    print()
    print("=" * 60)
    if success:
        print("✅ Réinitialisation terminée avec succès")
    else:
        print("❌ Échec de la réinitialisation")
    print("=" * 60)

