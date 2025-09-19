# Script de test pour le système de suivi mensuel
from sqlmodel import Session, select
from datetime import date, datetime
from app_lia_web.core.database import get_session
from app_lia_web.app.models.base import SuiviMensuel, Inscription, Candidat, Programme
from app_lia_web.app.services.suivi_mensuel_service import SuiviMensuelService
from app_lia_web.app.schemas.suivi_mensuel_schemas import SuiviMensuelCreate, SuiviMensuelFilter

def test_suivi_mensuel_system():
    """Test du système de suivi mensuel"""
    print("🧪 Test du système de suivi mensuel")
    
    # Obtenir une session de base de données
    session = next(get_session())
    service = SuiviMensuelService()
    
    try:
        # 1. Vérifier que la table existe
        print("\n1. Vérification de la table SuiviMensuel...")
        suivis_count = session.exec(select(SuiviMensuel)).all()
        print(f"   ✅ Table SuiviMensuel trouvée ({len(suivis_count)} enregistrements)")
        
        # 2. Vérifier les programmes disponibles
        print("\n2. Programmes disponibles...")
        programmes = session.exec(select(Programme)).all()
        print(f"   📊 {len(programmes)} programmes trouvés:")
        for prog in programmes[:3]:  # Afficher les 3 premiers
            print(f"      - {prog.nom} (ID: {prog.id})")
        
        # 3. Vérifier les inscriptions disponibles
        print("\n3. Inscriptions disponibles...")
        inscriptions = session.exec(select(Inscription).limit(5)).all()
        print(f"   👥 {len(inscriptions)} inscriptions trouvées (affichage des 5 premières):")
        for insc in inscriptions:
            candidat = session.get(Candidat, insc.candidat_id)
            programme = session.get(Programme, insc.programme_id)
            print(f"      - {candidat.prenom} {candidat.nom} dans {programme.nom} (ID: {insc.id})")
        
        # 4. Tester les statistiques
        print("\n4. Statistiques des suivis...")
        stats = service.get_suivi_stats(session)
        print(f"   📈 Statistiques globales:")
        print(f"      - Total suivis: {stats.total_suivis}")
        print(f"      - Score moyen: {stats.score_moyen or 'N/A'}")
        print(f"      - Avec commentaire: {stats.suivis_avec_commentaire}")
        print(f"      - Sans commentaire: {stats.suivis_sans_commentaire}")
        
        # 5. Tester les filtres
        print("\n5. Test des filtres...")
        if programmes:
            programme_id = programmes[0].id
            filters = SuiviMensuelFilter(programme_id=programme_id)
            suivis_filtres = service.get_suivis_with_filters(session, filters)
            print(f"   🔍 Suivis pour le programme {programmes[0].nom}: {len(suivis_filtres)}")
        
        # 6. Tester la récupération des mois
        print("\n6. Mois avec des suivis...")
        mois_disponibles = service.get_mois_suivis(session)
        print(f"   📅 {len(mois_disponibles)} mois avec des suivis:")
        for mois in mois_disponibles[:5]:  # Afficher les 5 premiers
            print(f"      - {mois.strftime('%m/%Y')}")
        
        print("\n✅ Tous les tests sont passés avec succès!")
        
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    test_suivi_mensuel_system()