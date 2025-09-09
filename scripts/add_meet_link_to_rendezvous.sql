-- Ajouter le champ meet_link à la table rendezvous
-- Ce champ stockera le lien Google Meet unique pour chaque RDV

ALTER TABLE rendezvous 
ADD COLUMN meet_link TEXT;

-- Commentaire pour expliquer le champ
COMMENT ON COLUMN rendezvous.meet_link IS 'Lien Google Meet unique pour la visioconférence';

-- Index pour optimiser les recherches
CREATE INDEX idx_rendezvous_meet_link ON rendezvous(meet_link);

-- Vérification
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'rendezvous' 
AND column_name = 'meet_link';
