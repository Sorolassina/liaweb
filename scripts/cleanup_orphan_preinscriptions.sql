-- Script pour nettoyer les préinscriptions orphelines
-- À exécuter dans PostgreSQL

-- Supprimer les préinscriptions dont le candidat n'existe plus
DELETE FROM preinscription 
WHERE candidat_id NOT IN (SELECT id FROM candidat)
AND programme_id = (SELECT id FROM programme WHERE code = 'ACD');

-- Afficher le résultat
SELECT 'Préinscriptions après nettoyage:' as info;
SELECT COUNT(*) as total_preinscriptions_acd
FROM preinscription p
JOIN programme pr ON pr.id = p.programme_id
WHERE pr.code = 'ACD';
