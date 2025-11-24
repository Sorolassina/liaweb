# 🚀 Guide d'Installation Jitsi Meet - Étape par Étape

## 📋 Prérequis

- ✅ Docker installé (vérifié : vous l'avez !)
- ✅ Docker Compose installé (vérifié : vous l'avez !)
- ✅ Un domaine ou une IP publique
- ✅ Ports ouverts : 80 (HTTP), 443 (HTTPS), 10000 (UDP pour vidéo)

---

## 🎯 Option 1 : Installation Automatique (Recommandé)

### Sur Linux/Mac :
```bash
chmod +x scripts/install_jitsi.sh
./scripts/install_jitsi.sh
```

### Sur Windows (PowerShell) :
```powershell
.\scripts\install_jitsi.ps1
```

Le script vous demandera votre domaine ou IP et fera tout automatiquement.

---

## 🛠️ Option 2 : Installation Manuelle

### Étape 1 : Cloner le dépôt Jitsi

```bash
cd ~
git clone https://github.com/jitsi/docker-jitsi-meet
cd docker-jitsi-meet
```

### Étape 2 : Créer la configuration

```bash
cp env.example .env
```

### Étape 3 : Générer les mots de passe

```bash
./gen-passwords.sh
```

### Étape 4 : Créer les dossiers de configuration

```bash
mkdir -p ~/.jitsi-meet-cfg/{web/letsencrypt,transcripts,prosody/config,prosody/prosody-plugins-custom,jicofo,jvb,jigasi,jibri}
```

### Étape 5 : Configurer le domaine

Éditez le fichier `.env` et modifiez :

```env
# Remplacez par votre domaine ou IP
PUBLIC_URL=https://votre-domaine.com
# Ou si vous utilisez une IP :
# PUBLIC_URL=https://VOTRE_IP_PUBLIQUE

# Désactiver l'authentification pour commencer (plus simple)
ENABLE_AUTH=0
ENABLE_GUESTS=1

# Si vous avez un domaine, activer Let's Encrypt
ENABLE_LETSENCRYPT=1
LETSENCRYPT_DOMAIN=votre-domaine.com
LETSENCRYPT_EMAIL=admin@votre-domaine.com

# Si vous utilisez une IP, désactiver Let's Encrypt
# ENABLE_LETSENCRYPT=0
```

### Étape 6 : Lancer les conteneurs

```bash
docker-compose up -d
```

### Étape 7 : Vérifier que tout fonctionne

```bash
docker-compose ps
```

Tous les services doivent être "Up" :
- `web` (interface web)
- `prosody` (serveur XMPP)
- `jicofo` (coordinateur de conférence)
- `jvb` (pont vidéo)

### Étape 8 : Tester

Ouvrez votre navigateur et allez à :
- `https://votre-domaine.com` (si domaine)
- `https://VOTRE_IP` (si IP)

Vous devriez voir l'interface Jitsi Meet !

---

## ⚙️ Configuration dans votre Application

### 1. Créer/modifier le fichier `.env` à la racine du projet

```env
# Visioconférence
VIDEO_CONFERENCE_TYPE=jitsi
JITSI_DOMAIN=votre-domaine.com
# Ou si vous utilisez une IP :
# JITSI_DOMAIN=VOTRE_IP_PUBLIQUE
```

### 2. Redémarrer votre application FastAPI

Le template utilisera automatiquement votre domaine configuré !

---

## 🔧 Configuration Avancée

### Activer l'authentification JWT (Optionnel)

Si vous voulez sécuriser votre instance :

1. **Dans le `.env` de Jitsi** (`docker-jitsi-meet/.env`) :
```env
ENABLE_AUTH=1
ENABLE_GUESTS=0
JWT_APP_ID=votre-app-id
JWT_APP_SECRET=votre-secret-super-securise
JWT_ACCEPTED_ISSUERS=votre-domaine.com
JWT_ACCEPTED_AUDIENCES=votre-app-id
```

2. **Dans votre `.env` d'application** :
```env
JITSI_APP_ID=votre-app-id
JITSI_APP_SECRET=votre-secret-super-securise
```

### Personnaliser l'interface

Modifier `~/.jitsi-meet-cfg/web/config.js` et `interface_config.js`

---

## 📊 Commandes Utiles

```bash
# Voir les logs
cd ~/docker-jitsi-meet
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs -f web
docker-compose logs -f jvb

# Arrêter les services
docker-compose down

# Redémarrer les services
docker-compose restart

# Mettre à jour Jitsi
cd ~/docker-jitsi-meet
git pull
docker-compose pull
docker-compose up -d
```

---

## 🚨 Dépannage

### Les participants ne se voient pas

1. Vérifier que le port UDP 10000 est ouvert dans le firewall
2. Vérifier les logs : `docker-compose logs jvb`
3. Vérifier que le service `jvb` est "Up" : `docker-compose ps`

### Erreur de certificat SSL

- Si vous utilisez une IP, désactivez Let's Encrypt : `ENABLE_LETSENCRYPT=0`
- Si vous utilisez un domaine, vérifiez que le DNS pointe vers votre serveur
- Vérifiez que les ports 80 et 443 sont ouverts

### Les conteneurs ne démarrent pas

```bash
# Voir les erreurs
docker-compose logs

# Vérifier l'espace disque
df -h

# Vérifier la mémoire
free -h
```

### Réinitialiser complètement

```bash
cd ~/docker-jitsi-meet
docker-compose down -v
rm -rf ~/.jitsi-meet-cfg
# Puis recommencer depuis l'étape 2
```

---

## 🔒 Sécurité

### Firewall recommandé

```bash
# Autoriser HTTP, HTTPS et UDP 10000
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 10000/udp
```

### Mettre à jour régulièrement

```bash
cd ~/docker-jitsi-meet
git pull
docker-compose pull
docker-compose up -d
```

---

## 📚 Ressources

- Documentation officielle : https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker
- Support communautaire : https://community.jitsi.org/
- GitHub : https://github.com/jitsi/docker-jitsi-meet

---

## ✅ Checklist de Vérification

- [ ] Docker et Docker Compose installés
- [ ] Dépôt Jitsi cloné
- [ ] Fichier `.env` configuré
- [ ] Mots de passe générés
- [ ] Dossiers de configuration créés
- [ ] Conteneurs lancés et "Up"
- [ ] Interface accessible dans le navigateur
- [ ] Configuration ajoutée dans `.env` de l'application
- [ ] Application redémarrée
- [ ] Test d'une réunion vidéo réussi

---

**🎉 Félicitations ! Votre instance Jitsi est maintenant opérationnelle !**

