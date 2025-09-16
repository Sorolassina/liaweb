-- Script pour corriger les valeurs d'enum dans les tables codev
-- À exécuter dans PostgreSQL

-- Mettre à jour les valeurs de statut dans cyclecodev
UPDATE cyclecodev SET statut = 'PLANIFIE' WHERE statut = 'planifie';
UPDATE cyclecodev SET statut = 'EN_COURS' WHERE statut = 'en_cours';
UPDATE cyclecodev SET statut = 'TERMINE' WHERE statut = 'termine';
UPDATE cyclecodev SET statut = 'SUSPENDU' WHERE statut = 'suspendu';

-- Mettre à jour les valeurs de statut dans groupecodev
UPDATE groupecodev SET statut = 'EN_CONSTITUTION' WHERE statut = 'en_constitution';
UPDATE groupecodev SET statut = 'ACTIF' WHERE statut = 'actif';
UPDATE groupecodev SET statut = 'COMPLET' WHERE statut = 'complet';
UPDATE groupecodev SET statut = 'TERMINE' WHERE statut = 'termine';

-- Mettre à jour les valeurs de statut dans membregroupecodev
UPDATE membregroupecodev SET statut = 'ACTIF' WHERE statut = 'actif';
UPDATE membregroupecodev SET statut = 'INACTIF' WHERE statut = 'inactif';
UPDATE membregroupecodev SET statut = 'EXCLU' WHERE statut = 'exclu';

-- Mettre à jour les valeurs de statut dans seancecodev
UPDATE seancecodev SET statut = 'PLANIFIEE' WHERE statut = 'planifiee';
UPDATE seancecodev SET statut = 'EN_COURS' WHERE statut = 'en_cours';
UPDATE seancecodev SET statut = 'TERMINEE' WHERE statut = 'terminee';
UPDATE seancecodev SET statut = 'ANNULEE' WHERE statut = 'annulee';

-- Mettre à jour les valeurs de statut dans presentationcodev
UPDATE presentationcodev SET statut = 'EN_ATTENTE' WHERE statut = 'en_attente';
UPDATE presentationcodev SET statut = 'EN_COURS' WHERE statut = 'en_cours';
UPDATE presentationcodev SET statut = 'ENGAGEMENT_PRIS' WHERE statut = 'engagement_pris';
UPDATE presentationcodev SET statut = 'TEST_EN_COURS' WHERE statut = 'test_en_cours';
UPDATE presentationcodev SET statut = 'RETOUR_FAIT' WHERE statut = 'retour_fait';

-- Mettre à jour les valeurs de statut dans contributioncodev
UPDATE contributioncodev SET type_contribution = 'SUGGESTION' WHERE type_contribution = 'suggestion';
UPDATE contributioncodev SET type_contribution = 'QUESTION' WHERE type_contribution = 'question';
UPDATE contributioncodev SET type_contribution = 'EXPERIENCE' WHERE type_contribution = 'experience';
UPDATE contributioncodev SET type_contribution = 'CONSEIL' WHERE type_contribution = 'conseil';

-- Mettre à jour les valeurs de statut dans participationseance
UPDATE participationseance SET statut_presence = 'PRESENT' WHERE statut_presence = 'present';
UPDATE participationseance SET statut_presence = 'ABSENT' WHERE statut_presence = 'absent';
UPDATE participationseance SET statut_presence = 'RETARD' WHERE statut_presence = 'retard';
UPDATE participationseance SET statut_presence = 'EXCUSE' WHERE statut_presence = 'excuse';

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
SELECT 'Valeurs d''enum corrigées avec succès !' as message;
