-- Script SQL pour convertir la colonne role de enum vers text
-- et mettre à jour les rôles des utilisateurs

-- 1. Afficher les utilisateurs actuels avant la mise à jour
SELECT id, email, role, nom_complet FROM "user" ORDER BY id;

-- 2. Créer une colonne temporaire de type text
ALTER TABLE "user" ADD COLUMN role_temp TEXT;

-- 3. Copier les valeurs de role vers role_temp avec conversion
UPDATE "user" 
SET role_temp = CASE 
    WHEN role::text = 'ADMINISTRATEUR' THEN 'administrateur'
    WHEN role::text = 'DIRECTEUR_GENERAL' THEN 'directeur_general'
    WHEN role::text = 'DIRECTEUR_TECHNIQUE' THEN 'directeur_technique'
    WHEN role::text = 'RESPONSABLE_PROGRAMME' THEN 'responsable_programme'
    WHEN role::text = 'CONSEILLER' THEN 'conseiller'
    WHEN role::text = 'COORDINATEUR' THEN 'coordinateur'
    WHEN role::text = 'FORMATEUR' THEN 'formateur'
    WHEN role::text = 'EVALUATEUR' THEN 'evaluateur'
    WHEN role::text = 'ACCOMPAGNATEUR' THEN 'accompagnateur'
    WHEN role::text = 'DRH' THEN 'drh'
    WHEN role::text = 'RESPONSABLE_STRUCTURE' THEN 'responsable_structure'
    WHEN role::text = 'COACH_EXTERNE' THEN 'coach_externe'
    WHEN role::text = 'JURY_EXTERNE' THEN 'jury_externe'
    WHEN role::text = 'CANDIDAT' THEN 'candidat'
    WHEN role::text = 'RESPONSABLE_COMMUNICATION' THEN 'responsable_communication'
    WHEN role::text = 'ASSISTANT_COMMUNICATION' THEN 'assistant_communication'
    ELSE role::text  -- Garder le rôle tel quel s'il est déjà au bon format
END;

-- 4. Supprimer l'ancienne colonne role
ALTER TABLE "user" DROP COLUMN role;

-- 5. Renommer role_temp en role
ALTER TABLE "user" RENAME COLUMN role_temp TO role;

-- 6. Ajouter une contrainte NOT NULL si nécessaire
ALTER TABLE "user" ALTER COLUMN role SET NOT NULL;

-- 7. Afficher le nombre d'utilisateurs mis à jour
SELECT COUNT(*) as utilisateurs_mis_a_jour 
FROM "user" 
WHERE role IN (
    'administrateur', 'directeur_general', 'directeur_technique',
    'responsable_programme', 'conseiller', 'coordinateur',
    'formateur', 'evaluateur', 'accompagnateur', 'drh',
    'responsable_structure', 'coach_externe', 'jury_externe',
    'candidat', 'responsable_communication', 'assistant_communication'
);

-- 8. Afficher les utilisateurs après la mise à jour
SELECT id, email, role, nom_complet FROM "user" ORDER BY id;

-- 9. Vérifier le type de la colonne role
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'user' AND column_name = 'role';
