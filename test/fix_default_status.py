#!/usr/bin/env python3
"""
Script Python pour corriger les statuts par défaut dans la base de données
Applique la nouvelle logique : en_attente par défaut pour les événements futurs
"""

from sqlmodel import Session, text
from app_lia_web.core.database import get_session
from datetime import date

def fix_default_status():
    """Corrige les statuts par défaut selon la nouvelle logique"""
    
    print("🔧 CORRECTION DES STATUTS PAR DÉFAUT")
    print("=" * 60)
    
    session = next(get_session())
    
    try:
        # 1. CORRECTION DES SÉMINAIRES
        print("📚 Correction des séminaires...")
        
        # Mettre 'en_attente' pour les événements futurs avec invitation acceptée
        query1 = text("""
            UPDATE presenceseminaire 
            SET presence = 'en_attente'
            WHERE presence = 'absent' 
              AND session_id IN (
                SELECT s.id 
                FROM sessionseminaire s 
                WHERE s.date_session >= CURRENT_DATE
              )
              AND inscription_id IN (
                SELECT i.inscription_id 
                FROM invitationseminaire i 
                WHERE i.statut = 'ACCEPTEE'
              )
        """)
        
        result1 = session.exec(query1)
        session.commit()
        print(f"   ✅ Séminaires futurs acceptés: {result1.rowcount} mises à jour")
        
        # Garder 'absent' pour les invitations refusées
        query2 = text("""
            UPDATE presenceseminaire 
            SET presence = 'absent'
            WHERE presence = 'en_attente'
              AND session_id IN (
                SELECT s.id 
                FROM sessionseminaire s 
                WHERE s.date_session >= CURRENT_DATE
              )
              AND inscription_id IN (
                SELECT i.inscription_id 
                FROM invitationseminaire i 
                WHERE i.statut = 'REFUSEE'
              )
        """)
        
        result2 = session.exec(query2)
        session.commit()
        print(f"   ✅ Séminaires futurs refusés: {result2.rowcount} mises à jour")
        
        # Mettre 'absent' pour les événements passés sans signature
        query3 = text("""
            UPDATE presenceseminaire 
            SET presence = 'absent'
            WHERE presence = 'en_attente'
              AND session_id IN (
                SELECT s.id 
                FROM sessionseminaire s 
                WHERE s.date_session < CURRENT_DATE
              )
              AND (signature_digitale IS NULL OR signature_digitale = '')
              AND (signature_manuelle IS NULL OR signature_manuelle = '')
        """)
        
        result3 = session.exec(query3)
        session.commit()
        print(f"   ✅ Séminaires passés sans signature: {result3.rowcount} mises à jour")
        
        # 2. CORRECTION DES ÉVÉNEMENTS
        print("\n🎯 Correction des événements...")
        
        # Mettre 'en_attente' pour les événements futurs avec invitation acceptée
        query4 = text("""
            UPDATE presence_events 
            SET presence = 'en_attente'
            WHERE presence = 'absent' 
              AND event_id IN (
                SELECT e.id 
                FROM events e 
                WHERE e.date_fin >= CURRENT_DATE
              )
              AND inscription_id IN (
                SELECT i.inscription_id 
                FROM invitation_events i 
                WHERE i.statut = 'acceptee'
              )
        """)
        
        result4 = session.exec(query4)
        session.commit()
        print(f"   ✅ Événements futurs acceptés: {result4.rowcount} mises à jour")
        
        # Garder 'absent' pour les invitations refusées
        query5 = text("""
            UPDATE presence_events 
            SET presence = 'absent'
            WHERE presence = 'en_attente'
              AND event_id IN (
                SELECT e.id 
                FROM events e 
                WHERE e.date_fin >= CURRENT_DATE
              )
              AND inscription_id IN (
                SELECT i.inscription_id 
                FROM invitation_events i 
                WHERE i.statut = 'refusee'
              )
        """)
        
        result5 = session.exec(query5)
        session.commit()
        print(f"   ✅ Événements futurs refusés: {result5.rowcount} mises à jour")
        
        # Mettre 'absent' pour les événements passés sans signature
        query6 = text("""
            UPDATE presence_events 
            SET presence = 'absent'
            WHERE presence = 'en_attente'
              AND event_id IN (
                SELECT e.id 
                FROM events e 
                WHERE e.date_fin < CURRENT_DATE
              )
              AND (signature_digitale IS NULL OR signature_digitale = '')
              AND (signature_manuelle IS NULL OR signature_manuelle = '')
        """)
        
        result6 = session.exec(query6)
        session.commit()
        print(f"   ✅ Événements passés sans signature: {result6.rowcount} mises à jour")
        
        # 3. VÉRIFICATION DES RÉSULTATS
        print("\n📊 Vérification des résultats...")
        
        # Statistiques des séminaires
        stats_seminaires = session.exec(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
                COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
                COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse,
                COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente
            FROM presenceseminaire
        """)).first()
        
        print(f"📚 Séminaires: Total={stats_seminaires[0]}, Présent={stats_seminaires[1]}, Absent={stats_seminaires[2]}, Excusé={stats_seminaires[3]}, En attente={stats_seminaires[4]}")
        
        # Statistiques des événements
        stats_events = session.exec(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
                COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
                COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse,
                COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente
            FROM presence_events
        """)).first()
        
        print(f"🎯 Événements: Total={stats_events[0]}, Présent={stats_events[1]}, Absent={stats_events[2]}, Excusé={stats_events[3]}, En attente={stats_events[4]}")
        
        print("\n✅ Correction terminée avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        session.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    fix_default_status()
