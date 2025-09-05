"""
Script de données de test pour l'application LIA Coaching
"""
from sqlmodel import Session, select
from datetime import date, datetime
import json

from app.core.database import engine
from app.core.security import get_password_hash
from app.models.base import *
from app.models.enums import *

def create_test_data():
    """Crée des données de test pour l'application"""
    with Session(engine) as session:
        print("🔄 Création des données de test...")
        
        # 1. Créer les utilisateurs de test
        users_data = [
            {
                "email": "admin@lia-coaching.com",
                "nom_complet": "Administrateur LIA",
                "role": UserRole.ADMINISTRATEUR,
                "type_utilisateur": TypeUtilisateur.INTERNE
            },
            {
                "email": "directeur@lia-coaching.com",
                "nom_complet": "Directeur Technique",
                "role": UserRole.DIRECTEUR_TECHNIQUE,
                "type_utilisateur": TypeUtilisateur.INTERNE
            },
            {
                "email": "responsable.acd@lia-coaching.com",
                "nom_complet": "Responsable ACD",
                "role": UserRole.RESPONSABLE_PROGRAMME,
                "type_utilisateur": TypeUtilisateur.INTERNE
            },
            {
                "email": "responsable.aci@lia-coaching.com",
                "nom_complet": "Responsable ACI",
                "role": UserRole.RESPONSABLE_PROGRAMME,
                "type_utilisateur": TypeUtilisateur.INTERNE
            },
            {
                "email": "responsable.act@lia-coaching.com",
                "nom_complet": "Responsable ACT",
                "role": UserRole.RESPONSABLE_PROGRAMME,
                "type_utilisateur": TypeUtilisateur.INTERNE
            },
            {
                "email": "conseiller1@lia-coaching.com",
                "nom_complet": "Conseiller 1",
                "role": UserRole.CONSEILLER,
                "type_utilisateur": TypeUtilisateur.INTERNE
            },
            {
                "email": "conseiller2@lia-coaching.com",
                "nom_complet": "Conseiller 2",
                "role": UserRole.CONSEILLER,
                "type_utilisateur": TypeUtilisateur.INTERNE
            }
        ]
        
        users = {}
        for user_data in users_data:
            user = User(
                email=user_data["email"],
                nom_complet=user_data["nom_complet"],
                role=user_data["role"],
                type_utilisateur=user_data["type_utilisateur"],
                mot_de_passe_hash=get_password_hash("password123"),
                actif=True
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            users[user_data["email"]] = user
            print(f"✅ Utilisateur créé: {user.nom_complet}")
        
        # 2. Créer les programmes
        programmes_data = [
            {
                "code": "ACD",
                "nom": "Accompagnement Création d'Entreprise",
                "objectif": "Accompagner les créateurs d'entreprise dans leur démarche",
                "date_debut": date(2024, 1, 1),
                "date_fin": date(2024, 12, 31),
                "ca_seuil_min": 50000,
                "ca_seuil_max": 500000,
                "anciennete_min_annees": 1,
                "responsable_id": users["responsable.acd@lia-coaching.com"].id
            },
            {
                "code": "ACI",
                "nom": "Accompagnement Innovation",
                "objectif": "Accompagner les entreprises innovantes",
                "date_debut": date(2024, 1, 1),
                "date_fin": date(2024, 12, 31),
                "ca_seuil_min": 100000,
                "ca_seuil_max": 1000000,
                "anciennete_min_annees": 2,
                "responsable_id": users["responsable.aci@lia-coaching.com"].id
            },
            {
                "code": "ACT",
                "nom": "Accompagnement Transformation",
                "objectif": "Accompagner la transformation des entreprises",
                "date_debut": date(2024, 1, 1),
                "date_fin": date(2024, 12, 31),
                "ca_seuil_min": 200000,
                "ca_seuil_max": 2000000,
                "anciennete_min_annees": 3,
                "responsable_id": users["responsable.act@lia-coaching.com"].id
            }
        ]
        
        programmes = {}
        for prog_data in programmes_data:
            programme = Programme(**prog_data, actif=True)
            session.add(programme)
            session.commit()
            session.refresh(programme)
            programmes[prog_data["code"]] = programme
            print(f"✅ Programme créé: {programme.nom}")
        
        # 3. Créer les promotions
        promotions_data = [
            {
                "programme_id": programmes["ACD"].id,
                "libelle": "Promo ACD Octobre 2024",
                "capacite": 15,
                "date_debut": date(2024, 10, 1),
                "date_fin": date(2025, 10, 1)
            },
            {
                "programme_id": programmes["ACI"].id,
                "libelle": "Promo ACI Mars 2025",
                "capacite": 15,
                "date_debut": date(2025, 3, 1),
                "date_fin": date(2026, 3, 1)
            },
            {
                "programme_id": programmes["ACT"].id,
                "libelle": "Promo ACT Juin 2025",
                "capacite": 15,
                "date_debut": date(2025, 6, 1),
                "date_fin": date(2026, 6, 1)
            }
        ]
        
        for promo_data in promotions_data:
            promotion = Promotion(**promo_data, actif=True)
            session.add(promotion)
            session.commit()
            session.refresh(promotion)
            print(f"✅ Promotion créée: {promotion.libelle}")
        
        # 4. Créer des candidats de test
        candidats_data = [
            {
                "civilite": "M.",
                "nom": "Dupont",
                "prenom": "Jean",
                "date_naissance": date(1985, 5, 15),
                "email": "jean.dupont@email.com",
                "telephone": "0123456789",
                "adresse_personnelle": "123 Rue de la Paix, 75001 Paris",
                "niveau_etudes": "Bac+5",
                "secteur_activite": "Restauration",
                "handicap": False
            },
            {
                "civilite": "Mme",
                "nom": "Martin",
                "prenom": "Sophie",
                "date_naissance": date(1990, 8, 22),
                "email": "sophie.martin@email.com",
                "telephone": "0987654321",
                "adresse_personnelle": "456 Avenue des Champs, 69000 Lyon",
                "niveau_etudes": "Bac+3",
                "secteur_activite": "Technologie",
                "handicap": True,
                "type_handicap": StatutHandicap.MOBILITE,
                "besoins_accommodation": "Accès fauteuil roulant"
            },
            {
                "civilite": "M.",
                "nom": "Bernard",
                "prenom": "Pierre",
                "date_naissance": date(1982, 3, 10),
                "email": "pierre.bernard@email.com",
                "telephone": "0555666777",
                "adresse_personnelle": "789 Boulevard Central, 13000 Marseille",
                "niveau_etudes": "Bac+4",
                "secteur_activite": "Commerce",
                "handicap": False
            }
        ]
        
        candidats = []
        for candidat_data in candidats_data:
            candidat = Candidat(**candidat_data)
            session.add(candidat)
            session.commit()
            session.refresh(candidat)
            candidats.append(candidat)
            print(f"✅ Candidat créé: {candidat.nom} {candidat.prenom}")
        
        # 5. Créer des entreprises pour les candidats
        entreprises_data = [
            {
                "candidat_id": candidats[0].id,
                "siret": "12345678901234",
                "siren": "123456789",
                "raison_sociale": "Restaurant Le Gourmet",
                "code_naf": "5610A",
                "date_creation": date(2022, 1, 15),
                "adresse": "123 Rue de la Paix, 75001 Paris",
                "qpv": False,
                "chiffre_affaires": 150000,
                "nombre_points_vente": 1,
                "specialite_culinaire": "Cuisine française traditionnelle",
                "nom_concept": "Le Gourmet",
                "territoire": "Paris"
            },
            {
                "candidat_id": candidats[1].id,
                "siret": "98765432109876",
                "siren": "987654321",
                "raison_sociale": "TechInnov Solutions",
                "code_naf": "6201Z",
                "date_creation": date(2021, 6, 20),
                "adresse": "456 Avenue des Champs, 69000 Lyon",
                "qpv": True,
                "chiffre_affaires": 300000,
                "nombre_points_vente": 1,
                "specialite_culinaire": "Solutions technologiques",
                "nom_concept": "TechInnov",
                "territoire": "Lyon"
            },
            {
                "candidat_id": candidats[2].id,
                "siret": "11223344556677",
                "siren": "112233445",
                "raison_sociale": "Commerce Plus",
                "code_naf": "4711A",
                "date_creation": date(2020, 9, 5),
                "adresse": "789 Boulevard Central, 13000 Marseille",
                "qpv": False,
                "chiffre_affaires": 800000,
                "nombre_points_vente": 3,
                "specialite_culinaire": "Commerce de détail",
                "nom_concept": "Commerce Plus",
                "territoire": "Marseille"
            }
        ]
        
        for entreprise_data in entreprises_data:
            entreprise = Entreprise(**entreprise_data)
            session.add(entreprise)
            session.commit()
            session.refresh(entreprise)
            print(f"✅ Entreprise créée: {entreprise.raison_sociale}")
        
        # 6. Créer des préinscriptions
        preinscriptions_data = [
            {
                "programme_id": programmes["ACD"].id,
                "candidat_id": candidats[0].id,
                "source": "formulaire",
                "statut": StatutDossier.SOUMIS
            },
            {
                "programme_id": programmes["ACI"].id,
                "candidat_id": candidats[1].id,
                "source": "formulaire",
                "statut": StatutDossier.EN_EXAMEN
            },
            {
                "programme_id": programmes["ACT"].id,
                "candidat_id": candidats[2].id,
                "source": "formulaire",
                "statut": StatutDossier.VALIDE
            }
        ]
        
        for preinscription_data in preinscriptions_data:
            preinscription = Preinscription(**preinscription_data)
            session.add(preinscription)
            session.commit()
            session.refresh(preinscription)
            print(f"✅ Préinscription créée pour candidat {preinscription.candidat_id}")
        
        print("🎉 Données de test créées avec succès!")
        print("\n📋 Récapitulatif:")
        print(f"- {len(users)} utilisateurs créés")
        print(f"- {len(programmes)} programmes créés")
        print(f"- {len(candidats)} candidats créés")
        print(f"- {len(entreprises_data)} entreprises créées")
        print(f"- {len(preinscriptions_data)} préinscriptions créées")
        print("\n🔑 Identifiants de test:")
        print("- Admin: admin@lia-coaching.com / password123")
        print("- Directeur: directeur@lia-coaching.com / password123")
        print("- Conseiller: conseiller1@lia-coaching.com / password123")

if __name__ == "__main__":
    create_test_data()
