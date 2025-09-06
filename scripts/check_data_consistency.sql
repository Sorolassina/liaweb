-- Script pour vérifier la cohérence des données
-- À exécuter dans PostgreSQL

-- 1. Vérifier toutes les préinscriptions du programme ACD
SELECT 'Préinscriptions ACD:' as info;
SELECT 
    p.id as preinscription_id,
    p.candidat_id,
    c.nom,
    c.prenom,
    c.email,
    p.cree_le,
    CASE 
        WHEN c.id IS NULL THEN 'CANDIDAT SUPPRIMÉ'
        ELSE 'OK'
    END as statut
FROM preinscription p
JOIN programme pr ON pr.id = p.programme_id
LEFT JOIN candidat c ON c.id = p.candidat_id
WHERE pr.code = 'ACD'
ORDER BY p.id;

-- 2. Vérifier spécifiquement la préinscription ID 6
SELECT 'Préinscription ID 6:' as info;
SELECT 
    p.id,
    p.candidat_id,
    p.programme_id,
    c.nom,
    c.prenom,
    pr.code as programme_code
FROM preinscription p
LEFT JOIN candidat c ON c.id = p.candidat_id
LEFT JOIN programme pr ON pr.id = p.programme_id
WHERE p.id = 6;

-- 3. Compter les préinscriptions valides vs orphelines
SELECT 'Résumé:' as info;
SELECT 
    COUNT(*) as total_preinscriptions,
    COUNT(c.id) as preinscriptions_valides,
    COUNT(*) - COUNT(c.id) as preinscriptions_orphelines
FROM preinscription p
JOIN programme pr ON pr.id = p.programme_id
LEFT JOIN candidat c ON c.id = p.candidat_id
WHERE pr.code = 'ACD';
