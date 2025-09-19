-- Migration pour étendre le modèle SuiviMensuel avec des métriques business
-- Script: add_business_fields_to_suivi_mensuel.sql

-- Ajouter les nouveaux champs au modèle SuiviMensuel
ALTER TABLE suivi_mensuel 
ADD COLUMN IF NOT EXISTS chiffre_affaires_actuel DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS nb_stagiaires INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS nb_alternants INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS nb_cdd INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS nb_cdi INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS montant_subventions_obtenues DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS organismes_financeurs TEXT,
ADD COLUMN IF NOT EXISTS montant_dettes_effectuees DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS montant_dettes_encours DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS montant_dettes_envisagees DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS montant_equity_effectue DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS montant_equity_encours DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS statut_juridique VARCHAR(100),
ADD COLUMN IF NOT EXISTS adresse_entreprise TEXT,
ADD COLUMN IF NOT EXISTS situation_socioprofessionnelle VARCHAR(200),
ADD COLUMN IF NOT EXISTS modifie_le TIMESTAMP;

-- Ajouter des contraintes de validation
ALTER TABLE suivi_mensuel 
ADD CONSTRAINT check_chiffre_affaires_actuel CHECK (chiffre_affaires_actuel >= 0),
ADD CONSTRAINT check_nb_stagiaires CHECK (nb_stagiaires >= 0),
ADD CONSTRAINT check_nb_alternants CHECK (nb_alternants >= 0),
ADD CONSTRAINT check_nb_cdd CHECK (nb_cdd >= 0),
ADD CONSTRAINT check_nb_cdi CHECK (nb_cdi >= 0),
ADD CONSTRAINT check_montant_subventions CHECK (montant_subventions_obtenues >= 0),
ADD CONSTRAINT check_montant_dettes_effectuees CHECK (montant_dettes_effectuees >= 0),
ADD CONSTRAINT check_montant_dettes_encours CHECK (montant_dettes_encours >= 0),
ADD CONSTRAINT check_montant_dettes_envisagees CHECK (montant_dettes_envisagees >= 0),
ADD CONSTRAINT check_montant_equity_effectue CHECK (montant_equity_effectue >= 0),
ADD CONSTRAINT check_montant_equity_encours CHECK (montant_equity_encours >= 0);

-- Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_chiffre_affaires ON suivi_mensuel(chiffre_affaires_actuel);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_employes ON suivi_mensuel(nb_stagiaires, nb_alternants, nb_cdd, nb_cdi);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_subventions ON suivi_mensuel(montant_subventions_obtenues);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_statut_juridique ON suivi_mensuel(statut_juridique);

-- Ajouter des commentaires pour documenter les champs
COMMENT ON COLUMN suivi_mensuel.chiffre_affaires_actuel IS 'Chiffre d''affaires actuel en euros';
COMMENT ON COLUMN suivi_mensuel.nb_stagiaires IS 'Nombre de stagiaires employés';
COMMENT ON COLUMN suivi_mensuel.nb_alternants IS 'Nombre d''alternants employés';
COMMENT ON COLUMN suivi_mensuel.nb_cdd IS 'Nombre de CDD employés';
COMMENT ON COLUMN suivi_mensuel.nb_cdi IS 'Nombre de CDI employés';
COMMENT ON COLUMN suivi_mensuel.montant_subventions_obtenues IS 'Montant des subventions obtenues en euros';
COMMENT ON COLUMN suivi_mensuel.organismes_financeurs IS 'Liste des organismes ayant financé';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_effectuees IS 'Montant des dettes payées en euros';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_encours IS 'Montant des dettes en cours en euros';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_envisagees IS 'Montant des dettes prévues en euros';
COMMENT ON COLUMN suivi_mensuel.montant_equity_effectue IS 'Montant de levée de fonds equity réalisée en euros';
COMMENT ON COLUMN suivi_mensuel.montant_equity_encours IS 'Montant de levée de fonds equity en cours en euros';
COMMENT ON COLUMN suivi_mensuel.statut_juridique IS 'Statut juridique de l''entreprise (SAS, SARL, etc.)';
COMMENT ON COLUMN suivi_mensuel.adresse_entreprise IS 'Adresse de l''entreprise si changement';
COMMENT ON COLUMN suivi_mensuel.situation_socioprofessionnelle IS 'Situation socioprofessionnelle du candidat';
COMMENT ON COLUMN suivi_mensuel.modifie_le IS 'Date de dernière modification';

-- Insérer des données de test pour vérifier le fonctionnement
INSERT INTO suivi_mensuel (
    inscription_id, 
    mois, 
    chiffre_affaires_actuel,
    nb_stagiaires,
    nb_alternants,
    nb_cdd,
    nb_cdi,
    montant_subventions_obtenues,
    organismes_financeurs,
    montant_dettes_effectuees,
    montant_dettes_encours,
    montant_dettes_envisagees,
    montant_equity_effectue,
    montant_equity_encours,
    statut_juridique,
    adresse_entreprise,
    situation_socioprofessionnelle,
    score_objectifs,
    commentaire
) VALUES (
    1, -- inscription_id (à adapter selon vos données)
    '2024-01-01', -- mois
    50000.00, -- chiffre_affaires_actuel
    2, -- nb_stagiaires
    1, -- nb_alternants
    3, -- nb_cdd
    5, -- nb_cdi
    10000.00, -- montant_subventions_obtenues
    'Bpifrance, Région Île-de-France', -- organismes_financeurs
    5000.00, -- montant_dettes_effectuees
    15000.00, -- montant_dettes_encours
    8000.00, -- montant_dettes_envisagees
    200000.00, -- montant_equity_effectue
    0.00, -- montant_equity_encours
    'SAS', -- statut_juridique
    '123 Rue de la Tech, 75001 Paris', -- adresse_entreprise
    'Dirigeant d''entreprise', -- situation_socioprofessionnelle
    85.0, -- score_objectifs
    'Très bonne évolution du chiffre d''affaires et de l''équipe' -- commentaire
) ON CONFLICT (inscription_id, mois) DO NOTHING;

-- Vérifier la structure de la table
\d suivi_mensuel;

-- Afficher les données de test
SELECT 
    sm.id,
    sm.mois,
    sm.chiffre_affaires_actuel,
    sm.nb_stagiaires + sm.nb_alternants + sm.nb_cdd + sm.nb_cdi as total_employes,
    sm.montant_subventions_obtenues,
    sm.statut_juridique,
    sm.score_objectifs
FROM suivi_mensuel sm
WHERE sm.chiffre_affaires_actuel IS NOT NULL
ORDER BY sm.mois DESC;
