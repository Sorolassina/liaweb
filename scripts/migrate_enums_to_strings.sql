-- Script pour migrer de enum PostgreSQL vers string libre
-- Ce script supprime les contraintes d'enum et permet la flexibilité totale

-- 1. Vérifier les types d'enum existants
SELECT typname, enumlabel 
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid 
WHERE typname IN ('decisionjury', 'groupecodev', 'typedocument', 'userrole')
ORDER BY typname, enumlabel;

-- 2. Migrer decisionjurycandidat.groupe_codev de enum vers text
-- (si la colonne est encore de type enum)

-- Vérifier le type actuel de la colonne
SELECT column_name, data_type, udt_name 
FROM information_schema.columns 
WHERE table_name = 'decisionjurycandidat' 
AND column_name = 'groupe_codev';

-- Si la colonne est encore de type enum, la convertir en text
DO $$ 
BEGIN
    -- Vérifier si la colonne est de type enum
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'decisionjurycandidat' 
        AND column_name = 'groupe_codev' 
        AND udt_name = 'groupecodev'
    ) THEN
        -- Créer une colonne temporaire de type text
        ALTER TABLE decisionjurycandidat ADD COLUMN groupe_codev_temp TEXT;
        
        -- Copier les données en convertissant l'enum en text
        UPDATE decisionjurycandidat 
        SET groupe_codev_temp = groupe_codev::text;
        
        -- Supprimer l'ancienne colonne et renommer la nouvelle
        ALTER TABLE decisionjurycandidat DROP COLUMN groupe_codev;
        ALTER TABLE decisionjurycandidat RENAME COLUMN groupe_codev_temp TO groupe_codev;
        
        RAISE NOTICE 'Colonne groupe_codev migrée de enum vers text';
    ELSE
        RAISE NOTICE 'Colonne groupe_codev déjà de type text ou autre';
    END IF;
END $$;

-- 3. Migrer decisionjurycandidat.decision de enum vers text
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'decisionjurycandidat' 
        AND column_name = 'decision' 
        AND udt_name = 'decisionjury'
    ) THEN
        ALTER TABLE decisionjurycandidat ADD COLUMN decision_temp TEXT;
        UPDATE decisionjurycandidat SET decision_temp = decision::text;
        ALTER TABLE decisionjurycandidat DROP COLUMN decision;
        ALTER TABLE decisionjurycandidat RENAME COLUMN decision_temp TO decision;
        RAISE NOTICE 'Colonne decision migrée de enum vers text';
    ELSE
        RAISE NOTICE 'Colonne decision déjà de type text ou autre';
    END IF;
END $$;

-- 4. Migrer document.type_document de enum vers text
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'document' 
        AND column_name = 'type_document' 
        AND udt_name = 'typedocument'
    ) THEN
        ALTER TABLE document ADD COLUMN type_document_temp TEXT;
        UPDATE document SET type_document_temp = type_document::text;
        ALTER TABLE document DROP COLUMN type_document;
        ALTER TABLE document RENAME COLUMN type_document_temp TO type_document;
        RAISE NOTICE 'Colonne type_document migrée de enum vers text';
    ELSE
        RAISE NOTICE 'Colonne type_document déjà de type text ou autre';
    END IF;
END $$;

-- 5. Migrer user.role de enum vers text
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user' 
        AND column_name = 'role' 
        AND udt_name = 'userrole'
    ) THEN
        ALTER TABLE "user" ADD COLUMN role_temp TEXT;
        UPDATE "user" SET role_temp = role::text;
        ALTER TABLE "user" DROP COLUMN role;
        ALTER TABLE "user" RENAME COLUMN role_temp TO role;
        RAISE NOTICE 'Colonne user.role migrée de enum vers text';
    ELSE
        RAISE NOTICE 'Colonne user.role déjà de type text ou autre';
    END IF;
END $$;

-- 6. Vérification finale
SELECT 'Migration terminée' as status;

-- Afficher les types de colonnes après migration
SELECT 
    table_name,
    column_name,
    data_type,
    udt_name,
    is_nullable
FROM information_schema.columns 
WHERE table_name IN ('decisionjurycandidat', 'document', 'user')
AND column_name IN ('groupe_codev', 'decision', 'type_document', 'role')
ORDER BY table_name, column_name;

-- Statistiques des valeurs après migration
SELECT 'decisionjurycandidat.decision' as table_column, decision as value, COUNT(*) as count
FROM decisionjurycandidat 
GROUP BY decision
UNION ALL
SELECT 'decisionjurycandidat.groupe_codev' as table_column, groupe_codev as value, COUNT(*) as count
FROM decisionjurycandidat 
WHERE groupe_codev IS NOT NULL
GROUP BY groupe_codev
UNION ALL
SELECT 'document.type_document' as table_column, type_document as value, COUNT(*) as count
FROM document 
GROUP BY type_document
UNION ALL
SELECT 'user.role' as table_column, role as value, COUNT(*) as count
FROM "user" 
GROUP BY role
ORDER BY table_column, count DESC;
