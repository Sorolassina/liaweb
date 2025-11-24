# 🔗 Intégration de Jitsi dans l'Application

## ✅ Modifications Effectuées

### 1. Configuration Automatique Debug/Production

Le système détecte automatiquement l'environnement et utilise :
- **En DEBUG** : `http://localhost:8001` (votre instance locale)
- **En PRODUCTION** : `https://skpartners.consulting` (votre domaine Cloudflare)

### 2. Génération de Noms de Salle

La fonction `generate_meet_link()` génère maintenant des noms de salle Jitsi uniques :
- Format : `rdv-abc123def4` (au lieu d'un lien Google Meet)
- Compatible avec l'ancien format pour la rétrocompatibilité

### 3. Template Mis à Jour

Le template `seance_jitsi.html` utilise automatiquement :
- `settings.JITSI_URL_ACTIVE` : URL complète avec protocole (http/https)
- `settings.JITSI_DOMAIN_ACTIVE` : Domaine uniquement

---

## ⚙️ Configuration dans `.env`

### Pour le Test Local (DEBUG) :

```env
# === Environnement ===
DEBUG=True

# === Visioconférence ===
VIDEO_CONFERENCE_TYPE=jitsi
JITSI_DOMAIN=skpartners.consulting
JITSI_DOMAIN_DEBUG=localhost:8001
```

### Pour la Production :

```env
# === Environnement ===
DEBUG=False

# === Visioconférence ===
VIDEO_CONFERENCE_TYPE=jitsi
JITSI_DOMAIN=skpartners.consulting
# JITSI_DOMAIN_DEBUG n'est pas nécessaire en production
```

---

## 🧪 Tester l'Intégration

### 1. Vérifier la Configuration

```powershell
# Vérifier que Jitsi tourne
cd C:\Users\SOROLASSINA\jitsi-meet\docker-jitsi-meet
docker-compose ps
```

### 2. Démarrer votre Application

```powershell
python -m app.main
```

### 3. Tester un Rendez-vous Vidéo

1. **Connectez-vous** à votre application
2. **Créez un rendez-vous** ou utilisez un existant
3. **Cliquez sur "Commencer RDV vidéo"** ou "Continuer le rendez-vous vidéo"
4. **Vérifiez** que Jitsi se charge avec votre instance locale

### 4. Vérifier dans les Logs

Dans la console de votre navigateur (F12), vous devriez voir :
- Le script chargé depuis : `http://localhost:8001/external_api.js`
- La salle Jitsi créée avec le nom généré

---

## 🔍 Vérifications

### Dans le Navigateur (F12 → Console) :

```javascript
// Vérifier que le script Jitsi est chargé
console.log(jitsiDomain); // Devrait afficher "localhost:8001" en debug

// Vérifier que la salle est créée
// Vous devriez voir les logs Jitsi dans la console
```

### Dans les Logs de l'Application :

```
✅ Page RDV vidéo chargée pour RDV {id}
🔍 [commencer_rdv_video] Schéma configuré: acd
```

---

## 🚨 Problèmes Courants

### Le script Jitsi ne se charge pas

**Vérifier :**
1. Que Jitsi tourne : `docker-compose ps` dans le dossier Jitsi
2. Que le port est accessible : `http://localhost:8001` dans le navigateur
3. Les logs : `docker-compose logs web`

### Erreur CORS

**Solution :** Jitsi doit être configuré pour accepter les requêtes depuis votre domaine d'application.

### La salle ne se crée pas

**Vérifier :**
1. Que le `room_name` est bien généré
2. Les logs du navigateur (F12)
3. Les logs Jitsi : `docker-compose logs jicofo`

---

## 📋 Checklist d'Intégration

- [ ] ✅ Jitsi installé et accessible sur `http://localhost:8001`
- [ ] ✅ Configuration ajoutée dans `.env` :
  - [ ] `DEBUG=True`
  - [ ] `JITSI_DOMAIN=skpartners.consulting`
  - [ ] `JITSI_DOMAIN_DEBUG=localhost:8001`
- [ ] ✅ Application redémarrée
- [ ] ✅ Test d'un rendez-vous vidéo réussi
- [ ] ✅ Vérification que le script se charge depuis `http://localhost:8001`
- [ ] ✅ Vérification que la salle Jitsi se crée correctement
- [ ] ✅ Test avec 2 participants (2 onglets)

---

## 🎯 Prochaines Étapes

Une fois que tout fonctionne en local :

1. **Configurer le DNS** pour `skpartners.consulting`
2. **Configurer Jitsi** pour utiliser le domaine en production
3. **Mettre à jour le `.env`** : `DEBUG=False`
4. **Tester en production**

---

**🎉 Votre application est maintenant intégrée avec Jitsi auto-hébergé !**

