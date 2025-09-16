-- Script pour mettre à jour les valeurs existantes dans les tables codev
-- Pour correspondre aux enums Python (valeurs en minuscules)

-- Mettre à jour les valeurs de statut dans cyclecodev
UPDATE cyclecodev SET statut = 'planifie' WHERE statut = 'PLANIFIE';
UPDATE cyclecodev SET statut = 'en_cours' WHERE statut = 'EN_COURS';
UPDATE cyclecodev SET statut = 'termine' WHERE statut = 'TERMINE';
UPDATE cyclecodev SET statut = 'annule' WHERE statut = 'ANNULE';
UPDATE cyclecodev SET statut = 'suspendu' WHERE statut = 'SUSPENDU';

-- Mettre à jour les valeurs de statut dans groupecodev
UPDATE groupecodev SET statut = 'en_constitution' WHERE statut = 'EN_CONSTITUTION';
UPDATE groupecodev SET statut = 'complet' WHERE statut = 'COMPLET';
UPDATE groupecodev SET statut = 'en_cours' WHERE statut = 'EN_COURS';
UPDATE groupecodev SET statut = 'termine' WHERE statut = 'TERMINE';
UPDATE groupecodev SET statut = 'dissous' WHERE statut = 'DISSOUS';

-- Mettre à jour les valeurs de statut dans membregroupecodev
UPDATE membregroupecodev SET statut = 'actif' WHERE statut = 'ACTIF';
UPDATE membregroupecodev SET statut = 'inactif' WHERE statut = 'INACTIF';
UPDATE membregroupecodev SET statut = 'suspendu' WHERE statut = 'SUSPENDU';
UPDATE membregroupecodev SET statut = 'exclu' WHERE statut = 'EXCLU';

-- Mettre à jour les valeurs de statut dans seancecodev
UPDATE seancecodev SET statut = 'planifiee' WHERE statut = 'PLANIFIEE';
UPDATE seancecodev SET statut = 'en_cours' WHERE statut = 'EN_COURS';
UPDATE seancecodev SET statut = 'terminee' WHERE statut = 'TERMINEE';
UPDATE seancecodev SET statut = 'annulee' WHERE statut = 'ANNULEE';
UPDATE seancecodev SET statut = 'reportee' WHERE statut = 'REPORTEE';

-- Mettre à jour les valeurs de statut dans presentationcodev
UPDATE presentationcodev SET statut = 'en_attente' WHERE statut = 'EN_ATTENTE';
UPDATE presentationcodev SET statut = 'en_cours' WHERE statut = 'EN_COURS';
UPDATE presentationcodev SET statut = 'terminee' WHERE statut = 'TERMINEE';
UPDATE presentationcodev SET statut = 'engagement_pris' WHERE statut = 'ENGAGEMENT_PRIS';
UPDATE presentationcodev SET statut = 'test_en_cours' WHERE statut = 'TEST_EN_COURS';
UPDATE presentationcodev SET statut = 'retour_fait' WHERE statut = 'RETOUR_FAIT';

-- Mettre à jour les valeurs de type dans contributioncodev
UPDATE contributioncodev SET type_contribution = 'question' WHERE type_contribution = 'QUESTION';
UPDATE contributioncodev SET type_contribution = 'suggestion' WHERE type_contribution = 'SUGGESTION';
UPDATE contributioncodev SET type_contribution = 'experience' WHERE type_contribution = 'EXPERIENCE';
UPDATE contributioncodev SET type_contribution = 'conseil' WHERE type_contribution = 'CONSEIL';
UPDATE contributioncodev SET type_contribution = 'ressource' WHERE type_contribution = 'RESSOURCE';
UPDATE contributioncodev SET type_contribution = 'autre' WHERE type_contribution = 'AUTRE';

-- Mettre à jour les valeurs de statut dans participationseance
UPDATE participationseance SET statut_presence = 'present' WHERE statut_presence = 'PRESENT';
UPDATE participationseance SET statut_presence = 'absent' WHERE statut_presence = 'ABSENT';
UPDATE participationseance SET statut_presence = 'retard' WHERE statut_presence = 'RETARD';
UPDATE participationseance SET statut_presence = 'excuse' WHERE statut_presence = 'EXCUSE';

-- Vérifier les valeurs mises à jour
SELECT 'cyclecodev' as table_name, statut, COUNT(*) as count FROM cyclecodev GROUP BY statut
UNION ALL
SELECT 'groupecodev' as table_name, statut, COUNT(*) as count FROM groupecodev GROUP BY statut
UNION ALL
SELECT 'membregroupecodev' as table_name, statut, COUNT(*) as count FROM membregroupecodev GROUP BY statut
UNION ALL
SELECT 'seancecodev' as table_name, statut, COUNT(*) as count FROM seancecodev GROUP BY statut
UNION ALL
SELECT 'presentationcodev' as table_name, statut, COUNT(*) as count FROM presentationcodev GROUP BY statut
UNION ALL
SELECT 'contributioncodev' as table_name, type_contribution as statut, COUNT(*) as count FROM contributioncodev GROUP BY type_contribution
UNION ALL
SELECT 'participationseance' as table_name, statut_presence as statut, COUNT(*) as count FROM participationseance GROUP BY statut_presence
ORDER BY table_name, statut;

-- Message de confirmation
SELECT 'Valeurs mises à jour pour correspondre aux enums Python (minuscules) !' as message;
