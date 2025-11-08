# Processus de Démarrage de l'Application LIA Coaching

Ce document décrit en détail toutes les étapes qui se déroulent lors du démarrage de l'application FastAPI.

## 📋 Table des Matières

1. [Initialisation des Chemins et Configuration](#initialisation-des-chemins-et-configuration)
2. [Création de l'Application FastAPI](#création-de-lapplication-fastapi)
3. [Configuration des Middlewares](#configuration-des-middlewares)
4. [Configuration CORS](#configuration-cors)
5. [Configuration des Fichiers Statiques](#configuration-des-fichiers-statiques)
6. [Montage des Dossiers Statiques](#montage-des-dossiers-statiques)
7. [Configuration des Routers](#configuration-des-routers)
8. [Événement de Démarrage (`on_startup`)](#événement-de-démarrage-on_startup)
9. [Gestionnaires d'Erreurs](#gestionnaires-derreurs)

---

## 🔧 Initialisation des Chemins et Configuration

### 1. Création des Dossiers Nécessaires

```python
settings.ensure_directories()
```

**Actions :**
- Crée tous les dossiers requis si ils n'existent pas :
  - `static/` (CSS, JS, images)
  - `templates/`
  - `uploads/`
  - `fichiers/`
  - `static/maps/`
  - `static/images/`

### 2. Configuration des Chemins

Les chemins sont récupérés depuis `settings` et `path_config` :
- `STATIC_DIR` : Dossier des fichiers statiques
- `TEMPLATES_DIR` : Dossier des templates Jinja2
- `STATIC_MAPS_DIR` : Dossier des cartes statiques
- `STATIC_IMAGES_DIR` : Dossier des images statiques
- `FICHIERS_DIR` : Dossier des fichiers uploadés
- `MEDIA_ROOT` : Dossier racine des médias

---

## 🚀 Création de l'Application FastAPI

```python
app = FastAPI(
    title=settings.APP_NAME,
    description="Application de gestion de coaching LIA",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    root_path=getattr(settings, "ROOT_PATH", ""),
)
```

**Configuration :**
- **Mode DEBUG** : Documentation Swagger/ReDoc activée
- **Mode PRODUCTION** : Documentation désactivée pour la sécurité
- Les `settings` sont stockés dans `app.state.settings` pour un accès global

---

## 🛡️ Configuration des Middlewares

### Ordre d'Exécution (Important !)

Les middlewares sont exécutés dans l'ordre inverse de leur ajout :

1. **`SharedSessionMiddleware`** (ajouté en dernier dans `setup_all_middlewares` = exécuté en premier)
   - Crée une session partagée pour chaque requête
   - Disponible pour tous les autres middlewares via `request.state.shared_session`

2. **`ProgramCreationMiddleware`** (ajouté en deuxième dans `setup_all_middlewares` = exécuté en deuxième)
   - **Moment** : APRÈS le traitement de la requête
   - **Rôle** : Surveille la création de nouveaux programmes
   - **Actions** :
     - Détecte les requêtes POST qui créent un programme
     - Vérifie tous les programmes actifs et crée les schémas manquants

3. **`ProgramSchemaMiddleware`** (ajouté en premier dans `setup_all_middlewares` = exécuté en dernier)
   - **Moment** : AVANT le traitement de la requête
   - **Rôle** : Détecte le programme depuis l'URL/params/headers
   - **Actions** :
     - Extrait le code du programme (`ACD`, `ACT`, etc.)
     - Crée le schéma s'il n'existe pas
     - Configure le routage SQL vers le bon schéma
     - Stocke le programme dans `request.state.current_programme`

**Ordre d'ajout dans le code :**
```python
app.add_middleware(ProgramSchemaMiddleware)      # 1er ajouté
app.add_middleware(ProgramCreationMiddleware)   # 2ème ajouté
app.add_middleware(SharedSessionMiddleware)     # 3ème ajouté (dernier)
```

**Ordre d'exécution lors d'une requête :**
```
Requête HTTP
    ↓
[1] SharedSessionMiddleware.dispatch() commence
    ├─ Crée la session partagée dans request.state.shared_session
    └─ Appelle call_next() →
        ↓
[2] ProgramCreationMiddleware.dispatch() commence
    └─ Appelle call_next() →
        ↓
[3] ProgramSchemaMiddleware.dispatch() commence
    ├─ Détecte le programme depuis l'URL/params/headers
    ├─ Crée le schéma s'il n'existe pas
    ├─ Configure le routage SQL (set_schema)
    ├─ Stocke le programme dans request.state
    └─ Appelle call_next() →
        ↓
[4] Traitement de la requête par la route FastAPI
    └─ Utilise request.state.shared_session pour les requêtes DB
        ↓
    Retour vers ProgramSchemaMiddleware (fin dispatch)
        ↓
    Retour vers ProgramCreationMiddleware (fin dispatch)
    ├─ Reçoit la réponse HTTP
    ├─ Vérifie si c'est une création de programme (POST, status 200/201)
    └─ Si oui, crée les schémas manquants pour tous les programmes
        ↓
    Retour vers SharedSessionMiddleware (fin dispatch)
    ├─ Commit de la session partagée
    └─ Fermeture de la session
        ↓
Réponse HTTP
```

### Fonction `setup_all_middlewares()`

```python
setup_all_middlewares(
    app,
    allowed_hosts=getattr(settings, "ALLOWED_HOSTS", ["localhost", "127.0.0.0.1"]),
    secret_key=settings.SECRET_KEY,
)
```

**Configuration :**
- Ajoute `ProgramSchemaMiddleware` en premier (dans `setup_all_middlewares`)
- Ajoute `ProgramCreationMiddleware` en second (dans `setup_all_middlewares`)
- Ajoute `SharedSessionMiddleware` en troisième (dans `setup_all_middlewares`)
- Configure les hôtes autorisés et la clé secrète

**Note importante :** `SharedSessionMiddleware` est maintenant ajouté dans `setup_all_middlewares()` et non séparément dans `main.py`. Cela garantit que tous les middlewares sont configurés au même endroit.

---

## 🌐 Configuration CORS

**Statut** : Actuellement commenté (non activé)

```python
# Middleware CORS commenté - peut être activé si nécessaire
```

Si activé, il permettrait :
- Les requêtes cross-origin depuis des domaines spécifiques
- L'authentification avec credentials
- Toutes les méthodes HTTP (`GET`, `POST`, `PUT`, `DELETE`, etc.)

---

## 📁 Configuration des Fichiers Statiques

### Mode Développement (`settings.DEBUG = True`)

**Actions automatiques :**
1. Création des sous-dossiers `css/` et `js/` s'ils n'existent pas
2. Génération automatique du fichier `theme.css` si absent :
   - Variables CSS depuis `settings.THEME_PRIMARY`, `THEME_SECONDARY`, etc.
   - Styles de base pour l'application

### Mode Production

Les fichiers statiques doivent être créés manuellement ou via un processus de build.

---

## 📂 Montage des Dossiers Statiques

**Configuration automatique depuis `path_config.MOUNT_CONFIGS` :**

```python
for mount_name, config in path_config.MOUNT_CONFIGS.items():
    path_config.ensure_directory_exists(mount_name)
    app.mount(
        config["path"], 
        StaticFiles(directory=config["directory"], check_dir=True), 
        name=config["name"]
    )
```

**Dossiers montés :**
- `/static` → `static/` (CSS, JS, images)
- `/maps` → `static/maps/` (cartes statiques)
- `/static/images` → `static/images/` (images)
- `/files` → `fichiers/` (fichiers uploadés)
- `/uploads` → `uploads/` (médias)

---

## 🛣️ Configuration des Routers

**Inclusion automatique depuis `router_configs` :**

```python
for router, prefix, tags in router_configs:
    app.include_router(router, prefix=prefix, tags=tags)
```

**Routers inclus :**
- Routes d'authentification (`/auth/*`)
- Routes d'administration (`/admin/*`)
- Routes de programmes (`/programmes/*`)
- Routes de préinscriptions (`/preinscriptions/*`)
- Routes publiques (`/public/*`)
- Et autres...

---

## 🎬 Événement de Démarrage (`on_startup`)

Cette fonction est appelée automatiquement par FastAPI au démarrage du serveur.

### ÉTAPE 1 : Bootstrap SQL

```python
maybe_bootstrap_database()
```

**Fonction `maybe_bootstrap_database()` :**

**Objectif** : Exécuter le script SQL d'initialisation (`core/init_postgres.sql`) via `psql` **une seule fois**.

**Mécanisme d'Idempotence :**
- Utilise un fichier sentinelle `.db_bootstrapped` pour éviter les réexécutions
- Peut être forcé avec `settings.DB_INIT_ALWAYS=True`

**Actions :**
1. Vérifie si `init_postgres.sql` existe
2. Vérifie si le bootstrap a déjà été effectué (fichier sentinelle)
3. Vérifie que `psql` est disponible dans le PATH
4. Exécute `psql` avec les variables :
   - `dbname` : Nom de la base applicative
   - `appuser` : Utilisateur applicatif
   - `apppass` : Mot de passe applicatif
5. Crée le fichier sentinelle après succès

**Contenu typique du script SQL :**
- Création de la base de données si elle n'existe pas
- Création de l'utilisateur applicatif
- Attribution des permissions
- Configuration des extensions PostgreSQL (`pgcrypto`, `uuid-ossp`, etc.)

---

### ÉTAPE 2 : Test de Connexion DB

```python
test_db_connection()
```

**Actions :**
- Teste la connexion à PostgreSQL
- Vérifie que le serveur répond
- Affiche l'URL de connexion pour le debug

**En cas d'échec :**
- L'erreur est loggée mais le démarrage continue (ne bloque pas)

---

### ÉTAPE 3 : Création des Tables ORM et Migration

```python
create_db_and_tables()
```

**Fonction `create_db_and_tables()` :**

**Objectif** : Créer toutes les tables du schéma `public` (tables système) et migrer les colonnes manquantes.

**Tables publiques créées :**
- `user` : Utilisateurs de l'application
- `programme` : Programmes de coaching
- `partenaire` : Partenaires
- `groupe` : Groupes d'utilisateurs
- `password_recovery_code` : Codes de récupération de mot de passe
- `programme_utilisateur` : Relation programme-utilisateur
- `promotion` : Promotions
- `activity_log` : Journal des activités
- `conversation` : Conversations
- `message` : Messages

**Migration automatique des colonnes :**
1. Pour chaque table publique :
   - Compare les colonnes existantes dans la DB avec les colonnes du modèle SQLModel
   - Identifie les colonnes manquantes
   - Ajoute les colonnes manquantes avec `ALTER TABLE ADD COLUMN`
   - Gère les types de données (conversion ENUM → VARCHAR si nécessaire)
   - Gère les contraintes NULL/NOT NULL
   - Gère les valeurs par défaut

**Exemple :**
```sql
-- Si la colonne 'statut' manque dans la table 'programme'
ALTER TABLE programme ADD COLUMN statut VARCHAR(50) DEFAULT 'brouillon';
```

---

### ÉTAPE 4 : Création des Schémas par Programme

```python
create_program_schemas_and_tables()
```

**Fonction `create_program_schemas_and_tables()` :**

**Objectif** : Créer les schémas PostgreSQL pour chaque programme actif et toutes leurs tables.

**Processus détaillé :**

#### 4.1. Récupération des Programmes Actifs

```python
programmes_query = text("""
    SELECT code 
    FROM programme 
    WHERE actif = true
""")
programme_codes = [row[0] for row in result]  # Ex: ['ACD', 'ACT']
```

#### 4.2. Pour Chaque Programme

**a) Création du Schéma**

```python
schema_name = programme_code.lower()  # Ex: 'acd', 'act'
session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
session.commit()
```

**b) Création des Tables dans le Schéma**

Utilise `ProgramSchemaManager._create_tables_in_schema()` pour créer toutes les tables :

**Tables créées dans chaque schéma :**
- `candidat` : Candidats du programme
- `preinscription` : Préinscriptions
- `inscription` : Inscriptions
- `entreprise` : Entreprises
- `document` : Documents
- `eligibilite` : Calculs d'éligibilité
- `jury` : Jurys
- `membre_jury` : Membres des jurys
- `decision_jury_table` : Décisions des jurys
- `etape_pipeline` : Étapes du pipeline
- `avancement_etape` : Avancements dans les étapes
- `action_handicap` : Actions handicap
- `rendez_vous` : Rendez-vous
- `session_programme` : Sessions de programme
- `session_participant` : Participants aux sessions
- `suivi_mensuel` : Suivis mensuels
- `decision_jury_candidat` : Décisions jury pour candidats
- `reorientation_candidat` : Réorientations de candidats
- `emargement_rdv` : Émargements des rendez-vous
- `seminaire` : Séminaires
- `session_seminaire` : Sessions de séminaire
- `invitation_seminaire` : Invitations aux séminaires
- `presence_seminaire` : Présences aux séminaires
- `livrable_seminaire` : Livrables des séminaires
- `rendu_livrable` : Rendu des livrables
- `event` : Événements
- `invitation_event` : Invitations aux événements
- `presence_event` : Présences aux événements
- `ressource_elearning` : Ressources e-learning
- `module_elearning` : Modules e-learning
- `progression_elearning` : Progressions e-learning
- `objectif_elearning` : Objectifs e-learning
- `quiz_elearning` : Quiz e-learning
- `reponse_quiz` : Réponses aux quiz
- `certificat_elearning` : Certificats e-learning
- `module_ressource` : Relations module-ressource
- `seance_codev` : Séances de codéveloppement
- `presentation_codev` : Présentations codéveloppement
- `contribution_codev` : Contributions codéveloppement
- `participation_seance` : Participations aux séances
- `cycle_codev` : Cycles de codéveloppement
- `groupe_codev` : Groupes de codéveloppement
- `membre_groupe_codev` : Membres des groupes

**Chaque table est créée avec sa propre transaction** pour éviter les rollbacks en cascade.

**c) Migration Automatique des Colonnes**

Pour chaque table dans chaque schéma :
1. Compare les colonnes existantes avec le modèle SQLModel
2. Ajoute les colonnes manquantes avec `ALTER TABLE`
3. Gère les types de données (conversion ENUM → VARCHAR)
4. Configure les contraintes et valeurs par défaut

**Exemple pour le schéma `acd` :**
```sql
-- Si la colonne 'handicap' manque dans acd.candidat
ALTER TABLE acd.candidat ADD COLUMN handicap BOOLEAN DEFAULT FALSE;
```

---

### ÉTAPE 5 : Vérification Administrateur

```python
ensure_admin_user()
```

**Fonction `ensure_admin_user()` :**

**Objectif** : S'assurer qu'il existe au moins un utilisateur administrateur dans la base de données.

**Actions :**
1. Utilise `UserService.ensure_admin_exists(session)`
2. Vérifie si un admin existe avec l'email configuré dans `settings.ADMIN_EMAIL`
3. Si aucun admin n'existe :
   - Crée un utilisateur admin avec l'email et mot de passe par défaut
   - Le mot de passe peut être défini dans `settings.ADMIN_PASSWORD` ou généré automatiquement
4. Si l'admin existe mais le mot de passe est incorrect :
   - Log un avertissement
   - L'admin devra réinitialiser son mot de passe

**Configuration :**
- Email admin : `settings.ADMIN_EMAIL` (ex: `admin@lia-coaching.fr`)
- Mot de passe admin : `settings.ADMIN_PASSWORD` (si défini)

---

## ⚠️ Gestionnaires d'Erreurs

### Erreurs HTTP (404, 500, etc.)

**Gestionnaire `http_exception_handler` :**

- **404 (Not Found)** : Affiche une page d'erreur personnalisée avec le template `404.html`
- **500 (Internal Server Error)** : 
  - Génère un ID d'incident unique pour le support
  - Affiche une page d'erreur avec le template `500.html`
  - Inclut le chemin de la requête et l'heure

### Exceptions Non Gérées

**Gestionnaire `unhandled_exception_handler` :**

- Capture toutes les exceptions non interceptées
- Génère un ID d'incident unique
- Affiche une page d'erreur 500 avec les détails

---

## 📊 Schéma du Flux de Démarrage

```
Démarrage de l'application
    ↓
[1] Initialisation des chemins et création des dossiers
    ↓
[2] Création de l'instance FastAPI
    ↓
[3] Configuration des middlewares
    ├─ SharedSessionMiddleware
    ├─ ProgramSchemaMiddleware
    └─ ProgramCreationMiddleware
    ↓
[4] Configuration CORS (commenté)
    ↓
[5] Configuration des fichiers statiques (mode dev)
    ↓
[6] Montage des dossiers statiques
    ↓
[7] Inclusion des routers
    ↓
[8] Événement on_startup()
    ├─ [ÉTAPE 1] Bootstrap SQL (init_postgres.sql)
    ├─ [ÉTAPE 2] Test de connexion DB
    ├─ [ÉTAPE 3] Création tables publiques + migration
    ├─ [ÉTAPE 4] Création schémas par programme + tables + migration
    └─ [ÉTAPE 5] Vérification administrateur
    ↓
[9] Enregistrement des gestionnaires d'erreurs
    ↓
Application prête à recevoir des requêtes !
```

---

## 🔍 Points Importants à Retenir

### 1. Ordre d'Exécution des Middlewares

**Critique** : L'ordre d'ajout des middlewares est inversé lors de l'exécution.

- `SharedSessionMiddleware` est ajouté en dernier → exécuté en premier
- Permet à tous les autres middlewares d'accéder à la session partagée

### 2. Migration Automatique

**Avantage** : Les colonnes manquantes sont ajoutées automatiquement sans script de migration manuel.

**Limitation** : Ne gère pas :
- La suppression de colonnes
- Le renommage de colonnes
- La modification de types de colonnes (nécessite une migration manuelle)

### 3. Schémas par Programme

**Architecture** : Chaque programme a son propre schéma PostgreSQL avec ses propres tables.

**Exemple** :
- Schéma `acd` : Tables `acd.candidat`, `acd.preinscription`, etc.
- Schéma `act` : Tables `act.candidat`, `act.preinscription`, etc.
- Schéma `public` : Tables système (`user`, `programme`, etc.)

### 4. Idempotence

**Toutes les fonctions de création sont idempotentes** :
- `CREATE SCHEMA IF NOT EXISTS` : Ne crée pas si existe déjà
- `CREATE TABLE IF NOT EXISTS` : Ne crée pas si existe déjà
- Migration : Vérifie l'existence avant d'ajouter une colonne

**Conséquence** : On peut redémarrer l'application sans risque de duplication.

---

## 🐛 Dépannage

### Problème : Tables non créées

**Solution** : Vérifier les logs au démarrage pour identifier les erreurs SQL.

### Problème : Schémas non créés

**Solution** : 
1. Vérifier que la table `programme` contient des programmes avec `actif = true`
2. Vérifier les logs pour les erreurs de création de schéma

### Problème : Colonnes manquantes

**Solution** : 
1. Vérifier que le modèle SQLModel contient bien la colonne
2. Vérifier les logs de migration pour les erreurs `ALTER TABLE`

### Problème : Admin non créé

**Solution** :
1. Vérifier `settings.ADMIN_EMAIL` et `settings.ADMIN_PASSWORD`
2. Vérifier les logs pour les erreurs de création d'utilisateur

---

## 📝 Notes Finales

- **Temps de démarrage** : Dépend du nombre de programmes et de tables (~5-30 secondes)
- **Base de données** : PostgreSQL 12+ requis
- **Extensions PostgreSQL** : `pgcrypto`, `uuid-ossp` recommandées
- **Permissions** : L'utilisateur DB doit avoir les droits de création de schémas et tables

---

*Document généré automatiquement - Dernière mise à jour : 2025-11-05*

