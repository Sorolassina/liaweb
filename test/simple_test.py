#!/usr/bin/env python3
"""
Script de test simple pour vérifier les statuts de présence
Utilise des requêtes SQL brutes pour éviter les références circulaires
"""

from sqlmodel import Session, text
from app_lia_web.core.database import get_session

def simple_test():
    """Test simple des présences avec requêtes SQL brutes"""
    
    print("🔍 TEST SIMPLE DES PRÉSENCES ET SIGNATURES")
    print("=" * 50)
    
    session = next(get_session())
    
    try:
        # 1. Récupérer TOUS les événements avec requête SQL brute
        event_query = text("""
            SELECT id, titre, date_debut, date_fin, lieu 
            FROM events 
            ORDER BY date_debut DESC
        """)
        
        events = session.exec(event_query).all()
        
        if not events:
            print("❌ Aucun événement trouvé")
            return
        
        print(f"📅 Événements trouvés: {len(events)}")
        print()
        
        for event in events:
            event_id, titre, date_debut, date_fin, lieu = event
            print(f"🎯 Événement: {titre} (ID: {event_id})")
            print(f"📅 Date: {date_debut} - {date_fin}")
            print(f"📍 Lieu: {lieu or 'Non défini'}")
            
            # Vérifier les présences pour cet événement
            presences_query = text("""
                SELECT COUNT(*) 
                FROM presence_events 
                WHERE event_id = :event_id
            """)
            
            presences_count = session.exec(presences_query.bindparams(event_id=event_id)).first()
            
            # Vérifier les invitations pour cet événement
            invitations_query = text("""
                SELECT COUNT(*) 
                FROM invitation_events 
                WHERE event_id = :event_id
            """)
            
            invitations_count = session.exec(invitations_query.bindparams(event_id=event_id)).first()
            
            print(f"   👥 Présences: {presences_count[0]}")
            print(f"   📧 Invitations: {invitations_count[0]}")
            print()
        
        # Recherche globale des signatures digitales
        print("🔍 RECHERCHE GLOBALE DES SIGNATURES DIGITALES")
        print("-" * 50)
        
        signatures_query = text("""
            SELECT 
                pe.id,
                pe.event_id,
                pe.inscription_id,
                pe.presence,
                pe.signature_digitale,
                pe.methode_signature,
                e.titre as event_titre
            FROM presence_events pe
            JOIN events e ON pe.event_id = e.id
            WHERE pe.signature_digitale IS NOT NULL
            ORDER BY pe.event_id, pe.inscription_id
        """)
        
        signatures = session.exec(signatures_query).all()
        
        print(f"✍️ Signatures digitales trouvées: {len(signatures)}")
        print()
        
        for sig in signatures:
            sig_id, event_id, inscription_id, presence, signature_digitale, methode_signature, event_titre = sig
            print(f"   📝 Signature ID: {sig_id}")
            print(f"      🎯 Événement: {event_titre} (ID: {event_id})")
            print(f"      👤 Inscription ID: {inscription_id}")
            print(f"      📊 Statut présence: {presence}")
            print(f"      📝 Méthode: {methode_signature}")
            print(f"      ✍️ Signature: {len(signature_digitale)} caractères")
            print()
        
        if not signatures:
            print("❌ Aucune signature digitale trouvée dans la base")
            print()
        
        # Analyser le premier événement en détail
        event_id, titre, date_debut, date_fin, lieu = events[0]
        
        # 2. Récupérer toutes les présences avec signature digitale
        presences_query = text("""
            SELECT 
                id,
                presence,
                cree_le,
                modifie_le,
                heure_arrivee,
                methode_signature,
                commentaire,
                inscription_id,
                signature_digitale
            FROM presence_events 
            WHERE event_id = :event_id
            ORDER BY inscription_id
        """)
        
        presences = session.exec(presences_query.bindparams(event_id=event_id)).all()
        
        print(f"👥 Présences trouvées: {len(presences)}")
        print()
        
        for presence in presences:
            presence_id, statut, cree_le, modifie_le, heure_arrivee, methode_signature, commentaire, inscription_id, signature_digitale = presence
            
            print(f"   👤 Inscription ID: {inscription_id}")
            print(f"      🎯 Statut: {statut}")
            print(f"      📅 Créée: {cree_le}")
            print(f"      📅 Modifiée: {modifie_le}")
            print(f"      ⏰ Heure arrivée: {heure_arrivee}")
            print(f"      📝 Méthode signature: {methode_signature}")
            print(f"      💬 Commentaire: {commentaire or 'Aucun'}")
            print(f"      ✍️ Signature digitale: {'OUI' if signature_digitale else 'NON'}")
            if signature_digitale:
                print(f"         📄 Taille signature: {len(signature_digitale)} caractères")
            print()
        
        # 3. Récupérer aussi les invitations pour comparaison
        invitations_query = text("""
            SELECT 
                statut,
                cree_le,
                inscription_id
            FROM invitation_events 
            WHERE event_id = :event_id
            ORDER BY inscription_id
        """)
        
        invitations = session.exec(invitations_query.bindparams(event_id=event_id)).all()
        
        print(f"📧 Invitations trouvées: {len(invitations)}")
        print()
        
        for invitation in invitations:
            invitation_statut, invitation_cree_le, inscription_id = invitation
            
            print(f"   👤 Inscription ID: {inscription_id}")
            print(f"      📧 Statut invitation: {invitation_statut}")
            print(f"      📅 Invitation créée: {invitation_cree_le}")
            print()
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    simple_test()