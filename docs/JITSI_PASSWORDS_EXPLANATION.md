# 🔐 Explication des Mots de Passe Jitsi

## 📋 À quoi servent les mots de passe générés ?

Les mots de passe générés par `gen-passwords.sh` (ou `gen-jitsi-passwords.ps1`) sont utilisés pour **sécuriser la communication entre les différents composants de Jitsi**.

### 🔑 Mots de passe générés :

1. **`JICOFO_AUTH_PASSWORD`**
   - **Utilité** : Authentification du service Jicofo (Jitsi Conference Focus)
   - **Rôle** : Jicofo coordonne les conférences et gère les participants
   - **Sécurité** : Empêche l'accès non autorisé au service de coordination

2. **`JVB_AUTH_PASSWORD`**
   - **Utilité** : Authentification du JVB (Jitsi Video Bridge)
   - **Rôle** : JVB gère le routage vidéo/audio entre les participants
   - **Sécurité** : Protège le pont vidéo contre les accès non autorisés

3. **`JIGASI_XMPP_PASSWORD`**
   - **Utilité** : Authentification XMPP pour Jigasi (intégration téléphonie)
   - **Rôle** : Permet aux participants d'appeler par téléphone
   - **Sécurité** : Sécurise l'accès au service de téléphonie

4. **`JIBRI_RECORDER_PASSWORD`**
   - **Utilité** : Authentification pour l'enregistrement des sessions
   - **Rôle** : Permet d'enregistrer les réunions vidéo
   - **Sécurité** : Contrôle l'accès au service d'enregistrement

5. **`JIBRI_XMPP_PASSWORD`**
   - **Utilité** : Authentification XMPP pour Jibri (service d'enregistrement)
   - **Rôle** : Communication XMPP pour l'enregistrement
   - **Sécurité** : Sécurise la communication d'enregistrement

6. **`JIGASI_TRANSCRIBER_PASSWORD`**
   - **Utilité** : Authentification pour la transcription
   - **Rôle** : Permet de transcrire les conversations
   - **Sécurité** : Contrôle l'accès au service de transcription

---

## 🔄 Comment ça fonctionne ?

Ces mots de passe sont utilisés **en interne** entre les conteneurs Docker de Jitsi :

```
┌─────────────┐
│   Prosody   │ ← Serveur XMPP (utilise les mots de passe)
│  (XMPP)     │
└──────┬──────┘
       │
       ├──→ Jicofo (utilise JICOFO_AUTH_PASSWORD)
       ├──→ JVB (utilise JVB_AUTH_PASSWORD)
       ├──→ Jigasi (utilise JIGASI_XMPP_PASSWORD)
       └──→ Jibri (utilise JIBRI_XMPP_PASSWORD)
```

**Les utilisateurs finaux ne voient jamais ces mots de passe !** Ils sont uniquement utilisés pour la communication interne entre les services.

---

## 📁 Où sont stockés les mots de passe ?

### ⚠️ Important : Il y a DEUX fichiers `.env` différents !

1. **`.env` de Jitsi** (dans `C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet\.env`)
   - ✅ **C'est ici que les mots de passe sont ajoutés**
   - Contient la configuration de Jitsi
   - Utilisé par Docker Compose pour Jitsi

2. **`.env` de votre application** (dans `C:\Users\SOROLASSINA\OneDrive\Bureau\1. LIA WEB\app_lia_web\.env`)
   - ❌ **Les mots de passe ne sont PAS ajoutés ici** (et c'est normal !)
   - Contient la configuration de votre application FastAPI
   - Utilisé par votre application

---

## 🔍 Vérifier que les mots de passe sont présents

### Dans le .env de Jitsi :

```powershell
cd C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet
Get-Content .env | Select-String -Pattern "PASSWORD"
```

Vous devriez voir :
```
JICOFO_AUTH_PASSWORD=abc123def456...
JVB_AUTH_PASSWORD=xyz789uvw012...
JIGASI_XMPP_PASSWORD=...
JIBRI_RECORDER_PASSWORD=...
JIBRI_XMPP_PASSWORD=...
JIGASI_TRANSCRIBER_PASSWORD=...
```

---

## ❓ Pourquoi ne pas les voir dans le .env de l'application ?

**C'est normal !** Les mots de passe Jitsi ne doivent **PAS** être dans le `.env` de votre application car :

1. ✅ Ils sont uniquement utilisés par les conteneurs Docker de Jitsi
2. ✅ Votre application n'a pas besoin de connaître ces mots de passe
3. ✅ Séparation des responsabilités : Jitsi gère sa propre sécurité

Votre application a seulement besoin de connaître :
- `JITSI_DOMAIN` : Le domaine où Jitsi est accessible
- (Optionnel) `JITSI_APP_ID` et `JITSI_APP_SECRET` : Si vous activez l'authentification JWT

---

## 🔒 Sécurité

### Les mots de passe sont :
- ✅ Générés aléatoirement (32 caractères hexadécimaux)
- ✅ Uniques à chaque installation
- ✅ Stockés uniquement dans le `.env` de Jitsi
- ✅ Utilisés uniquement en interne entre les services

### Bonnes pratiques :
- ✅ Ne jamais partager le `.env` de Jitsi
- ✅ Ne jamais commiter le `.env` dans Git
- ✅ Garder le `.env` de Jitsi sécurisé
- ✅ Régénérer les mots de passe si compromis

---

## 🛠️ Régénérer les mots de passe

Si vous avez besoin de régénérer les mots de passe :

```powershell
cd C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet
..\..\..\OneDrive\Bureau\1. LIA WEB\app_lia_web\scripts\gen-jitsi-passwords.ps1
docker-compose down
docker-compose up -d
```

---

## ✅ Résumé

| Question | Réponse |
|----------|---------|
| **Où sont les mots de passe ?** | Dans `C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet\.env` |
| **Pourquoi pas dans mon .env d'app ?** | Ils ne sont pas nécessaires pour votre application |
| **Les utilisateurs les voient-ils ?** | Non, uniquement utilisés en interne |
| **Sont-ils importants ?** | Oui, pour la sécurité interne de Jitsi |
| **Dois-je les mémoriser ?** | Non, ils sont gérés automatiquement |

---

**💡 En résumé : Les mots de passe sont dans le `.env` de Jitsi, pas dans celui de votre application. C'est normal et sécurisé !**

