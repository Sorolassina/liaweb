-- Script de vérification détaillée avant/après correction

-- AVANT correction
SELECT 
    'AVANT CORRECTION' as etape,
    presence,
    COUNT(*) as nombre,
    COUNT(CASE WHEN signature_digitale IS NOT NULL AND signature_digitale != '' THEN 1 END) as avec_signature_digitale,
    COUNT(CASE WHEN signature_manuelle IS NOT NULL AND signature_manuelle != '' THEN 1 END) as avec_signature_manuelle,
    COUNT(CASE WHEN heure_arrivee IS NOT NULL THEN 1 END) as avec_heure_arrivee
FROM presenceseminaire 
GROUP BY presence;

-- Exécuter la correction
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

-- APRÈS correction
SELECT 
    'APRÈS CORRECTION' as etape,
    presence,
    COUNT(*) as nombre,
    COUNT(CASE WHEN signature_digitale IS NOT NULL AND signature_digitale != '' THEN 1 END) as avec_signature_digitale,
    COUNT(CASE WHEN signature_manuelle IS NOT NULL AND signature_manuelle != '' THEN 1 END) as avec_signature_manuelle,
    COUNT(CASE WHEN heure_arrivee IS NOT NULL THEN 1 END) as avec_heure_arrivee
FROM presenceseminaire 
GROUP BY presence;
