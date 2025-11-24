# Options de Visioconférence Open Source

## 📋 Vue d'ensemble

Actuellement, l'application utilise Jitsi Meet via le service public `meet.jit.si`. Voici les options pour une solution 100% open source et auto-hébergée.

---

## 🎯 Option 1 : Auto-héberger Jitsi (Recommandé - Le plus simple)

### Avantages
- ✅ **100% Open Source** (Apache 2.0)
- ✅ **Gratuit** (pas de coûts cachés)
- ✅ **Contrôle total** sur vos données
- ✅ **Interface déjà connue** (pas besoin de réécrire le frontend)
- ✅ **Fonctionnalités complètes** (partage d'écran, chat, enregistrement, etc.)

### Installation
```bash
# Avec Docker (le plus simple)
docker run -d \
  --name jitsi-meet \
  -p 80:80 \
  -p 443:443 \
  -p 10000:10000/udp \
  -e ENABLE_AUTH=0 \
  -e ENABLE_GUESTS=1 \
  -e ENABLE_RECORDING=1 \
  jitsi/web

# Ou avec docker-compose (recommandé pour production)
git clone https://github.com/jitsi/docker-jitsi-meet
cd docker-jitsi-meet
cp env.example .env
./gen-passwords.sh
docker-compose up -d
```

### Configuration dans l'application
Il suffit de changer l'URL dans le template :
```javascript
// Au lieu de "meet.jit.si"
const api = new JitsiMeetExternalAPI("votre-domaine.com", options);
```

---

## 🛠️ Option 2 : Solution Custom avec WebRTC (100% Custom)

### Avantages
- ✅ **Contrôle total** sur l'interface et les fonctionnalités
- ✅ **Personnalisation complète** du design
- ✅ **Pas de dépendance externe**
- ✅ **Intégration native** avec votre application

### Inconvénients
- ⚠️ **Plus complexe** à développer
- ⚠️ **Nécessite un serveur de signalisation** (WebSocket)
- ⚠️ **Nécessite un serveur TURN/STUN** pour le NAT traversal
- ⚠️ **Plus de maintenance**

### Architecture nécessaire

1. **Frontend (JavaScript/WebRTC)**
   - Bibliothèques : `simple-peer`, `socket.io-client`, `mediasoup-client`
   - Gestion des streams vidéo/audio
   - Interface utilisateur custom

2. **Backend (Python/FastAPI)**
   - Serveur WebSocket pour la signalisation
   - Gestion des salles de réunion
   - Authentification et autorisation

3. **Serveur TURN/STUN**
   - Coturn (open source)
   - Pour traverser les NAT/firewalls

### Exemple de structure

```
app/
├── services/
│   └── webrtc_service.py      # Gestion WebRTC
├── routers/
│   └── webrtc_router.py      # Routes WebSocket
├── static/
│   ├── js/
│   │   └── webrtc.js         # Client WebRTC
│   └── css/
│       └── video.css          # Styles vidéo
└── templates/
    └── pages/
        └── rendez_vous/
            └── video_custom.html  # Interface custom
```

### Bibliothèques recommandées

**Frontend :**
- `simple-peer` : Simplifie WebRTC
- `socket.io-client` : Communication WebSocket
- `mediasoup-client` : Solution complète (serveur + client)

**Backend :**
- `python-socketio` : Serveur WebSocket
- `aiortc` : WebRTC pour Python (optionnel, pour serveur SFU)

---

## 🔄 Option 3 : Alternatives Open Source

### 1. **Galene** (Simple et léger)
- Installation simple
- Interface basique mais fonctionnelle
- Bon pour petits groupes

### 2. **Nextcloud Talk** (Si vous utilisez Nextcloud)
- Intégration avec Nextcloud
- Fonctionnalités complètes
- Interface moderne

### 3. **Janus Gateway** (Très flexible)
- Serveur WebRTC très puissant
- Nécessite développement frontend custom
- Bon pour solutions enterprise

---

## 💡 Recommandation

### Pour votre cas d'usage (coaching/rendez-vous) :

**Option 1 (Auto-héberger Jitsi)** est la meilleure car :
1. ✅ Migration simple (changer juste l'URL)
2. ✅ Interface déjà testée et fonctionnelle
3. ✅ Fonctionnalités complètes (salle d'attente, partage d'écran, etc.)
4. ✅ Maintenance minimale
5. ✅ 100% open source et gratuit

### Si vous voulez vraiment du custom :

**Option 2** avec `mediasoup` ou `simple-peer` + `socket.io` :
- Plus de travail initial
- Contrôle total sur l'expérience utilisateur
- Intégration parfaite avec votre design

---

## 🚀 Prochaines étapes

1. **Décider de l'option** (recommandé : Option 1)
2. **Configurer les variables d'environnement** pour le service vidéo
3. **Modifier le template** pour utiliser la configuration dynamique
4. **Tester** avec votre instance auto-hébergée

---

## 📚 Ressources

- **Jitsi Documentation** : https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker
- **WebRTC MDN** : https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- **Simple Peer** : https://github.com/feross/simple-peer
- **Mediasoup** : https://mediasoup.org/
- **Socket.IO** : https://socket.io/

