-- Script pour supprimer l'ancienne colonne groupe_codev
-- À exécuter APRÈS avoir vérifié que la migration fonctionne correctement

-- ATTENTION: Ce script supprime définitivement la colonne groupe_codev
-- Assurez-vous que toutes les données ont été migrées vers groupe_id

-- Étape 1: Vérifier qu'il n'y a plus de données dans groupe_codev
SELECT 'Vérification des données restantes dans groupe_codev:' as info;
SELECT COUNT(*) as count_non_null_groupe_codev 
FROM decisionjurycandidat 
WHERE groupe_codev IS NOT NULL AND groupe_codev != '';

-- Si le count est > 0, ne pas exécuter la suite du script
-- Migrer d'abord les données restantes

-- Étape 2: Supprimer la colonne groupe_codev
-- DÉCOMMENTER LES LIGNES SUIVANTES UNIQUEMENT SI LA VÉRIFICATION CI-DESSUS RETOURNE 0

-- ALTER TABLE decisionjurycandidat DROP COLUMN IF EXISTS groupe_codev;

-- Étape 3: Vérifier la suppression
-- SELECT 'Colonnes restantes de decisionjurycandidat:' as info;
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'decisionjurycandidat' 
-- ORDER BY column_name;

SELECT 'Script de nettoyage prêt. Décommentez les lignes ALTER TABLE si la vérification est OK.' as status;
