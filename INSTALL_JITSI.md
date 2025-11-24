# 🚀 Installation Rapide de Jitsi Meet Auto-hébergé

## ✅ Vous avez déjà Docker installé - Parfait !

---

## 📝 Étape 1 : Installer Jitsi (5 minutes)

### Option A : Avec le script automatique (Recommandé)

**Sur Windows (PowerShell) :**
```powershell
.\scripts\install_jitsi.ps1
```

Le script va vous demander :
- Votre domaine (ex: `meet.votredomaine.com`) **OU**
- Votre IP publique (ex: `123.45.67.89`)

### Option B : Installation manuelle

```powershell
# 1. Aller dans votre dossier home
cd $env:USERPROFILE

# 2. Cloner Jitsi
git clone https://github.com/jitsi/docker-jitsi-meet
cd docker-jitsi-meet

# 3. Créer la config
Copy-Item env.example .env

# 4. Générer les mots de passe (nécessite Git Bash ou WSL)
# Si vous avez Git Bash :
bash -c "./gen-passwords.sh"
# OU si vous avez WSL :
wsl bash -c "cd /mnt/c/Users/$env:USERNAME/docker-jitsi-meet && ./gen-passwords.sh"

# 5. Créer les dossiers
$cfgDir = "$env:USERPROFILE\.jitsi-meet-cfg"
New-Item -ItemType Directory -Force -Path "$cfgDir\web\letsencrypt"
New-Item -ItemType Directory -Force -Path "$cfgDir\transcripts"
New-Item -ItemType Directory -Force -Path "$cfgDir\prosody\config"
New-Item -ItemType Directory -Force -Path "$cfgDir\prosody\prosody-plugins-custom"
New-Item -ItemType Directory -Force -Path "$cfgDir\jicofo"
New-Item -ItemType Directory -Force -Path "$cfgDir\jvb"
New-Item -ItemType Directory -Force -Path "$cfgDir\jigasi"
New-Item -ItemType Directory -Force -Path "$cfgDir\jibri"

# 6. Éditer le fichier .env
notepad .env
```

Dans le fichier `.env`, modifiez :
```env
# Remplacez par votre domaine ou IP
PUBLIC_URL=https://VOTRE_DOMAINE_OU_IP

# Désactiver l'auth pour commencer
ENABLE_AUTH=0
ENABLE_GUESTS=1

# Si vous utilisez une IP (pas de domaine), désactiver Let's Encrypt
ENABLE_LETSENCRYPT=0
```

```powershell
# 7. Lancer Jitsi
docker-compose up -d

# 8. Attendre 30 secondes puis vérifier
Start-Sleep -Seconds 30
docker-compose ps
```

---

## ⚙️ Étape 2 : Configurer votre Application

### 1. Ajouter dans votre `.env` (à la racine du projet)

```env
# Visioconférence
VIDEO_CONFERENCE_TYPE=jitsi
JITSI_DOMAIN=votre-domaine-ou-ip
```

**Exemple :**
- Si vous avez un domaine : `JITSI_DOMAIN=meet.votredomaine.com`
- Si vous avez une IP : `JITSI_DOMAIN=123.45.67.89`

### 2. Redémarrer votre application FastAPI

Votre application utilisera automatiquement votre instance Jitsi !

---

## 🧪 Étape 3 : Tester

1. **Tester Jitsi directement :**
   - Ouvrez votre navigateur
   - Allez à `https://votre-domaine-ou-ip`
   - Vous devriez voir l'interface Jitsi

2. **Tester depuis votre application :**
   - Créez un rendez-vous
   - Cliquez sur "Commencer RDV vidéo"
   - La vidéo devrait utiliser votre instance Jitsi

---

## 🔧 Commandes Utiles

```powershell
# Voir les logs
cd $env:USERPROFILE\docker-jitsi-meet
docker-compose logs -f

# Arrêter Jitsi
docker-compose down

# Redémarrer Jitsi
docker-compose restart

# Voir le statut
docker-compose ps
```

---

## 🚨 Problèmes Courants

### Les conteneurs ne démarrent pas
```powershell
# Voir les erreurs
cd $env:USERPROFILE\docker-jitsi-meet
docker-compose logs
```

### Erreur de certificat SSL avec une IP
- Dans `.env`, mettez : `ENABLE_LETSENCRYPT=0`
- Redémarrez : `docker-compose restart`

### Les participants ne se voient pas
- Vérifiez que le port UDP 10000 est ouvert dans votre firewall
- Vérifiez les logs : `docker-compose logs jvb`

---

## 📚 Documentation Complète

Voir `docs/INSTALLATION_JITSI_GUIDE.md` pour plus de détails.

---

## ✅ Checklist

- [ ] Jitsi installé et démarré
- [ ] Interface accessible dans le navigateur
- [ ] Configuration ajoutée dans `.env` de l'application
- [ ] Application redémarrée
- [ ] Test d'une réunion vidéo réussi

**🎉 C'est tout ! Votre Jitsi est maintenant auto-hébergé et 100% open source !**

