#!/usr/bin/env python3
"""Script pour vérifier les candidats validés"""

from app_lia_web.core.database import get_session
from app_lia_web.app.models.base import Inscription, Candidat, Programme
from sqlmodel import select

def check_validated_candidates():
    db = next(get_session())
    
    # Compter les inscriptions par statut
    inscriptions_by_status = db.exec(
        select(Inscription.statut, func.count(Inscription.id))
        .group_by(Inscription.statut)
    ).all()
    
    print("=== STATUTS DES INSCRIPTIONS ===")
    for statut, count in inscriptions_by_status:
        print(f"{statut}: {count}")
    
    # Récupérer les candidats validés
    candidats_valides = db.exec(
        select(Inscription.id, Inscription.statut, Candidat.prenom, Candidat.nom, Programme.nom)
        .join(Candidat)
        .join(Programme)
        .where(Inscription.statut == 'valide')
    ).all()
    
    print(f"\n=== CANDIDATS VALIDÉS ({len(candidats_valides)}) ===")
    for inscription in candidats_valides[:10]:  # Afficher les 10 premiers
        print(f"- {inscription.prenom} {inscription.nom} - {inscription.nom}")
    
    if len(candidats_valides) == 0:
        print("\n⚠️  Aucun candidat validé trouvé!")
        print("💡 Vous devez d'abord valider des candidats dans le système d'inscription.")

if __name__ == "__main__":
    from sqlmodel import func
    check_validated_candidates()
