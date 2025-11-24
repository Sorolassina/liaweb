# 🧪 Comment Tester Jitsi dans votre Navigateur

## 🎯 Accès Direct à Jitsi

### Option 1 : Via localhost (Recommandé pour test local)

1. **Ouvrir votre navigateur**
2. **Aller à l'URL** :
   - **HTTP** : `http://localhost:8001` (ou `8000` si pas de conflit)
   - **HTTPS** : `https://localhost:8443`

3. **Accepter le certificat auto-signé** (si HTTPS)
   - Le navigateur affichera un avertissement de sécurité
   - Cliquez sur "Avancé" puis "Continuer vers localhost (non sécurisé)"
   - C'est normal pour un certificat auto-signé en local

### Option 2 : Via votre domaine/IP

Si vous avez configuré un domaine ou une IP publique :

- **HTTP** : `http://skpartners.consulting:8001`
- **HTTPS** : `https://skpartners.consulting:8443` (ou `https://skpartners.consulting` si port 443)

---

## 🎬 Créer une Réunion de Test

### Étape 1 : Accéder à Jitsi

1. Ouvrez votre navigateur
2. Allez à `https://localhost:8443` (ou votre URL configurée)
3. Vous devriez voir l'interface Jitsi Meet

### Étape 2 : Créer une salle

1. **Entrez un nom de salle** (ex: `test-reunion-123`)
2. **Cliquez sur "Go"** ou appuyez sur Entrée
3. **Autorisez l'accès** à votre micro et caméra quand le navigateur le demande

### Étape 3 : Tester avec plusieurs onglets

Pour simuler plusieurs participants :

1. **Ouvrez un deuxième onglet** dans votre navigateur
2. **Allez à la même URL** : `https://localhost:8443`
3. **Entrez le même nom de salle** : `test-reunion-123`
4. **Vous devriez voir les deux participants** dans la même réunion !

---

## 🔍 Vérifier que tout fonctionne

### Tests à effectuer :

- [ ] ✅ L'interface Jitsi s'affiche correctement
- [ ] ✅ Vous pouvez activer/désactiver votre micro
- [ ] ✅ Vous pouvez activer/désactiver votre caméra
- [ ] ✅ Vous pouvez voir votre propre vidéo
- [ ] ✅ Avec 2 onglets, vous voyez les 2 participants
- [ ] ✅ Le partage d'écran fonctionne (si testé)
- [ ] ✅ Le chat fonctionne (si testé)

---

## 🚨 Problèmes Courants

### Erreur : "Impossible de se connecter"

**Solution :**
```powershell
# Vérifier que les conteneurs tournent
cd C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet
docker-compose ps

# Voir les logs
docker-compose logs web
```

### Erreur de certificat SSL

**Solution :**
- C'est normal en local avec un certificat auto-signé
- Cliquez sur "Avancé" → "Continuer vers localhost"
- Ou utilisez HTTP : `http://localhost:8001`

### La vidéo ne fonctionne pas

**Vérifications :**
1. Autorisez l'accès au micro/caméra dans le navigateur
2. Vérifiez que le port UDP 10000 est ouvert
3. Vérifiez les logs : `docker-compose logs jvb`

### Les participants ne se voient pas

**Vérifications :**
1. Vérifiez que les deux onglets utilisent le même nom de salle
2. Vérifiez les logs : `docker-compose logs jicofo`
3. Vérifiez que le port UDP 10000 est accessible

---

## 📊 Commandes Utiles pour le Debug

```powershell
# Voir le statut des conteneurs
cd C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet
docker-compose ps

# Voir les logs en temps réel
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs -f web      # Interface web
docker-compose logs -f jvb      # Pont vidéo
docker-compose logs -f jicofo   # Coordinateur
docker-compose logs -f prosody  # Serveur XMPP

# Redémarrer un service
docker-compose restart web

# Redémarrer tous les services
docker-compose restart
```

---

## 🎯 Test Complet : Scénario Réaliste

### Test avec 2 participants (2 onglets) :

1. **Onglet 1** : `https://localhost:8443` → Salle `test-123`
   - Activez votre caméra et micro
   - Vous devriez vous voir

2. **Onglet 2** : `https://localhost:8443` → Salle `test-123`
   - Activez votre caméra et micro
   - Vous devriez voir les 2 participants

3. **Testez les fonctionnalités** :
   - Parler dans un onglet, écouter dans l'autre
   - Activer/désactiver le micro
   - Activer/désactiver la caméra
   - Partager l'écran (si disponible)

---

## ✅ Checklist de Test

Avant d'intégrer à votre application, vérifiez :

- [ ] ✅ Jitsi est accessible dans le navigateur
- [ ] ✅ Vous pouvez créer une salle
- [ ] ✅ La vidéo fonctionne
- [ ] ✅ L'audio fonctionne
- [ ] ✅ Plusieurs participants peuvent se rejoindre
- [ ] ✅ Les participants se voient et s'entendent
- [ ] ✅ Le partage d'écran fonctionne (optionnel)
- [ ] ✅ Le chat fonctionne (optionnel)

---

## 🔗 URLs de Test

### En local :
- HTTP : `http://localhost:8001`
- HTTPS : `https://localhost:8443`

### Avec votre domaine :
- HTTP : `http://skpartners.consulting:8001`
- HTTPS : `https://skpartners.consulting:8443`

---

## 💡 Astuce

Pour tester rapidement, créez un raccourci dans votre navigateur :
- URL : `https://localhost:8443`
- Nom : "Jitsi Local"

---

**🎉 Une fois que tout fonctionne dans le navigateur, vous pouvez l'intégrer à votre application !**

