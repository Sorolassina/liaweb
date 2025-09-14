-- Migration de la colonne presence de enum vers texte
-- À exécuter seulement si votre colonne presence est encore de type enum

-- 1. Créer une colonne temporaire
ALTER TABLE presenceseminaire ADD COLUMN presence_temp TEXT;

-- 2. Copier les données en convertissant les enums
UPDATE presenceseminaire 
SET presence_temp = CASE 
    WHEN presence::text = 'ABSENT' THEN 'absent'
    WHEN presence::text = 'PRESENT' THEN 'present'
    WHEN presence::text = 'EXCUSE' THEN 'excuse'
    ELSE 'absent'
END;

-- 3. Supprimer l'ancienne colonne
ALTER TABLE presenceseminaire DROP COLUMN presence;

-- 4. Renommer la colonne temporaire
ALTER TABLE presenceseminaire RENAME COLUMN presence_temp TO presence;

-- 5. Définir la valeur par défaut
ALTER TABLE presenceseminaire ALTER COLUMN presence SET DEFAULT 'absent';

-- 6. Corriger les statuts des présences avec signatures
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
