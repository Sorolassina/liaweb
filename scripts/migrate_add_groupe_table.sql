-- Migration pour ajouter la gestion des groupes
-- À exécuter pour migrer de groupe_codev (string) vers groupe_id (relation)

-- Étape 1: Créer la table 'groupe'
CREATE TABLE IF NOT EXISTS groupe (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    capacite_max INTEGER,
    actif BOOLEAN DEFAULT TRUE,
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date_modification TIMESTAMP WITH TIME ZONE
);

-- Étape 2: Ajouter la colonne 'groupe_id' à 'decisionjurycandidat'
ALTER TABLE decisionjurycandidat 
ADD COLUMN IF NOT EXISTS groupe_id INTEGER;

-- Étape 3: Ajouter la contrainte de clé étrangère
ALTER TABLE decisionjurycandidat 
ADD CONSTRAINT fk_decisionjurycandidat_groupe 
FOREIGN KEY (groupe_id) REFERENCES groupe(id);

-- Étape 4: Créer un index sur groupe_id pour les performances
CREATE INDEX IF NOT EXISTS idx_decisionjurycandidat_groupe_id 
ON decisionjurycandidat(groupe_id);

-- Étape 5: Insérer quelques groupes de base
INSERT INTO groupe (nom, description, capacite_max, actif) VALUES
('Groupe Alpha', 'Groupe de codéveloppement Alpha', 12, true),
('Groupe Beta', 'Groupe de codéveloppement Beta', 12, true),
('Groupe Gamma', 'Groupe de codéveloppement Gamma', 12, true),
('Groupe Delta', 'Groupe de codéveloppement Delta', 12, true),
('Groupe Epsilon', 'Groupe de codéveloppement Epsilon', 12, true)
ON CONFLICT (nom) DO NOTHING;

-- Étape 6: Migrer les données existantes de groupe_codev vers groupe_id (si nécessaire)
-- Cette étape est optionnelle si vous voulez migrer les anciennes données
-- Vous pouvez l'adapter selon vos besoins

-- Exemple de migration des données existantes (à adapter selon vos données)
-- UPDATE decisionjurycandidat 
-- SET groupe_id = (SELECT id FROM groupe WHERE nom = 'Groupe Alpha')
-- WHERE groupe_codev = 'GROUPE_1';

-- Étape 7: Vérifier la migration
SELECT 'Migration terminée' as status;
SELECT 'Groupes créés:' as info;
SELECT id, nom, description, capacite_max, actif FROM groupe ORDER BY nom;

SELECT 'Colonnes de decisionjurycandidat:' as info;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'decisionjurycandidat' 
AND column_name IN ('groupe_id', 'groupe_codev')
ORDER BY column_name;
