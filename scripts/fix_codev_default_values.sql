-- Script pour corriger les valeurs par défaut dans les tables codev
-- Les enums Python utilisent des valeurs en minuscules, donc nous devons les utiliser en base

-- Corriger les valeurs par défaut dans cyclecodev
ALTER TABLE cyclecodev ALTER COLUMN statut SET DEFAULT 'planifie';

-- Corriger les valeurs par défaut dans groupecodev  
ALTER TABLE groupecodev ALTER COLUMN statut SET DEFAULT 'en_constitution';

-- Corriger les valeurs par défaut dans membregroupecodev
ALTER TABLE membregroupecodev ALTER COLUMN statut SET DEFAULT 'actif';

-- Corriger les valeurs par défaut dans seancecodev
ALTER TABLE seancecodev ALTER COLUMN statut SET DEFAULT 'planifiee';

-- Corriger les valeurs par défaut dans presentationcodev
ALTER TABLE presentationcodev ALTER COLUMN statut SET DEFAULT 'en_attente';

-- Corriger les valeurs par défaut dans contributioncodev
ALTER TABLE contributioncodev ALTER COLUMN type_contribution SET DEFAULT 'suggestion';

-- Corriger les valeurs par défaut dans participationseance
ALTER TABLE participationseance ALTER COLUMN statut_presence SET DEFAULT 'absent';

-- Vérifier les valeurs par défaut actuelles
SELECT 
    table_name,
    column_name,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name LIKE '%codev%'
AND column_name IN ('statut', 'type_contribution', 'statut_presence')
ORDER BY table_name, column_name;

-- Message de confirmation
SELECT 'Valeurs par défaut corrigées pour correspondre aux enums Python !' as message;
