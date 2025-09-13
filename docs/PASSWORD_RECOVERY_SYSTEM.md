# Système de Récupération de Mot de Passe

## Vue d'ensemble

Le système de récupération de mot de passe permet aux utilisateurs de réinitialiser leur mot de passe en cas d'oubli, via l'envoi d'un code temporaire par email.

## Fonctionnalités

### 🔐 Processus de récupération
1. **Demande de récupération** : L'utilisateur saisit son email
2. **Envoi du code** : Un code à 6 chiffres est envoyé par email
3. **Vérification** : L'utilisateur saisit le code reçu
4. **Réinitialisation** : Choix d'un nouveau mot de passe sécurisé

### ⏰ Sécurité
- **Code temporaire** : Validité de 15 minutes
- **Usage unique** : Chaque code ne peut être utilisé qu'une fois
- **Nettoyage automatique** : Suppression des codes expirés
- **Traçabilité** : Enregistrement de l'adresse IP

## Installation

### 1. Migration de la base de données
```bash
cd app
python scripts/migrate_password_recovery.py
```

### 2. Test du système
```bash
cd app
python scripts/test_password_recovery.py
```

### 3. Nettoyage automatique (optionnel)
Ajoutez un cron job pour nettoyer les codes expirés :
```bash
# Nettoyage toutes les heures
0 * * * * cd /path/to/app && python -c "from services.cleanup_service import run_cleanup; run_cleanup()"
```

## Utilisation

### Interface Web
1. **Page de connexion** : Cliquer sur "Mot de passe oublié ?"
2. **Demande** : Saisir l'email (`/mot-de-passe-oublie`)
3. **Vérification** : Saisir le code reçu (`/verification-code`)
4. **Réinitialisation** : Choisir un nouveau mot de passe (`/reinitialiser-mot-de-passe`)

### API REST
```bash
# Demander une récupération
POST /api/password-recovery/request
{
    "email": "utilisateur@example.com"
}

# Vérifier un code
POST /api/password-recovery/verify
{
    "email": "utilisateur@example.com",
    "code": "123456"
}

# Réinitialiser le mot de passe
POST /api/password-recovery/reset
{
    "email": "utilisateur@example.com",
    "code": "123456",
    "new_password": "NouveauMotDePasse123",
    "confirm_password": "NouveauMotDePasse123"
}
```

## Configuration

### Variables d'environnement
```bash
# Configuration SMTP (requis pour l'envoi d'emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-mot-de-passe-app
SMTP_TLS=true
SMTP_SSL=false

# Configuration email
MAIL_FROM=noreply@lia-coaching.com
MAIL_FROM_NAME=LIA Coaching
```

### Personnalisation des emails
Les templates d'email sont dans `app/services/password_recovery_service.py` dans la méthode `_send_recovery_email()`.

## Sécurité

### Bonnes pratiques
1. **Codes temporaires** : Durée de vie limitée (15 minutes)
2. **Usage unique** : Chaque code ne peut être utilisé qu'une fois
3. **Validation stricte** : Vérification de la force du mot de passe
4. **Traçabilité** : Enregistrement des tentatives et adresses IP
5. **Nettoyage automatique** : Suppression des codes expirés

### Exigences de mot de passe
- Minimum 8 caractères
- Au moins une majuscule
- Au moins une minuscule
- Au moins un chiffre

## Monitoring

### Logs
Les opérations sont loggées avec les niveaux appropriés :
- `INFO` : Opérations réussies
- `WARNING` : Tentatives invalides
- `ERROR` : Erreurs système

### Métriques
- Nombre de codes générés
- Taux de réussite des réinitialisations
- Codes expirés nettoyés

## Dépannage

### Problèmes courants

#### 1. Email non reçu
- Vérifier la configuration SMTP
- Vérifier les spams/courrier indésirable
- Vérifier les logs d'erreur

#### 2. Code invalide
- Vérifier que le code n'est pas expiré
- Vérifier que le code n'a pas déjà été utilisé
- Vérifier la saisie (6 chiffres uniquement)

#### 3. Erreur de réinitialisation
- Vérifier que le code est valide
- Vérifier les exigences du mot de passe
- Vérifier que les mots de passe correspondent

### Logs utiles
```bash
# Logs de l'application
tail -f logs/app.log | grep "password_recovery"

# Logs PostgreSQL
tail -f /var/log/postgresql/postgresql.log | grep "passwordrecoverycode"
```

## Support

Pour toute question ou problème :
1. Vérifier les logs de l'application
2. Consulter la documentation des modèles
3. Exécuter les tests de validation
4. Contacter l'équipe de développement

---

**Version** : 1.0.0  
**Dernière mise à jour** : 2024  
**Auteur** : Soro Wangboho Lassina
