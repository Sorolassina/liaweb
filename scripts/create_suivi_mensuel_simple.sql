-- Creation de la table suivi_mensuel avec metriques business
-- Script simplifie sans caracteres speciaux

-- Creer la table suivi_mensuel complete
CREATE TABLE IF NOT EXISTS suivi_mensuel (
    id SERIAL PRIMARY KEY,
    inscription_id INTEGER NOT NULL,
    mois DATE NOT NULL,
    
    -- Metriques business principales
    chiffre_affaires_actuel DECIMAL(15,2),
    
    -- Evolution des employes
    nb_stagiaires INTEGER DEFAULT 0,
    nb_alternants INTEGER DEFAULT 0,
    nb_cdd INTEGER DEFAULT 0,
    nb_cdi INTEGER DEFAULT 0,
    
    -- Subventions et financements
    montant_subventions_obtenues DECIMAL(15,2),
    organismes_financeurs TEXT,
    
    -- Dettes
    montant_dettes_effectuees DECIMAL(15,2),
    montant_dettes_encours DECIMAL(15,2),
    montant_dettes_envisagees DECIMAL(15,2),
    
    -- Levee de fonds equity
    montant_equity_effectue DECIMAL(15,2),
    montant_equity_encours DECIMAL(15,2),
    
    -- Informations entreprise
    statut_juridique VARCHAR(100),
    adresse_entreprise TEXT,
    
    -- Situation socioprofessionnelle
    situation_socioprofessionnelle VARCHAR(200),
    
    -- Metriques generales
    score_objectifs DECIMAL(5,2) CHECK (score_objectifs >= 0 AND score_objectifs <= 100),
    commentaire TEXT,
    
    -- Metadonnees
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    modifie_le TIMESTAMP WITH TIME ZONE,
    
    -- Contraintes
    CONSTRAINT fk_suivi_mensuel_inscription FOREIGN KEY (inscription_id) REFERENCES inscription(id) ON DELETE CASCADE,
    CONSTRAINT unique_suivi_inscription_mois UNIQUE (inscription_id, mois)
);

-- Ajouter des contraintes de validation pour les montants
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

-- Creer des index pour ameliorer les performances
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_inscription_id ON suivi_mensuel(inscription_id);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_mois ON suivi_mensuel(mois);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_chiffre_affaires ON suivi_mensuel(chiffre_affaires_actuel);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_employes ON suivi_mensuel(nb_stagiaires, nb_alternants, nb_cdd, nb_cdi);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_subventions ON suivi_mensuel(montant_subventions_obtenues);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_statut_juridique ON suivi_mensuel(statut_juridique);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_score ON suivi_mensuel(score_objectifs);

-- Ajouter des commentaires pour documenter les champs
COMMENT ON TABLE suivi_mensuel IS 'Suivi mensuel des candidats avec metriques business';
COMMENT ON COLUMN suivi_mensuel.id IS 'Identifiant unique du suivi';
COMMENT ON COLUMN suivi_mensuel.inscription_id IS 'Reference a l inscription';
COMMENT ON COLUMN suivi_mensuel.mois IS 'Mois du suivi (1er du mois)';
COMMENT ON COLUMN suivi_mensuel.chiffre_affaires_actuel IS 'Chiffre d affaires actuel en euros';
COMMENT ON COLUMN suivi_mensuel.nb_stagiaires IS 'Nombre de stagiaires employes';
COMMENT ON COLUMN suivi_mensuel.nb_alternants IS 'Nombre d alternants employes';
COMMENT ON COLUMN suivi_mensuel.nb_cdd IS 'Nombre de CDD employes';
COMMENT ON COLUMN suivi_mensuel.nb_cdi IS 'Nombre de CDI employes';
COMMENT ON COLUMN suivi_mensuel.montant_subventions_obtenues IS 'Montant des subventions obtenues en euros';
COMMENT ON COLUMN suivi_mensuel.organismes_financeurs IS 'Liste des organismes ayant finance';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_effectuees IS 'Montant des dettes payees en euros';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_encours IS 'Montant des dettes en cours en euros';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_envisagees IS 'Montant des dettes prevues en euros';
COMMENT ON COLUMN suivi_mensuel.montant_equity_effectue IS 'Montant de levee de fonds equity realisee en euros';
COMMENT ON COLUMN suivi_mensuel.montant_equity_encours IS 'Montant de levee de fonds equity en cours en euros';
COMMENT ON COLUMN suivi_mensuel.statut_juridique IS 'Statut juridique de l entreprise (SAS, SARL, etc.)';
COMMENT ON COLUMN suivi_mensuel.adresse_entreprise IS 'Adresse de l entreprise si changement';
COMMENT ON COLUMN suivi_mensuel.situation_socioprofessionnelle IS 'Situation socioprofessionnelle du candidat';
COMMENT ON COLUMN suivi_mensuel.score_objectifs IS 'Score global des objectifs (0-100)';
COMMENT ON COLUMN suivi_mensuel.commentaire IS 'Commentaires libres';
COMMENT ON COLUMN suivi_mensuel.cree_le IS 'Date de creation';
COMMENT ON COLUMN suivi_mensuel.modifie_le IS 'Date de derniere modification';

-- Verifier la structure de la table creee
\d suivi_mensuel;
