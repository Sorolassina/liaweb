#!/usr/bin/env python3
"""
Script de test pour vérifier la logique des statuts par défaut
"""

from sqlmodel import Session, text
from app_lia_web.core.database import get_session
from datetime import date

def test_default_status_logic():
    """Test de la logique des statuts par défaut"""
    
    print("🔍 TEST DE LA LOGIQUE DES STATUTS PAR DÉFAUT")
    print("=" * 60)
    
    session = next(get_session())
    
    try:
        # 1. Récupérer les sessions de séminaires avec leurs dates
        sessions_query = text("""
            SELECT 
                s.id,
                s.titre,
                s.date_session,
                sem.titre as seminaire_titre
            FROM sessionseminaire s
            JOIN seminaire sem ON s.seminaire_id = sem.id
            ORDER BY s.date_session DESC
            LIMIT 5
        """)
        
        sessions = session.exec(sessions_query).all()
        
        print(f"📅 Sessions trouvées: {len(sessions)}")
        print()
        
        today = date.today()
        
        for session_data in sessions:
            session_id, titre, date_session, seminaire_titre = session_data
            
            print(f"🎯 Session: {titre}")
            print(f"   📅 Date: {date_session}")
            print(f"   📚 Séminaire: {seminaire_titre}")
            
            # Déterminer le statut par défaut selon la logique
            if date_session < today:
                default_status = "absent"  # Événement passé
                status_reason = "Événement passé"
            else:
                default_status = "en_attente"  # Événement futur
                status_reason = "Événement futur"
            
            print(f"   🎯 Statut par défaut: {default_status} ({status_reason})")
            
            # Vérifier les présences existantes
            presences_query = text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse,
                    COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente
                FROM presenceseminaire 
                WHERE session_id = :session_id
            """)
            
            stats = session.exec(presences_query.bindparams(session_id=session_id)).first()
            
            if stats:
                total, present, absent, excuse, en_attente = stats
                print(f"   📊 Présences: Total={total}, Présent={present}, Absent={absent}, Excusé={excuse}, En attente={en_attente}")
            
            print()
        
        # 2. Récupérer les événements avec leurs dates
        events_query = text("""
            SELECT 
                id,
                titre,
                date_debut,
                date_fin
            FROM events 
            ORDER BY date_debut DESC
            LIMIT 5
        """)
        
        events = session.exec(events_query).all()
        
        print(f"📅 Événements trouvés: {len(events)}")
        print()
        
        for event_data in events:
            event_id, titre, date_debut, date_fin = event_data
            
            print(f"🎯 Événement: {titre}")
            print(f"   📅 Date: {date_debut} - {date_fin}")
            
            # Déterminer le statut par défaut selon la logique
            if date_fin < today:
                default_status = "absent"  # Événement passé
                status_reason = "Événement passé"
            else:
                default_status = "en_attente"  # Événement futur
                status_reason = "Événement futur"
            
            print(f"   🎯 Statut par défaut: {default_status} ({status_reason})")
            
            # Vérifier les présences existantes
            presences_query = text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse,
                    COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente
                FROM presence_events 
                WHERE event_id = :event_id
            """)
            
            stats = session.exec(presences_query.bindparams(event_id=event_id)).first()
            
            if stats:
                total, present, absent, excuse, en_attente = stats
                print(f"   📊 Présences: Total={total}, Présent={present}, Absent={absent}, Excusé={excuse}, En attente={en_attente}")
            
            print()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    test_default_status_logic()
