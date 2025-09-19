-- Migration pour ajouter les champs business à la table suivimensuel existante
-- Script: add_business_fields_to_existing_suivimensuel.sql

-- Ajouter les nouveaux champs business à la table suivimensuel
ALTER TABLE suivimensuel 
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
ADD COLUMN IF NOT EXISTS modifie_le TIMESTAMP WITH TIME ZONE;

-- Ajouter des contraintes de validation pour les montants
ALTER TABLE suivimensuel 
ADD CONSTRAINT IF NOT EXISTS check_chiffre_affaires_actuel CHECK (chiffre_affaires_actuel >= 0),
ADD CONSTRAINT IF NOT EXISTS check_nb_stagiaires CHECK (nb_stagiaires >= 0),
ADD CONSTRAINT IF NOT EXISTS check_nb_alternants CHECK (nb_alternants >= 0),
ADD CONSTRAINT IF NOT EXISTS check_nb_cdd CHECK (nb_cdd >= 0),
ADD CONSTRAINT IF NOT EXISTS check_nb_cdi CHECK (nb_cdi >= 0),
ADD CONSTRAINT IF NOT EXISTS check_montant_subventions CHECK (montant_subventions_obtenues >= 0),
ADD CONSTRAINT IF NOT EXISTS check_montant_dettes_effectuees CHECK (montant_dettes_effectuees >= 0),
ADD CONSTRAINT IF NOT EXISTS check_montant_dettes_encours CHECK (montant_dettes_encours >= 0),
ADD CONSTRAINT IF NOT EXISTS check_montant_dettes_envisagees CHECK (montant_dettes_envisagees >= 0),
ADD CONSTRAINT IF NOT EXISTS check_montant_equity_effectue CHECK (montant_equity_effectue >= 0),
ADD CONSTRAINT IF NOT EXISTS check_montant_equity_encours CHECK (montant_equity_encours >= 0);

-- Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_suivimensuel_chiffre_affaires ON suivimensuel(chiffre_affaires_actuel);
CREATE INDEX IF NOT EXISTS idx_suivimensuel_employes ON suivimensuel(nb_stagiaires, nb_alternants, nb_cdd, nb_cdi);
CREATE INDEX IF NOT EXISTS idx_suivimensuel_subventions ON suivimensuel(montant_subventions_obtenues);
CREATE INDEX IF NOT EXISTS idx_suivimensuel_statut_juridique ON suivimensuel(statut_juridique);

-- Ajouter des commentaires pour documenter les champs
COMMENT ON COLUMN suivimensuel.chiffre_affaires_actuel IS 'Chiffre d affaires actuel en euros';
COMMENT ON COLUMN suivimensuel.nb_stagiaires IS 'Nombre de stagiaires employes';
COMMENT ON COLUMN suivimensuel.nb_alternants IS 'Nombre d alternants employes';
COMMENT ON COLUMN suivimensuel.nb_cdd IS 'Nombre de CDD employes';
COMMENT ON COLUMN suivimensuel.nb_cdi IS 'Nombre de CDI employes';
COMMENT ON COLUMN suivimensuel.montant_subventions_obtenues IS 'Montant des subventions obtenues en euros';
COMMENT ON COLUMN suivimensuel.organismes_financeurs IS 'Liste des organismes ayant finance';
COMMENT ON COLUMN suivimensuel.montant_dettes_effectuees IS 'Montant des dettes payees en euros';
COMMENT ON COLUMN suivimensuel.montant_dettes_encours IS 'Montant des dettes en cours en euros';
COMMENT ON COLUMN suivimensuel.montant_dettes_envisagees IS 'Montant des dettes prevues en euros';
COMMENT ON COLUMN suivimensuel.montant_equity_effectue IS 'Montant de levee de fonds equity realisee en euros';
COMMENT ON COLUMN suivimensuel.montant_equity_encours IS 'Montant de levee de fonds equity en cours en euros';
COMMENT ON COLUMN suivimensuel.statut_juridique IS 'Statut juridique de l entreprise (SAS, SARL, etc.)';
COMMENT ON COLUMN suivimensuel.adresse_entreprise IS 'Adresse de l entreprise si changement';
COMMENT ON COLUMN suivimensuel.situation_socioprofessionnelle IS 'Situation socioprofessionnelle du candidat';
COMMENT ON COLUMN suivimensuel.modifie_le IS 'Date de derniere modification';

-- Vérifier la structure de la table mise à jour
\d suivimensuel;

-- Afficher un message de confirmation
SELECT 'Migration terminee avec succes - Champs business ajoutes a suivimensuel' as message;
