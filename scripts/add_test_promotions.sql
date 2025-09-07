-- Script pour ajouter des promotions de test
-- À exécuter si la table promotion est vide

-- Vérifier s'il y a des programmes
SELECT 'Programmes disponibles:' as info;
SELECT id, code, nom FROM programme ORDER BY code;

-- Vérifier s'il y a des promotions
SELECT 'Promotions existantes:' as info;
SELECT id, programme_id, libelle FROM promotion ORDER BY libelle;

-- Ajouter des promotions de test si aucun programme n'a de promotion
INSERT INTO promotion (programme_id, libelle, capacite, date_debut, date_fin, actif)
SELECT 
    p.id as programme_id,
    CONCAT('Promotion ', EXTRACT(YEAR FROM CURRENT_DATE), ' - ', p.code) as libelle,
    20 as capacite,
    CURRENT_DATE as date_debut,
    CURRENT_DATE + INTERVAL '1 year' as date_fin,
    true as actif
FROM programme p
WHERE NOT EXISTS (
    SELECT 1 FROM promotion pr WHERE pr.programme_id = p.id
)
LIMIT 3;

-- Vérifier les promotions ajoutées
SELECT 'Promotions après ajout:' as info;
SELECT 
    pr.id,
    pr.libelle,
    pr.capacite,
    p.code as programme_code,
    pr.actif
FROM promotion pr
JOIN programme p ON pr.programme_id = p.id
ORDER BY pr.libelle;
