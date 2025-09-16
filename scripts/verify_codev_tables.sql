-- Script de vérification des tables codev
-- À exécuter après avoir créé les tables

-- Vérifier que toutes les tables existent
SELECT 
    table_name,
    CASE 
        WHEN table_name IN ('cyclecodev', 'groupecodev', 'membregroupecodev', 'seancecodev', 'presentationcodev', 'contributioncodev', 'participationseance') 
        THEN '✅ Table créée'
        ELSE '❌ Table manquante'
    END as statut
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND (table_name LIKE '%codev%' OR table_name = 'participationseance')
ORDER BY table_name;

-- Vérifier les permissions pour l'utilisateur liauser
SELECT 
    table_name,
    privilege_type
FROM information_schema.table_privileges 
WHERE grantee = 'liauser' 
AND table_name LIKE '%codev%'
ORDER BY table_name, privilege_type;

-- Test d'insertion simple (optionnel)
-- INSERT INTO cyclecodev (nom, programme_id, date_debut, date_fin) 
-- VALUES ('Test Cycle', 1, '2024-01-01', '2024-12-31');

-- SELECT 'Test réussi' as message;
