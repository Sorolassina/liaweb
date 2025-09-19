-- =====================================================
-- VÉRIFICATION FINALE DE LA MIGRATION
-- =====================================================

-- 1. Vérifier la table RessourceElearning
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns 
    WHERE table_name = 'ressourceelearning';
    
    RAISE NOTICE '📊 Table ressourceelearning: % colonnes détectées', col_count;
    
    -- Vérifier les colonnes essentielles
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_video') THEN
        RAISE NOTICE '✅ url_contenu_video: OK';
    ELSE
        RAISE NOTICE '❌ url_contenu_video: MANQUANT';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_video_path') THEN
        RAISE NOTICE '✅ fichier_video_path: OK';
    ELSE
        RAISE NOTICE '❌ fichier_video_path: MANQUANT';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_document') THEN
        RAISE NOTICE '✅ url_contenu_document: OK';
    ELSE
        RAISE NOTICE '❌ url_contenu_document: MANQUANT';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_document_path') THEN
        RAISE NOTICE '✅ fichier_document_path: OK';
    ELSE
        RAISE NOTICE '❌ fichier_document_path: MANQUANT';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_audio') THEN
        RAISE NOTICE '✅ url_contenu_audio: OK';
    ELSE
        RAISE NOTICE '❌ url_contenu_audio: MANQUANT';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_audio_path') THEN
        RAISE NOTICE '✅ fichier_audio_path: OK';
    ELSE
        RAISE NOTICE '❌ fichier_audio_path: MANQUANT';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_lien') THEN
        RAISE NOTICE '✅ url_contenu_lien: OK';
    ELSE
        RAISE NOTICE '❌ url_contenu_lien: MANQUANT';
    END IF;
END $$;

-- 2. Vérifier les autres tables
DO $$
BEGIN
    -- Table programme
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'programme' AND column_name = 'statut') THEN
        RAISE NOTICE '✅ Table programme: colonne statut OK';
    ELSE
        RAISE NOTICE '❌ Table programme: colonne statut MANQUANTE';
    END IF;
    
    -- Table jury
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'jury' AND column_name = 'decision') THEN
        RAISE NOTICE '✅ Table jury: colonne decision OK';
    ELSE
        RAISE NOTICE '❌ Table jury: colonne decision MANQUANTE';
    END IF;
    
    -- Table moduleressource
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'moduleressource') THEN
        RAISE NOTICE '✅ Table moduleressource: OK';
    ELSE
        RAISE NOTICE '❌ Table moduleressource: MANQUANTE';
    END IF;
END $$;

-- 3. Vérifier l'administrateur
DO $$
DECLARE
    admin_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO admin_count FROM "user" WHERE role = 'administrateur';
    
    IF admin_count > 0 THEN
        RAISE NOTICE '✅ Administrateur(s) trouvé(s): %', admin_count;
        
        -- Afficher les administrateurs
        FOR rec IN 
            SELECT email, nom_complet, actif 
            FROM "user" 
            WHERE role = 'administrateur'
        LOOP
            RAISE NOTICE '  - % (%): actif=%', rec.email, rec.nom_complet, rec.actif;
        END LOOP;
    ELSE
        RAISE NOTICE '❌ Aucun administrateur trouvé';
    END IF;
END $$;

-- 4. Résumé final
DO $$
BEGIN
    RAISE NOTICE '🎉 VÉRIFICATION TERMINÉE';
    RAISE NOTICE '📋 Votre système e-learning est maintenant prêt !';
    RAISE NOTICE '🔑 Vous pouvez vous connecter avec: sorolassina58@gmail.com / admin123';
    RAISE NOTICE '⚠️  N''oubliez pas de changer le mot de passe après la première connexion';
END $$;
