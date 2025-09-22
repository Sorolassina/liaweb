# Système de Schémas par Programme - Guide d'utilisation

## Vue d'ensemble

Ce système permet d'isoler les données de chaque programme (ACD, ACI, ACT) dans des schémas séparés, évitant ainsi les confusions entre candidats de différents programmes.

## Structure des schémas

```
lia_coaching (base de données)
├── public (schéma par défaut)
│   ├── users (admin, conseillers, etc.)
│   ├── programmes
│   ├── jurys
│   └── ...
├── acd (schéma pour programme ACD)
│   ├── candidats
│   ├── preinscriptions
│   ├── inscriptions
│   └── ...
├── aci (schéma pour programme ACI)
│   ├── candidats
│   ├── preinscriptions
│   └── ...
└── act (schéma pour programme ACT)
    ├── candidats
    ├── preinscriptions
    └── ...
```

## Installation et configuration

### 1. Exécuter le script de création des schémas

```bash
# Option 1: Script automatique
python setup_program_schemas.py

# Option 2: Script manuel
psql -U liauser -d lia_coaching -f scripts/create_program_schemas_with_existing_models.sql
```

### 2. Démarrer l'application

```bash
python -m app_lia_web.app.main
```

### 3. Accéder à l'interface d'administration

Ouvrez votre navigateur et allez à : `http://localhost:8000/admin/schemas`

## Utilisation de l'interface d'administration

### Création des schémas

1. **Créer un schéma individuel** : Cliquez sur le bouton "Créer" pour un programme spécifique
2. **Créer tous les schémas** : Cliquez sur "Créer tous les schémas" pour créer tous les schémas manquants

### Migration des données

1. **Migrer les données existantes** : Cliquez sur l'icône de migration pour un programme
2. **Vérifier les statistiques** : Cliquez sur l'icône de statistiques pour voir le nombre d'enregistrements

### Sauvegarde et suppression

1. **Sauvegarder** : Cliquez sur l'icône de téléchargement pour sauvegarder en Excel
2. **Supprimer** : Cliquez sur l'icône de suppression (avec option de sauvegarde)

## Fonctionnalités

### Isolation des données

- Chaque programme a ses propres tables
- Pas de confusion entre candidats de différents programmes
- Sécurité renforcée

### Migration progressive

- Compatible avec le système existant
- Migration des données existantes possible
- Rollback possible

### Interface d'administration

- Création/suppression de schémas
- Migration des données existantes
- Sauvegarde en Excel
- Statistiques détaillées

## Tests

### Test d'intégration

```bash
python test_schema_integration.py
```

Ce script vérifie :
- Les programmes existants
- La création des schémas
- L'intégration du middleware
- Les statistiques des schémas

### Test manuel

1. Créer un schéma pour un programme
2. Migrer les données existantes
3. Vérifier les statistiques
4. Tester les fonctionnalités de l'application

## Dépannage

### Problèmes courants

1. **psql non trouvé**
   - Installez PostgreSQL
   - Ajoutez psql au PATH

2. **Erreur de connexion à la base de données**
   - Vérifiez les variables d'environnement (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD)
   - Vérifiez que la base de données existe

3. **Permissions insuffisantes**
   - Vérifiez que l'utilisateur a les droits de création de schémas
   - Utilisez un utilisateur avec des privilèges suffisants

### Logs

Les logs sont disponibles dans la console de l'application :
- Création de schémas
- Erreurs de migration
- Opérations d'administration

## Support

Pour toute question ou problème :
1. Vérifiez les logs de l'application
2. Consultez l'interface d'administration
3. Testez avec un programme de test
4. Sauvegardez avant toute modification

## Avantages

### Sécurité
- Isolation des données par programme
- Contrôle d'accès granulaire
- Sauvegarde sélective

### Performance
- Requêtes plus rapides (moins de données)
- Index optimisés par programme
- Maintenance simplifiée

### Évolutivité
- Facile d'ajouter de nouveaux programmes
- Schémas créés automatiquement
- Gestion centralisée
