-- Script SQL pour mettre à jour les rôles des utilisateurs
-- de l'ancien format enum vers le nouveau format string

-- Afficher les utilisateurs actuels avant la mise à jour
SELECT id, email, role, nom_complet FROM "user" ORDER BY id;

-- Mettre à jour les rôles des utilisateurs existants
UPDATE "user" 
SET role = CASE 
    WHEN role = 'ADMINISTRATEUR' THEN 'administrateur'
    WHEN role = 'DIRECTEUR_GENERAL' THEN 'directeur_general'
    WHEN role = 'DIRECTEUR_TECHNIQUE' THEN 'directeur_technique'
    WHEN role = 'RESPONSABLE_PROGRAMME' THEN 'responsable_programme'
    WHEN role = 'CONSEILLER' THEN 'conseiller'
    WHEN role = 'COORDINATEUR' THEN 'coordinateur'
    WHEN role = 'FORMATEUR' THEN 'formateur'
    WHEN role = 'EVALUATEUR' THEN 'evaluateur'
    WHEN role = 'ACCOMPAGNATEUR' THEN 'accompagnateur'
    WHEN role = 'DRH' THEN 'drh'
    WHEN role = 'RESPONSABLE_STRUCTURE' THEN 'responsable_structure'
    WHEN role = 'COACH_EXTERNE' THEN 'coach_externe'
    WHEN role = 'JURY_EXTERNE' THEN 'jury_externe'
    WHEN role = 'CANDIDAT' THEN 'candidat'
    WHEN role = 'RESPONSABLE_COMMUNICATION' THEN 'responsable_communication'
    WHEN role = 'ASSISTANT_COMMUNICATION' THEN 'assistant_communication'
    ELSE role  -- Garder le rôle tel quel s'il est déjà au bon format
END
WHERE role IN (
    'ADMINISTRATEUR', 'DIRECTEUR_GENERAL', 'DIRECTEUR_TECHNIQUE',
    'RESPONSABLE_PROGRAMME', 'CONSEILLER', 'COORDINATEUR',
    'FORMATEUR', 'EVALUATEUR', 'ACCOMPAGNATEUR', 'DRH',
    'RESPONSABLE_STRUCTURE', 'COACH_EXTERNE', 'JURY_EXTERNE',
    'CANDIDAT', 'RESPONSABLE_COMMUNICATION', 'ASSISTANT_COMMUNICATION'
);

-- Afficher le nombre d'utilisateurs mis à jour
SELECT COUNT(*) as utilisateurs_mis_a_jour 
FROM "user" 
WHERE role IN (
    'administrateur', 'directeur_general', 'directeur_technique',
    'responsable_programme', 'conseiller', 'coordinateur',
    'formateur', 'evaluateur', 'accompagnateur', 'drh',
    'responsable_structure', 'coach_externe', 'jury_externe',
    'candidat', 'responsable_communication', 'assistant_communication'
);

-- Afficher les utilisateurs après la mise à jour
SELECT id, email, role, nom_complet FROM "user" ORDER BY id;

-- Vérifier s'il reste des rôles au format ancien
SELECT DISTINCT role FROM "user" 
WHERE role NOT IN (
    'administrateur', 'directeur_general', 'directeur_technique',
    'responsable_programme', 'conseiller', 'coordinateur',
    'formateur', 'evaluateur', 'accompagnateur', 'drh',
    'responsable_structure', 'coach_externe', 'jury_externe',
    'candidat', 'responsable_communication', 'assistant_communication'
);
