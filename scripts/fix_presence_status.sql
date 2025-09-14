-- Script de correction des statuts de présence
-- À exécuter dans PostgreSQL

-- 1. Vérifier les présences actuelles
SELECT 
    id,
    session_id,
    inscription_id,
    presence,
    methode_signature,
    CASE 
        WHEN signature_digitale IS NOT NULL AND signature_digitale != '' THEN 'OUI'
        ELSE 'NON'
    END as signature_digitale,
    CASE 
        WHEN signature_manuelle IS NOT NULL AND signature_manuelle != '' THEN 'OUI'
        ELSE 'NON'
    END as signature_manuelle,
    CASE 
        WHEN heure_arrivee IS NOT NULL THEN 'OUI'
        ELSE 'NON'
    END as heure_arrivee,
    cree_le
FROM presenceseminaire 
ORDER BY cree_le DESC;

-- 2. Corriger les statuts des présences qui ont des signatures mais sont marquées "absent"
UPDATE presenceseminaire 
SET 
    presence = 'present',
    modifie_le = NOW()
WHERE 
    presence = 'absent' 
    AND (
        (signature_digitale IS NOT NULL AND signature_digitale != '') 
        OR 
        (signature_manuelle IS NOT NULL AND signature_manuelle != '')
        OR 
        heure_arrivee IS NOT NULL
    );

-- 3. Vérifier les corrections effectuées
SELECT 
    COUNT(*) as total_presences,
    COUNT(CASE WHEN presence = 'present' THEN 1 END) as presents,
    COUNT(CASE WHEN presence = 'absent' THEN 1 END) as absents,
    COUNT(CASE WHEN presence = 'excuse' THEN 1 END) as excuses
FROM presenceseminaire;

-- 4. Afficher les présences corrigées
SELECT 
    id,
    session_id,
    inscription_id,
    presence,
    methode_signature,
    CASE 
        WHEN signature_digitale IS NOT NULL AND signature_digitale != '' THEN 'OUI'
        ELSE 'NON'
    END as signature_digitale,
    CASE 
        WHEN signature_manuelle IS NOT NULL AND signature_manuelle != '' THEN 'OUI'
        ELSE 'NON'
    END as signature_manuelle,
    heure_arrivee,
    modifie_le
FROM presenceseminaire 
WHERE presence = 'present'
ORDER BY modifie_le DESC;
