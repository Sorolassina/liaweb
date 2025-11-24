// ============================================
// HELPERS GLOBAUX
// ============================================

/**
 * Helper pour préfixer automatiquement les URLs API avec root_path
 * Usage: apiUrl('/api/v1/users') => '/gimbie/api/v1/users' (en prod)
 */
window.apiUrl = window.apiUrl || function(path) {
    // Si le chemin commence déjà par root_path, le retourner tel quel
    if (window.root_path && path.startsWith(window.root_path)) {
        return path;
    }
    // Sinon, ajouter le préfixe
    return window.root_path ? window.root_path + path : path;
};

/**
 * Wrapper de fetch qui préfixe automatiquement les URLs API
 * Remplace le fetch natif pour gérer automatiquement le root_path
 */
(function() {
    const originalFetch = window.fetch;
    
    window.fetch = function(url, options) {
        // Si l'URL est une chaîne et commence par /api/, /static/, ou /uploads/
        if (typeof url === 'string') {
            if (url.startsWith('/api/') || url.startsWith('/static/') || url.startsWith('/uploads/')) {
                url = window.apiUrl(url);
            }
        }
        
        // Appeler le fetch original avec l'URL préfixée
        return originalFetch(url, options);
    };
})();

// ============================================
// FONCTIONS UTILITAIRES
// ============================================

/**
 * Convertit FormData en objet JSON propre
 * - Convertit les chaînes vides en null pour les champs ID
 * - Convertit 'true'/'false' strings en booléens
 * - Nettoie les espaces inutiles
 * - Prépare les données pour l'envoi JSON
 * 
 * @param {FormData} formData - Le FormData à convertir
 * @returns {Object} - Objet nettoyé prêt pour JSON.stringify()
 */
window.formDataToCleanObject = function(formData) {
    const data = {};
    
    for (const [key, value] of formData.entries()) {
        // Convertir 'true'/'false' strings en booléens (pour les checkboxes)
        if (value === 'true') {
            data[key] = true;
        }
        else if (value === 'false') {
            data[key] = false;
        }
        // Convertir les chaînes vides en null pour les champs numériques (ID)
        else if (value === '' && (key.endsWith('_id') || key === 'id')) {
            data[key] = null;
        }
        // Convertir "null" string en null
        else if (value === 'null') {
            data[key] = null;
        }
        // Nettoyer les espaces pour les chaînes
        else if (typeof value === 'string') {
            data[key] = value.trim();
        }
        // Garder les autres valeurs telles quelles
        else {
            data[key] = value;
        }
    }
    
    return data;
};

/**
 * Vérifie si un FormData contient des fichiers
 * @param {FormData} formData - Le FormData à vérifier
 * @returns {boolean} - true si contient des fichiers
 */
window.formDataHasFiles = function(formData) {
    for (const [key, value] of formData.entries()) {
        if (value instanceof File && value.size > 0) {
            return true;
        }
    }
    return false;
};

/**
 * Nettoie un FormData en supprimant toutes les valeurs vides
 * Les champs vides ne seront pas envoyés (= null côté serveur pour champs optionnels)
 * 
 * @param {FormData} formData - Le FormData à nettoyer
 * @returns {FormData} - Nouveau FormData nettoyé
 */
window.cleanFormData = function(formData) {
    const cleaned = new FormData();
    
    // Liste des champs ID optionnels qui peuvent être vides (pas d'envoi si vide)
    const optionalIdFields = ['vehicule_parc_id', 'user_id', 'parent_id', 'category_id', 'produit_id', 'fournisseur_id', 'compte_id', 'contrat_id', 'tranche_id', 'reservation_navire_id', 'ticket_id', 'vehicule_id'];
    
    for (const [key, value] of formData.entries()) {
        // Si c'est un fichier, toujours l'ajouter
        if (value instanceof File) {
            // N'ajouter que si le fichier a du contenu
            if (value.size > 0) {
                cleaned.append(key, value);
            }
        }
        // Si c'est un champ ID optionnel et qu'il est vide, ne pas l'envoyer
        else if (optionalIdFields.some(field => key.includes(field)) && (value === '' || value === 'null' || value === 'undefined')) {
            // Ne pas ajouter ce champ
            continue;
        }
        // Si la valeur est vide, l'envoyer comme chaîne vide (le serveur convertira en null si besoin)
        else if (value === '' || value === 'null' || value === 'undefined') {
            cleaned.append(key, '');  // Envoyer explicitement la chaîne vide
        }
        // Si la valeur est remplie, l'ajouter après nettoyage des espaces
        else {
            cleaned.append(key, typeof value === 'string' ? value.trim() : value);
        }
    }
    
    return cleaned;
};

/**
 * Helper intelligent pour envoyer des données de formulaire
 * Détecte automatiquement si le formulaire contient des fichiers :
 * - Si oui : envoie en multipart/form-data (garde FormData)
 * - Si non : envoie en JSON (convertit et nettoie)
 * 
 * @param {string} url - L'URL de destination
 * @param {FormData} formData - Le FormData du formulaire
 * @param {string} method - La méthode HTTP (POST, PUT, etc.)
 * @param {boolean} forceFormData - Forcer l'utilisation de FormData même sans fichiers
 * @returns {Promise} - La promesse du fetch
 */
window.submitFormAsJson = async function(url, formData, method = 'POST', forceFormData = false) {
    // Si le formulaire contient des fichiers ou forceFormData=true, envoyer en multipart/form-data
    if (forceFormData || window.formDataHasFiles(formData)) {
        // Nettoyer le FormData (supprimer les valeurs vides des champs ID)
        const cleanedFormData = window.cleanFormData(formData);
        return fetch(url, {
            method: method,
            body: cleanedFormData  // Pas de Content-Type, le navigateur le gère automatiquement
        });
    }
    
    // Sinon, convertir en JSON et nettoyer
    const data = window.formDataToCleanObject(formData);
    
    return fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
};

/**
 * Fonction générique pour toutes les soumissions de formulaires
 * Centralise la logique de soumission avec gestion d'overlay, erreurs et messages
 */
window.submitFormGeneric = async function(event, url, successMessage, method = 'POST', redirectDelay = 1500) {
    console.log('🚀 submitFormGeneric appelée avec:', { url, successMessage, method });
    event.preventDefault();
    
    // Afficher l'overlay global si disponible
    if (typeof showGlobalLoading === 'function') {
        showGlobalLoading();
    }
    
    try {
        const formData = new FormData(event.target);
        
        // Gérer les checkboxes : ajouter les checkboxes non cochées avec la valeur false
        const checkboxes = event.target.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            if (!checkbox.checked && !formData.has(checkbox.name)) {
                formData.append(checkbox.name, 'false');
            } else if (checkbox.checked) {
                formData.set(checkbox.name, 'true');
            }
        });
        
        // Debug : Afficher le contenu du FormData avant envoi
        // Vérifier si nombre_conteneurs est présent, sinon l'ajouter
        let hasNombreConteneurs = false;
        for (const [key, value] of formData.entries()) {
            if (key === 'nombre_conteneurs') {
                hasNombreConteneurs = true;
                break;
            }
        }
        
        if (!hasNombreConteneurs) {
            // Compter les conteneurs via les champs conteneur_X_numero
            let countConteneurs = 0;
            for (const [key, value] of formData.entries()) {
                if (key.startsWith('conteneur_') && key.endsWith('_numero') && value) {
                    countConteneurs++;
                }
            }
            formData.append('nombre_conteneurs', countConteneurs);
            console.log('🔧 nombre_conteneurs manquant, ajouté avec valeur:', countConteneurs);
        }
        
        console.log('🚀 submitFormGeneric - FormData avant envoi:');
        for (const [key, value] of formData.entries()) {
            console.log(`  ${key}:`, value);
        }
        console.log('🌐 URL de destination:', url);
        console.log('🔧 Méthode HTTP:', method);
        
        const response = await window.submitFormAsJson(url, formData, method, true);
        
        if (!response.ok) {
            console.log('❌ Erreur HTTP détectée:', response.status);
            // Essayer de lire le message d'erreur du JSON
            const errorData = await response.json();
            console.log('📄 Données d\'erreur reçues:', errorData);
            const errorMessage = errorData.detail || `Erreur HTTP: ${response.status}`;
            console.log('💬 Message d\'erreur extrait:', errorMessage);
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Fermer les modals si la fonction existe
            if (typeof closeModals === 'function') {
                closeModals();
            }
            
            // Afficher un message de succès
            if (typeof showToast === 'function') {
                showToast(successMessage, 'success');
            }
            
            // Recharger la page
            setTimeout(() => window.location.reload(), redirectDelay);
        } else {
            throw new Error(data.message || 'Erreur lors de la soumission');
        }
    } catch (error) {
        console.error('🚨 Erreur capturée:', error);
        console.log('📝 Message d\'erreur:', error.message);
        
        // Afficher un message d'erreur
        if (typeof showToast === 'function') {
            console.log('🎯 Appel de showToast avec le message:', error.message);
            showToast(`Erreur: ${error.message}`, 'error');
        } else {
            console.log('⚠️ showToast n\'est pas disponible');
        }
    } finally {
        // Masquer l'overlay global si disponible
        if (typeof hideGlobalLoading === 'function') {
            hideGlobalLoading();
        }
    }
};

/**
 * Fonctions centralisées pour gérer les modals
 */
window.showModal = function(modalId) {
    document.getElementById(modalId).classList.add('show');
};

window.closeModal = function(modalId) {
    document.getElementById(modalId).classList.remove('show');
};

window.closeModals = function() {
    // Fermer tous les modals ouverts
    const modals = document.querySelectorAll('.modal.show, .modal-sm.show, .modal-md.show, .modal-lg.show, .modal-xl.show');
    modals.forEach(modal => {
        modal.classList.remove('show');
    });
};

/**
 * Afficher un message de succès/erreur
 */
window.showMessage = window.showMessage || function(message, type = 'success') {
    console.log(`[${type.toUpperCase()}]`, message);
    // Cette fonction peut être surchargée par les pages individuelles
};

/**
 * Afficher un overlay de chargement
 */
window.showLoading = window.showLoading || function(text = 'Chargement...', subtext = 'Veuillez patienter') {
    console.log(`[LOADING] ${text} - ${subtext}`);
    // Cette fonction peut être surchargée par les pages individuelles
};

/**
 * Masquer l'overlay de chargement
 */
window.hideLoading = window.hideLoading || function() {
    console.log('[LOADING] Hidden');
    // Cette fonction peut être surchargée par les pages individuelles
};

// ============================================
// TRANSITIONS DE PAGE ÉLÉGANTES
// ============================================

/**
 * Ajoute des transitions fluides lors de la navigation entre les pages
 * Intercepte les clics sur les liens pour ajouter une animation de sortie
 */
(function() {
    // Attendre que le DOM soit chargé
    document.addEventListener('DOMContentLoaded', function() {
        
        // Intercepter tous les clics sur les liens internes
        document.addEventListener('click', function(e) {
            // Trouver le lien cliqué (peut être un parent du cible)
            const link = e.target.closest('a');
            
            // Vérifier si c'est un lien valide
            if (!link) return;
            
            const href = link.getAttribute('href');
            
            // Ignorer les cas suivants :
            // - Liens externes (commencent par http:// ou https://)
            // - Liens ancres (#)
            // - Liens vides ou javascript:
            // - Liens avec target="_blank"
            // - Liens avec download
            // - Clics avec Ctrl/Cmd (nouvel onglet)
            if (!href || 
                href.startsWith('http://') || 
                href.startsWith('https://') ||
                href.startsWith('#') ||
                href.startsWith('javascript:') ||
                href === '' ||
                link.target === '_blank' ||
                link.hasAttribute('download') ||
                e.ctrlKey || 
                e.metaKey) {
                return;
            }
            
            // Empêcher la navigation par défaut
            e.preventDefault();
            
            // Ajouter la classe d'animation de sortie
            document.body.classList.add('page-exit');
            
            // Naviguer après l'animation (300ms)
            setTimeout(function() {
                window.location.href = href;
            }, 300);
        });
        
        // Animation d'entrée au chargement de la page
        document.body.style.opacity = '0';
        document.body.style.transform = 'translateY(10px)';
        
        // Déclencher l'animation après un court délai
        setTimeout(function() {
            document.body.style.transition = 'opacity 0.4s ease-in-out, transform 0.4s ease-in-out';
            document.body.style.opacity = '1';
            document.body.style.transform = 'translateY(0)';
        }, 10);
    });
})();

// Script pour préserver le paramètre programme dans tous les liens et formulaires -->

    (function() {
        // Récupérer le paramètre programme de l'URL actuelle
        const urlParams = new URLSearchParams(window.location.search);
        const programmeParam = urlParams.get('programme');
        
        // Stocker dans une variable globale pour utilisation par d'autres scripts
        window.currentProgramme = programmeParam;
        
        if (programmeParam) {
            // Fonction pour ajouter le paramètre programme à une URL
            function addProgrammeToUrl(url) {
                if (!url) return url;
                
                try {
                    const urlObj = new URL(url, window.location.origin);
                    // Ne pas ajouter si déjà présent
                    if (!urlObj.searchParams.has('programme')) {
                        urlObj.searchParams.set('programme', programmeParam);
                    }
                    return urlObj.pathname + urlObj.search + urlObj.hash;
                } catch (e) {
                    // Si l'URL est relative, l'ajouter manuellement
                    if (url.startsWith('/') || url.startsWith('#')) {
                        const separator = url.includes('?') ? '&' : '?';
                        if (!url.includes('programme=')) {
                            return url + separator + 'programme=' + encodeURIComponent(programmeParam);
                        }
                    }
                    return url;
                }
            }
            
            // Ajouter le paramètre programme à tous les liens
            function processLinks() {
                const links = document.querySelectorAll('a[href]');
                links.forEach(function(link) {
                    const href = link.getAttribute('href');
                    // Ignorer les liens externes, les ancres, et les liens qui ont déjà le paramètre
                    if (href && !href.startsWith('http') && !href.startsWith('#') && !href.startsWith('javascript:') && !href.includes('programme=')) {
                        const newHref = addProgrammeToUrl(href);
                        if (newHref !== href) {
                            link.setAttribute('href', newHref);
                        }
                    }
                });
            }
            
            // Ajouter le paramètre programme à tous les formulaires
            function processForms() {
                const forms = document.querySelectorAll('form');
                forms.forEach(function(form) {
                    // Vérifier si le formulaire a déjà un champ programme
                    let hasProgrammeField = false;
                    const existingFields = form.querySelectorAll('input[name="programme"], input[type="hidden"][name="programme"]');
                    if (existingFields.length > 0) {
                        // Mettre à jour la valeur si le champ existe déjà
                        existingFields.forEach(function(field) {
                            field.value = programmeParam;
                            hasProgrammeField = true;
                        });
                    }
                    
                    // Ajouter un champ caché si nécessaire
                    if (!hasProgrammeField) {
                        const hiddenInput = document.createElement('input');
                        hiddenInput.type = 'hidden';
                        hiddenInput.name = 'programme';
                        hiddenInput.value = programmeParam;
                        form.appendChild(hiddenInput);
                    }
                    
                    // Ajouter le paramètre à l'action du formulaire si c'est une URL
                    const action = form.getAttribute('action');
                    if (action && !action.includes('programme=')) {
                        const newAction = addProgrammeToUrl(action);
                        if (newAction !== action) {
                            form.setAttribute('action', newAction);
                        }
                    }
                });
            }
            
            // Exécuter au chargement de la page
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    processLinks();
                    processForms();
                });
            } else {
                processLinks();
                processForms();
            }
            
            // Observer les changements du DOM pour les éléments ajoutés dynamiquement
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.addedNodes.length > 0) {
                        processLinks();
                        processForms();
                    }
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    })();


