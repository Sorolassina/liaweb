-- Script SQL pour corriger les statuts par défaut dans la base de données
-- Applique la nouvelle logique : en_attente par défaut pour les événements futurs

-- ==============================================
-- CORRECTION DES PRÉSENCES DE SÉMINAIRES
-- ==============================================

-- 1. Mettre à jour les présences des séminaires selon la nouvelle logique
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
  );

-- 2. Garder 'absent' pour les invitations refusées (même si événement futur)
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
  );

-- 3. Mettre 'absent' pour les événements passés sans signature
UPDATE presenceseminaire 
SET presence = 'absent'
WHERE presence = 'en_attente'
  AND session_id IN (
    SELECT s.id 
    FROM sessionseminaire s 
    WHERE s.date_session < CURRENT_DATE
  )
  AND (signature_digitale IS NULL OR signature_digitale = '')
  AND (signature_manuelle IS NULL OR signature_manuelle = '');

-- ==============================================
-- CORRECTION DES PRÉSENCES D'ÉVÉNEMENTS
-- ==============================================

-- 4. Mettre à jour les présences des événements selon la nouvelle logique
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
  );

-- 5. Garder 'absent' pour les invitations refusées (même si événement futur)
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
  );

-- 6. Mettre 'absent' pour les événements passés sans signature
UPDATE presence_events 
SET presence = 'absent'
WHERE presence = 'en_attente'
  AND event_id IN (
    SELECT e.id 
    FROM events e 
    WHERE e.date_fin < CURRENT_DATE
  )
  AND (signature_digitale IS NULL OR signature_digitale = '')
  AND (signature_manuelle IS NULL OR signature_manuelle = '');

-- ==============================================
-- VÉRIFICATION DES RÉSULTATS
-- ==============================================

-- 7. Afficher les statistiques des séminaires après correction
SELECT 
    'SÉMINAIRES' as type,
    COUNT(*) as total,
    COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
    COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
    COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse,
    COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente
FROM presenceseminaire;

-- 8. Afficher les statistiques des événements après correction
SELECT 
    'ÉVÉNEMENTS' as type,
    COUNT(*) as total,
    COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
    COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
    COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse,
    COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente
FROM presence_events;

-- 9. Détail des séminaires par statut et date
SELECT 
    s.titre as session_titre,
    s.date_session,
    CASE 
        WHEN s.date_session < CURRENT_DATE THEN 'PASSÉ'
        ELSE 'FUTUR'
    END as statut_date,
    COUNT(*) as total_presences,
    COUNT(CASE WHEN p.presence = 'present' THEN 1 END) as present,
    COUNT(CASE WHEN p.presence = 'absent' THEN 1 END) as absent,
    COUNT(CASE WHEN p.presence = 'excuse' THEN 1 END) as excuse,
    COUNT(CASE WHEN p.presence = 'en_attente' THEN 1 END) as en_attente
FROM presenceseminaire p
JOIN sessionseminaire s ON p.session_id = s.id
GROUP BY s.id, s.titre, s.date_session
ORDER BY s.date_session DESC;

-- 10. Détail des événements par statut et date
SELECT 
    e.titre as event_titre,
    e.date_fin,
    CASE 
        WHEN e.date_fin < CURRENT_DATE THEN 'PASSÉ'
        ELSE 'FUTUR'
    END as statut_date,
    COUNT(*) as total_presences,
    COUNT(CASE WHEN p.presence = 'present' THEN 1 END) as present,
    COUNT(CASE WHEN p.presence = 'absent' THEN 1 END) as absent,
    COUNT(CASE WHEN p.presence = 'excuse' THEN 1 END) as excuse,
    COUNT(CASE WHEN p.presence = 'en_attente' THEN 1 END) as en_attente
FROM presence_events p
JOIN events e ON p.event_id = e.id
GROUP BY e.id, e.titre, e.date_fin
ORDER BY e.date_fin DESC;
