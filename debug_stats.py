#!/usr/bin/env python3
"""
Script de debug pour vérifier les statistiques e-learning
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_lia_web.core.database import get_session
from app_lia_web.models.base import Programme, Inscription
from app_lia_web.models.elearning import ModuleElearning, ProgressionElearning
from app_lia_web.services.elearning_service import ElearningService
from sqlmodel import select, func

def debug_stats():
    session = next(get_session())
    
    print("🔍 DEBUG DES STATISTIQUES E-LEARNING")
    print("=" * 50)
    
    # 1. Vérifier les programmes
    programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
    print(f"📊 Programmes actifs trouvés: {len(programmes)}")
    for p in programmes:
        print(f"  - Programme {p.id}: {p.nom}")
    
    # 2. Vérifier les modules
    modules = session.exec(select(ModuleElearning)).all()
    print(f"\n📚 Modules e-learning trouvés: {len(modules)}")
    for m in modules:
        print(f"  - Module {m.id}: {m.titre} (programme: {m.programme_id}, actif: {m.actif})")
    
    # 3. Vérifier les inscriptions
    inscriptions = session.exec(select(Inscription)).all()
    print(f"\n👥 Inscriptions trouvées: {len(inscriptions)}")
    for i in inscriptions:
        print(f"  - Inscription {i.id}: {i.candidat.nom} {i.candidat.prenom} (programme: {i.programme_id})")
    
    # 4. Vérifier les progressions
    progressions = session.exec(select(ProgressionElearning)).all()
    print(f"\n📈 Progressions trouvées: {len(progressions)}")
    for p in progressions:
        print(f"  - Progression {p.id}: inscription {p.inscription_id}, module {p.module_id}, statut: {p.statut}")
    
    # 5. Tester la méthode get_statistiques_programme pour chaque programme
    print(f"\n🧮 TEST DES STATISTIQUES PAR PROGRAMME")
    print("=" * 50)
    
    for programme in programmes:
        print(f"\n📊 Programme: {programme.nom} (ID: {programme.id})")
        try:
            stats = ElearningService.get_statistiques_programme(session, programme.id)
            print(f"  ✅ Statistiques calculées avec succès:")
            print(f"    - Candidats inscrits: {stats.candidats_inscrits}")
            print(f"    - Candidats actifs: {stats.candidats_actifs}")
            print(f"    - Temps moyen: {stats.temps_moyen_minutes} minutes")
            print(f"    - Taux completion: {stats.taux_completion}%")
            print(f"    - Modules populaires: {len(stats.modules_populaires)}")
            for mp in stats.modules_populaires:
                print(f"      * {mp['titre']} ({mp['participations']} participations)")
        except Exception as e:
            print(f"  ❌ Erreur lors du calcul des statistiques: {e}")
            import traceback
            traceback.print_exc()
    
    session.close()

if __name__ == "__main__":
    debug_stats()
