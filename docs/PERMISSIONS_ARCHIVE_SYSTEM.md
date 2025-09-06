# Système de Permissions et d'Archivage

## 🔐 Système de Permissions

### Vue d'ensemble
Le système de permissions permet de contrôler finement l'accès aux différentes ressources de l'application selon les rôles des utilisateurs.

### Composants

#### 1. Modèles (`models/ACD/permissions.py`)
- **`RolePermission`** : Permissions par défaut pour chaque rôle
- **`UserPermission`** : Permissions spécifiques à un utilisateur (surcharge)
- **`PermissionLog`** : Historique des modifications de permissions

#### 2. Service (`services/ACD/permissions.py`)
- **`PermissionService`** : Logique métier pour la gestion des permissions
- Méthodes principales :
  - `get_user_permissions()` : Récupère toutes les permissions d'un utilisateur
  - `has_permission()` : Vérifie si un utilisateur a une permission spécifique
  - `grant_permission()` : Accorde une permission temporaire
  - `revoke_permission()` : Révoque une permission

#### 3. Décorateur (`core/permissions.py`)
- **`@require_permission()`** : Décorateur pour protéger les routes
- Usage : `@require_permission(ResourceType.USERS, PermissionLevel.WRITE)`

### Niveaux de Permission
1. **`READ`** : Lecture seule
2. **`WRITE`** : Lecture + écriture
3. **`DELETE`** : Lecture + écriture + suppression
4. **`ADMIN`** : Tous les droits

### Ressources
- `USERS` : Gestion des utilisateurs
- `PROGRAMMES` : Gestion des programmes
- `CANDIDATS` : Gestion des candidats
- `INSCRIPTIONS` : Gestion des inscriptions
- `JURYS` : Gestion des jurys
- `DOCUMENTS` : Gestion des documents
- `LOGS` : Consultation des logs
- `SETTINGS` : Paramètres système
- `BACKUP` : Sauvegardes
- `ARCHIVE` : Archives

## 📦 Système d'Archivage

### Vue d'ensemble
Le système d'archivage permet de créer des sauvegardes complètes de l'application et de nettoyer automatiquement les données obsolètes.

### Composants

#### 1. Modèles (`models/ACD/archive.py`)
- **`Archive`** : Enregistrement des archives créées
- **`CleanupRule`** : Règles de nettoyage automatique
- **`CleanupLog`** : Historique des opérations de nettoyage

#### 2. Service (`services/ACD/archive.py`)
- **`ArchiveService`** : Logique métier pour l'archivage
- Méthodes principales :
  - `create_full_backup()` : Crée une sauvegarde complète
  - `restore_from_backup()` : Restaure à partir d'une archive
  - `cleanup_old_data()` : Nettoie les données obsolètes
  - `delete_archive()` : Supprime une archive

### Types d'Archives
1. **`FULL_BACKUP`** : Sauvegarde complète (BDD + fichiers + config)
2. **`DATA_ONLY`** : Données uniquement
3. **`FILES_ONLY`** : Fichiers uniquement
4. **`SELECTIVE`** : Archivage sélectif

### Statuts d'Archives
- `PENDING` : En attente
- `IN_PROGRESS` : En cours
- `COMPLETED` : Terminé
- `FAILED` : Échec
- `EXPIRED` : Expiré

## 🚀 Installation et Configuration

### 1. Créer les tables
```bash
# Exécuter le script SQL
psql -d votre_base -f scripts/create_permissions_archive_tables.sql
```

### 2. Initialiser les permissions
```bash
python scripts/test_permissions.py
```

### 3. Initialiser les règles de nettoyage
```bash
python scripts/init_cleanup_rules.py
```

### 4. Créer une première sauvegarde
```bash
python scripts/create_backup.py
```

## 📋 Utilisation

### Interface Web
1. **Permissions** : `/admin/permissions`
   - Visualiser la matrice des permissions
   - Accorder/révoquer des permissions spécifiques
   - Historique des modifications

2. **Archives** : `/admin/archives`
   - Créer des sauvegardes
   - Télécharger/restaurer des archives
   - Exécuter le nettoyage

### Scripts en ligne de commande
```bash
# Créer une sauvegarde
python scripts/create_backup.py

# Exécuter le nettoyage
python scripts/run_cleanup.py

# Tester les permissions
python scripts/test_permissions.py
```

## 🔧 Configuration

### Variables d'environnement
```bash
# Configuration de la base de données
DATABASE_URL=postgresql://user:password@localhost/dbname

# Configuration des sauvegardes
ARCHIVE_RETENTION_DAYS=30
BACKUP_SCHEDULE=daily
```

### Règles de nettoyage par défaut
1. **Logs d'activité** : Suppression après 90 jours
2. **Sessions expirées** : Suppression après 7 jours
3. **Documents temporaires** : Suppression après 365 jours
4. **Préinscriptions abandonnées** : Suppression après 180 jours
5. **Archives expirées** : Suppression après 30 jours

## 🛡️ Sécurité

### Bonnes pratiques
1. **Permissions minimales** : Accorder seulement les permissions nécessaires
2. **Audit régulier** : Vérifier régulièrement les permissions accordées
3. **Sauvegardes fréquentes** : Créer des sauvegardes régulières
4. **Nettoyage automatique** : Configurer le nettoyage automatique
5. **Rotation des archives** : Supprimer les archives expirées

### Monitoring
- Consulter les logs d'activité : `/admin/logs`
- Vérifier les permissions : `/admin/permissions`
- Surveiller les archives : `/admin/archives`

## 🚨 Dépannage

### Problèmes courants
1. **Permission refusée** : Vérifier les permissions de l'utilisateur
2. **Sauvegarde échouée** : Vérifier l'espace disque et les permissions
3. **Nettoyage bloqué** : Vérifier les règles de nettoyage
4. **Restauration échouée** : Vérifier l'intégrité de l'archive

### Logs utiles
```bash
# Logs de l'application
tail -f logs/app.log

# Logs PostgreSQL
tail -f /var/log/postgresql/postgresql.log
```
