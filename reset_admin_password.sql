-- =====================================================
-- RÉINITIALISATION DU MOT DE PASSE ADMINISTRATEUR
-- =====================================================

-- Script pour réinitialiser le mot de passe de l'administrateur
-- Le mot de passe par défaut sera 'admin123' (à changer après la première connexion)

DO $$
DECLARE
    admin_email VARCHAR := 'sorolassina58@gmail.com';
    new_password_hash VARCHAR;
    admin_exists BOOLEAN;
BEGIN
    -- Vérifier si l'administrateur existe
    SELECT EXISTS(SELECT 1 FROM "user" WHERE email = admin_email) INTO admin_exists;
    
    IF admin_exists THEN
        RAISE NOTICE '👤 Administrateur trouvé: %', admin_email;
        
        -- Générer le hash du mot de passe 'admin123'
        -- Note: En production, utilisez une méthode plus sécurisée
        new_password_hash := '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/8Qz8Qz2'; -- admin123
        
        -- Mettre à jour le mot de passe
        UPDATE "user" 
        SET mot_de_passe_hash = new_password_hash
        WHERE email = admin_email;
        
        RAISE NOTICE '✅ Mot de passe réinitialisé pour: %', admin_email;
        RAISE NOTICE '🔑 Nouveau mot de passe: admin123';
        RAISE NOTICE '⚠️  IMPORTANT: Changez ce mot de passe après la première connexion !';
        
    ELSE
        RAISE NOTICE '❌ Administrateur non trouvé: %', admin_email;
        RAISE NOTICE '💡 Création d''un nouvel administrateur...';
        
        -- Créer un nouvel administrateur
        INSERT INTO "user" (
            email, 
            nom_complet, 
            mot_de_passe_hash, 
            role, 
            type_utilisateur, 
            actif,
            cree_le
        ) VALUES (
            admin_email,
            'Administrateur LIA',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/8Qz8Qz2', -- admin123
            'administrateur',
            'interne',
            TRUE,
            NOW()
        );
        
        RAISE NOTICE '✅ Nouvel administrateur créé: %', admin_email;
        RAISE NOTICE '🔑 Mot de passe: admin123';
        RAISE NOTICE '⚠️  IMPORTANT: Changez ce mot de passe après la première connexion !';
    END IF;
END $$;

-- Vérification finale
DO $$
DECLARE
    admin_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO admin_count FROM "user" WHERE role = 'administrateur';
    RAISE NOTICE '📊 Nombre d''administrateurs dans la base: %', admin_count;
    
    IF admin_count > 0 THEN
        RAISE NOTICE '✅ Au moins un administrateur est disponible';
    ELSE
        RAISE NOTICE '❌ Aucun administrateur trouvé';
    END IF;
END $$;
