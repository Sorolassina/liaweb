#!/bin/bash
# Script d'installation de Jitsi Meet auto-hébergé

set -e

echo "🚀 Installation de Jitsi Meet auto-hébergé"
echo "=========================================="
echo ""

# Vérifier Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

# Demander le domaine ou IP
read -p "🌐 Entrez votre domaine (ex: meet.votredomaine.com) ou votre IP publique: " JITSI_DOMAIN

if [ -z "$JITSI_DOMAIN" ]; then
    echo "❌ Le domaine/IP est requis"
    exit 1
fi

# Créer le dossier d'installation
INSTALL_DIR="$HOME/jitsi-meet"
echo "📁 Création du dossier d'installation: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Cloner le dépôt Jitsi
if [ ! -d "docker-jitsi-meet" ]; then
    echo "📥 Clonage du dépôt Jitsi..."
    git clone https://github.com/jitsi/docker-jitsi-meet.git
    cd docker-jitsi-meet
else
    echo "📂 Le dépôt existe déjà, mise à jour..."
    cd docker-jitsi-meet
    git pull
fi

# Créer le fichier .env
if [ ! -f ".env" ]; then
    echo "⚙️  Création du fichier .env..."
    cp env.example .env
else
    echo "⚠️  Le fichier .env existe déjà. Voulez-vous le remplacer? (o/n)"
    read -r REPLACE
    if [ "$REPLACE" = "o" ] || [ "$REPLACE" = "O" ]; then
        cp env.example .env
    fi
fi

# Générer les mots de passe
echo "🔐 Génération des mots de passe..."
./gen-passwords.sh

# Créer les dossiers de configuration
echo "📁 Création des dossiers de configuration..."
mkdir -p ~/.jitsi-meet-cfg/{web/letsencrypt,transcripts,prosody/config,prosody/prosody-plugins-custom,jicofo,jvb,jigasi,jibri}

# Configurer le domaine dans .env
echo "⚙️  Configuration du domaine: $JITSI_DOMAIN"

# Déterminer si c'est une IP ou un domaine
if [[ $JITSI_DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # C'est une IP
    PUBLIC_URL="https://$JITSI_DOMAIN"
    ENABLE_LETSENCRYPT=0
    echo "ℹ️  IP détectée. Let's Encrypt sera désactivé."
else
    # C'est un domaine
    PUBLIC_URL="https://$JITSI_DOMAIN"
    ENABLE_LETSENCRYPT=1
    echo "ℹ️  Domaine détecté. Let's Encrypt sera activé."
fi

# Modifier le .env
sed -i.bak "s|#PUBLIC_URL=|PUBLIC_URL=|g" .env
sed -i.bak "s|PUBLIC_URL=.*|PUBLIC_URL=$PUBLIC_URL|g" .env

# Désactiver l'authentification pour commencer (plus simple)
sed -i.bak "s|ENABLE_AUTH=.*|ENABLE_AUTH=0|g" .env
sed -i.bak "s|ENABLE_GUESTS=.*|ENABLE_GUESTS=1|g" .env

# Configurer Let's Encrypt si c'est un domaine
if [ "$ENABLE_LETSENCRYPT" = "1" ]; then
    sed -i.bak "s|#ENABLE_LETSENCRYPT=.*|ENABLE_LETSENCRYPT=1|g" .env
    sed -i.bak "s|#LETSENCRYPT_DOMAIN=.*|LETSENCRYPT_DOMAIN=$JITSI_DOMAIN|g" .env
    sed -i.bak "s|#LETSENCRYPT_EMAIL=.*|LETSENCRYPT_EMAIL=admin@$JITSI_DOMAIN|g" .env
else
    sed -i.bak "s|#ENABLE_LETSENCRYPT=.*|ENABLE_LETSENCRYPT=0|g" .env
fi

# Lancer les conteneurs
echo ""
echo "🐳 Lancement des conteneurs Docker..."
docker-compose up -d

# Attendre que les services démarrent
echo "⏳ Attente du démarrage des services (30 secondes)..."
sleep 30

# Vérifier le statut
echo ""
echo "📊 Vérification du statut des services..."
docker-compose ps

echo ""
echo "✅ Installation terminée!"
echo ""
echo "🌐 Votre instance Jitsi est accessible à: $PUBLIC_URL"
echo ""
echo "📝 Pour configurer votre application, ajoutez dans votre .env:"
echo "   JITSI_DOMAIN=$JITSI_DOMAIN"
echo ""
echo "📚 Commandes utiles:"
echo "   - Voir les logs: cd $INSTALL_DIR/docker-jitsi-meet && docker-compose logs -f"
echo "   - Arrêter: cd $INSTALL_DIR/docker-jitsi-meet && docker-compose down"
echo "   - Redémarrer: cd $INSTALL_DIR/docker-jitsi-meet && docker-compose restart"
echo ""

