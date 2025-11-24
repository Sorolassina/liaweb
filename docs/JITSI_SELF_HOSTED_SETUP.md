# Guide : Auto-héberger Jitsi Meet

## 🎯 Objectif

Remplacer le service public `meet.jit.si` par votre propre instance Jitsi auto-hébergée, 100% open source et gratuite.

---

## 📦 Installation avec Docker (Recommandé)

### Prérequis
- Docker et Docker Compose installés
- Un serveur avec au moins 2GB RAM
- Un domaine (optionnel mais recommandé)

### Étapes

1. **Cloner le dépôt officiel Jitsi**
```bash
git clone https://github.com/jitsi/docker-jitsi-meet
cd docker-jitsi-meet
```

2. **Créer le fichier de configuration**
```bash
cp env.example .env
```

3. **Générer les mots de passe**
```bash
./gen-passwords.sh
```

4. **Créer les dossiers nécessaires**
```bash
mkdir -p ~/.jitsi-meet-cfg/{web/letsencrypt,transcripts,prosody/config,prosody/prosody-plugins-custom,jicofo,jvb,jigasi,jibri}
```

5. **Configurer le domaine dans `.env`**
```env
# Définir votre domaine (ou IP si pas de domaine)
CONFIG=~/.jitsi-meet-cfg
TZ=Europe/Paris
PUBLIC_URL=https://votre-domaine.com
# Ou pour IP publique :
# PUBLIC_URL=https://VOTRE_IP_PUBLIQUE

# Désactiver l'authentification (pour commencer)
ENABLE_AUTH=0
ENABLE_GUESTS=1
```

6. **Lancer les conteneurs**
```bash
docker-compose up -d
```

7. **Vérifier que tout fonctionne**
```bash
docker-compose ps
# Tous les services doivent être "Up"
```

8. **Accéder à votre instance**
Ouvrez votre navigateur : `https://votre-domaine.com` (ou `https://VOTRE_IP`)

---

## ⚙️ Configuration dans votre application

### 1. Ajouter dans votre `.env`

```env
# Visioconférence
VIDEO_CONFERENCE_TYPE=jitsi
JITSI_DOMAIN=votre-domaine.com
# Ou si vous utilisez une IP :
# JITSI_DOMAIN=VOTRE_IP_PUBLIQUE
```

### 2. Redémarrer l'application

Le template utilisera automatiquement votre domaine configuré au lieu de `meet.jit.si`.

---

## 🔒 Sécurité (Optionnel mais recommandé)

### Activer l'authentification JWT

1. **Dans `.env` de Jitsi :**
```env
ENABLE_AUTH=1
ENABLE_GUESTS=0
JWT_APP_ID=votre-app-id
JWT_APP_SECRET=votre-secret-super-securise
JWT_ACCEPTED_ISSUERS=votre-domaine.com
JWT_ACCEPTED_AUDIENCES=votre-app-id
```

2. **Dans votre `.env` d'application :**
```env
JITSI_APP_ID=votre-app-id
JITSI_APP_SECRET=votre-secret-super-securise
```

3. **Modifier le template pour inclure le token JWT** (si nécessaire)

---

## 📊 Monitoring et logs

```bash
# Voir les logs
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs -f web
docker-compose logs -f jvb  # Jitsi Video Bridge
docker-compose logs -f jicofo  # Jitsi Conference Focus
```

---

## 🔧 Personnalisation

### Changer le thème
Modifier `~/.jitsi-meet-cfg/web/config.js` :
```javascript
// Couleurs personnalisées
interfaceConfig = {
    TOOLBAR_BUTTONS: [...],
    DEFAULT_BACKGROUND: '#000000',
    // etc.
}
```

### Activer l'enregistrement
```env
ENABLE_RECORDING=1
```

---

## 🚨 Dépannage

### Problème : Les participants ne se voient pas
- Vérifier que les ports UDP 10000 sont ouverts
- Vérifier le firewall
- Vérifier les logs : `docker-compose logs jvb`

### Problème : Connexion refusée
- Vérifier que tous les conteneurs sont "Up" : `docker-compose ps`
- Vérifier les logs : `docker-compose logs`

### Problème : Certificat SSL
- Si vous utilisez un domaine, configurer Let's Encrypt
- Ou utiliser un reverse proxy (Nginx) avec certificat SSL

---

## 💰 Coûts

**Gratuit !** 🎉
- Jitsi est 100% open source
- Pas de coûts cachés
- Seuls les coûts d'hébergement du serveur (si vous utilisez un VPS)

---

## 📚 Ressources

- Documentation officielle : https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker
- Support communautaire : https://community.jitsi.org/
- GitHub : https://github.com/jitsi/docker-jitsi-meet

