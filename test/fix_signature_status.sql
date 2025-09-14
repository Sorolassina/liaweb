-- Script SQL pour corriger les statuts de présence quand une signature existe
-- À exécuter directement dans PostgreSQL

-- 1. Voir les présences avec signature mais statut "en_attente"
SELECT 
    id,
    event_id,
    inscription_id,
    presence,
    CASE 
        WHEN signature_digitale IS NOT NULL THEN 'DIGITAL'
        WHEN signature_manuelle IS NOT NULL THEN 'MANUAL'
        ELSE 'AUCUNE'
    END as methode_signature,
    CASE 
        WHEN signature_digitale IS NOT NULL THEN LENGTH(signature_digitale)
        WHEN signature_manuelle IS NOT NULL THEN LENGTH(signature_manuelle)
        ELSE 0
    END as taille_signature
FROM presence_events 
WHERE (signature_digitale IS NOT NULL OR signature_manuelle IS NOT NULL)
AND presence = 'en_attente'
ORDER BY event_id, inscription_id;

-- 2. Corriger les statuts (mettre à "present" quand une signature existe)
UPDATE presence_events 
SET 
    presence = 'present',
    modifie_le = NOW()
WHERE (signature_digitale IS NOT NULL OR signature_manuelle IS NOT NULL)
AND presence = 'en_attente';

-- 3. Vérifier le résultat après correction
SELECT 
    id,
    event_id,
    inscription_id,
    presence,
    CASE 
        WHEN signature_digitale IS NOT NULL THEN 'DIGITAL'
        WHEN signature_manuelle IS NOT NULL THEN 'MANUAL'
        ELSE 'AUCUNE'
    END as methode_signature,
    CASE 
        WHEN signature_digitale IS NOT NULL THEN LENGTH(signature_digitale)
        WHEN signature_manuelle IS NOT NULL THEN LENGTH(signature_manuelle)
        ELSE 0
    END as taille_signature,
    modifie_le
FROM presence_events 
WHERE (signature_digitale IS NOT NULL OR signature_manuelle IS NOT NULL)
ORDER BY event_id, inscription_id;

-- 4. Statistiques finales
SELECT 
    'Présences avec signature' as type,
    COUNT(*) as total,
    COUNT(CASE WHEN presence = 'present' THEN 1 END) as present,
    COUNT(CASE WHEN presence = 'en_attente' THEN 1 END) as en_attente,
    COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absent,
    COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuse
FROM presence_events 
WHERE (signature_digitale IS NOT NULL OR signature_manuelle IS NOT NULL);
