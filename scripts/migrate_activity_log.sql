-- Script SQL pour ajouter les colonnes user_nom_complet et user_role à la table activitylog
-- À exécuter dans PostgreSQL

-- 1. Vérifier la structure actuelle de la table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'activitylog' 
ORDER BY ordinal_position;

-- 2. Ajouter la colonne user_nom_complet si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'activitylog' AND column_name = 'user_nom_complet'
    ) THEN
        ALTER TABLE activitylog ADD COLUMN user_nom_complet VARCHAR(255);
        RAISE NOTICE 'Colonne user_nom_complet ajoutée';
    ELSE
        RAISE NOTICE 'Colonne user_nom_complet existe déjà';
    END IF;
END $$;

-- 3. Ajouter la colonne user_role si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'activitylog' AND column_name = 'user_role'
    ) THEN
        ALTER TABLE activitylog ADD COLUMN user_role VARCHAR(50);
        RAISE NOTICE 'Colonne user_role ajoutée';
    ELSE
        RAISE NOTICE 'Colonne user_role existe déjà';
    END IF;
END $$;

-- 4. Renommer la colonne ip en ip_address si elle existe
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'activitylog' AND column_name = 'ip'
    ) THEN
        ALTER TABLE activitylog RENAME COLUMN ip TO ip_address;
        RAISE NOTICE 'Colonne ip renommée en ip_address';
    ELSE
        RAISE NOTICE 'Colonne ip n''existe pas';
    END IF;
END $$;

-- 5. Ajouter la colonne ip_address si elle n'existe pas du tout
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'activitylog' AND column_name = 'ip_address'
    ) THEN
        ALTER TABLE activitylog ADD COLUMN ip_address VARCHAR(45);
        RAISE NOTICE 'Colonne ip_address ajoutée';
    ELSE
        RAISE NOTICE 'Colonne ip_address existe déjà';
    END IF;
END $$;

-- 6. Mettre à jour les logs existants avec les données utilisateur
UPDATE activitylog 
SET 
    user_nom_complet = u.nom_complet,
    user_role = u.role
FROM "user" u
WHERE activitylog.user_id = u.id 
  AND activitylog.user_nom_complet IS NULL;

-- 7. Afficher les statistiques après migration
SELECT 
    COUNT(*) as total_logs,
    COUNT(user_nom_complet) as logs_with_name,
    COUNT(user_role) as logs_with_role,
    COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as logs_with_user_id
FROM activitylog;

-- 8. Vérifier la nouvelle structure de la table
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'activitylog' 
ORDER BY ordinal_position;
