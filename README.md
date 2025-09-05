# 🎯 LIA Coaching - Application de Gestion de Coaching

Application complète de gestion de coaching pour les programmes ACD, ACI et ACT.

## 🚀 Lancement Rapide

### Option 1 : Lancement automatique (Recommandé)
```bash
python run_lia.py
```

Ce script va automatiquement :
- ✅ Vérifier l'environnement
- ✅ Configurer PostgreSQL (base de données + utilisateur)
- ✅ Créer les fichiers statiques
- ✅ Lancer l'application

### Option 2 : Configuration manuelle

1. **Installer les dépendances** :
```bash
cd app
pip install -r requirements.txt
```

2. **Configurer PostgreSQL** :
```bash
cd app
python setup_database.py
```

3. **Lancer l'application** :
```bash
cd app
python main.py
```

## 🗄️ Configuration PostgreSQL

L'application utilise PostgreSQL avec les paramètres suivants :
- **Base de données** : `lia_coaching`
- **Utilisateur** : `liauser`
- **Mot de passe** : `liapass123`
- **Hôte** : `localhost`
- **Port** : `5432`

### Installation de PostgreSQL

#### Windows :
1. Télécharger PostgreSQL depuis [postgresql.org](https://www.postgresql.org/download/windows/)
2. Installer avec l'utilisateur `postgres` et le mot de passe `postgres`
3. Lancer le script `run_lia.py`

#### Linux (Ubuntu/Debian) :
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS :
```bash
brew install postgresql
brew services start postgresql
```

## 🎨 Interface Utilisateur

L'application utilise :
- **Backend** : FastAPI + SQLModel
- **Frontend** : HTML + Bootstrap 5 + Jinja2
- **Thème** : Couleurs LIA (Jaune, Noir, Blanc)
- **Base de données** : PostgreSQL

## 📁 Structure du Projet

```
lia-coaching/
├── app/
│   ├── core/           # Configuration, sécurité, base de données
│   ├── models/         # Modèles SQLModel
│   ├── routers/        # Routes API et web
│   ├── services/       # Logique métier
│   ├── schemas/        # Schémas Pydantic
│   ├── templates/      # Templates Jinja2
│   ├── static/         # Fichiers CSS/JS
│   └── main.py         # Point d'entrée
├── run_lia.py          # Script de lancement automatique
└── README.md           # Ce fichier
```

## 🔧 Fonctionnalités

### ✅ Gestion des Programmes
- ACD (Accompagnement Créateur d'Entreprise)
- ACI (Accompagnement Créateur d'Innovation)
- ACT (Accompagnement Créateur de Territoire)

### ✅ Gestion des Candidats
- Préinscription en ligne
- Validation par jury
- Suivi du pipeline de formation
- Gestion des documents

### ✅ Système de Jury
- Sessions de délibération
- Validation/rejet des candidatures
- Attribution des conseillers

### ✅ Pipeline de Formation
- Étapes configurables par programme
- Suivi de l'avancement
- Alertes et notifications

### ✅ Gestion des Documents
- Upload sécurisé
- Validation des types de fichiers
- Organisation par candidat

## 🌐 Accès à l'Application

Une fois lancée, l'application est accessible sur :
- **Interface web** : http://localhost:8000
- **Documentation API** : http://localhost:8000/docs
- **Documentation ReDoc** : http://localhost:8000/redoc

## 🔐 Authentification

L'application utilise JWT pour l'authentification :
- **Admin par défaut** : `sorolassina58@gmail.com`
- **Mot de passe** : `ChangeMoi#2025`

## 🛠️ Développement

### Variables d'environnement
Créer un fichier `.env` dans le répertoire `app/` :
```env
DEBUG=true
ENVIRONMENT=development
PAPPERS_API_KEY=your_api_key_here
```

### Mode développement
```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📞 Support

Pour toute question ou problème :
- **Email** : sorolassina58@gmail.com
- **Auteur** : Soro Wangboho Lassina

---

**Version** : 1.0.0  
**Dernière mise à jour** : 2024
