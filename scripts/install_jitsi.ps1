# Script PowerShell pour installer Jitsi Meet auto-hébergé sur Windows

Write-Host "🚀 Installation de Jitsi Meet auto-hébergé" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker n'est pas installé. Veuillez l'installer d'abord." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose n'est pas installé. Veuillez l'installer d'abord." -ForegroundColor Red
    exit 1
}

# Essayer de lire la configuration depuis le .env de l'application
# Chercher le .env dans le répertoire courant et les répertoires parents
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = $SCRIPT_DIR
$APP_ENV_FILE = $null

# Chercher le .env en remontant depuis le script
$currentDir = $SCRIPT_DIR
while ($currentDir -and -not $APP_ENV_FILE) {
    $testPath = Join-Path $currentDir ".env"
    if (Test-Path $testPath) {
        $APP_ENV_FILE = $testPath
        $PROJECT_ROOT = $currentDir
        break
    }
    $parent = Split-Path -Parent $currentDir
    if ($parent -eq $currentDir) { break }
    $currentDir = $parent
}

# Si pas trouvé, essayer le répertoire courant
if (-not $APP_ENV_FILE) {
    $testPath = Join-Path (Get-Location) ".env"
    if (Test-Path $testPath) {
        $APP_ENV_FILE = $testPath
        $PROJECT_ROOT = Get-Location
    }
}

$JITSI_DOMAIN = $null
$CLOUDFLARE_HOSTNAME = $null

if ($APP_ENV_FILE) {
    Write-Host "📖 Lecture de la configuration depuis: $APP_ENV_FILE" -ForegroundColor Yellow
    $envContent = Get-Content $APP_ENV_FILE -Raw
    
    # Chercher JITSI_DOMAIN dans le .env
    if ($envContent -match "JITSI_DOMAIN\s*=\s*([^\r\n]+)") {
        $JITSI_DOMAIN = $matches[1].Trim()
        Write-Host "   ✓ JITSI_DOMAIN trouvé: $JITSI_DOMAIN" -ForegroundColor Green
    }
    
    # Chercher CLOUDFLARE_HOSTNAME dans le .env
    if ($envContent -match "CLOUDFLARE_HOSTNAME\s*=\s*([^\r\n]+)") {
        $CLOUDFLARE_HOSTNAME = $matches[1].Trim()
        Write-Host "   ✓ CLOUDFLARE_HOSTNAME trouvé: $CLOUDFLARE_HOSTNAME" -ForegroundColor Green
    }
}

# Priorité : JITSI_DOMAIN > CLOUDFLARE_HOSTNAME (avec sous-domaine meet.) > Demander à l'utilisateur
if ([string]::IsNullOrWhiteSpace($JITSI_DOMAIN)) {
    if (-not [string]::IsNullOrWhiteSpace($CLOUDFLARE_HOSTNAME)) {
        # Proposer un sous-domaine pour Jitsi
        $suggestedDomain = "meet.$CLOUDFLARE_HOSTNAME"
        Write-Host ""
        Write-Host "📝 Domaine Cloudflare trouvé: $CLOUDFLARE_HOSTNAME" -ForegroundColor Cyan
        $useSuggested = Read-Host "   Utiliser '$suggestedDomain' pour Jitsi? (o/n)"
        if ($useSuggested -eq "o" -or $useSuggested -eq "O" -or [string]::IsNullOrWhiteSpace($useSuggested)) {
            $JITSI_DOMAIN = $suggestedDomain
            Write-Host "   ✓ Utilisation de: $JITSI_DOMAIN" -ForegroundColor Green
        } else {
            $JITSI_DOMAIN = Read-Host "   Entrez votre domaine pour Jitsi (ex: meet.votredomaine.com) ou votre IP publique"
        }
    } else {
        # Demander à l'utilisateur
        Write-Host ""
        Write-Host "🌐 Aucune configuration trouvée dans .env" -ForegroundColor Yellow
        $JITSI_DOMAIN = Read-Host "   Entrez votre domaine (ex: meet.votredomaine.com) ou votre IP publique"
    }
} else {
    Write-Host ""
    Write-Host "📝 Utilisation du domaine Jitsi configuré: $JITSI_DOMAIN" -ForegroundColor Cyan
}

if ([string]::IsNullOrWhiteSpace($JITSI_DOMAIN)) {
    Write-Host "❌ Le domaine/IP est requis" -ForegroundColor Red
    exit 1
}

# Créer le dossier d'installation
$INSTALL_DIR = Join-Path $env:USERPROFILE "jitsi-meet"
Write-Host "📁 Création du dossier d'installation: $INSTALL_DIR" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
Set-Location $INSTALL_DIR

# Cloner le dépôt Jitsi
$REPO_DIR = Join-Path $INSTALL_DIR "docker-jitsi-meet"
if (-not (Test-Path $REPO_DIR)) {
    Write-Host "📥 Clonage du dépôt Jitsi..." -ForegroundColor Yellow
    git clone https://github.com/jitsi/docker-jitsi-meet.git
    Set-Location $REPO_DIR
} else {
    Write-Host "📂 Le dépôt existe déjà, mise à jour..." -ForegroundColor Yellow
    Set-Location $REPO_DIR
    git pull
}

# Créer le fichier .env
$ENV_FILE = Join-Path $REPO_DIR ".env"
if (-not (Test-Path $ENV_FILE)) {
    Write-Host "⚙️  Création du fichier .env..." -ForegroundColor Yellow
    Copy-Item "env.example" ".env"
} else {
    $REPLACE = Read-Host "⚠️  Le fichier .env existe déjà. Voulez-vous le remplacer? (o/n)"
    if ($REPLACE -eq "o" -or $REPLACE -eq "O") {
        Copy-Item "env.example" ".env" -Force
    }
}

# Générer les mots de passe
Write-Host "🔐 Génération des mots de passe..." -ForegroundColor Yellow

# Fonction pour générer un mot de passe hexadécimal (comme dans gen-passwords.sh)
function Generate-HexPassword {
    param([int]$Length = 32)
    $bytes = New-Object byte[] ($Length / 2)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

# Générer les mots de passe
$JICOFO_AUTH_PASSWORD = Generate-HexPassword -Length 32
$JVB_AUTH_PASSWORD = Generate-HexPassword -Length 32
$JIGASI_XMPP_PASSWORD = Generate-HexPassword -Length 32
$JIBRI_RECORDER_PASSWORD = Generate-HexPassword -Length 32
$JIBRI_XMPP_PASSWORD = Generate-HexPassword -Length 32
$JIGASI_TRANSCRIBER_PASSWORD = Generate-HexPassword -Length 32

# Lire le contenu actuel du .env de Jitsi
$jitsiEnvContent = Get-Content $ENV_FILE -Raw

# Remplacer ou ajouter les mots de passe
$passwordReplacements = @{
    "JICOFO_AUTH_PASSWORD=" = "JICOFO_AUTH_PASSWORD=$JICOFO_AUTH_PASSWORD"
    "JVB_AUTH_PASSWORD=" = "JVB_AUTH_PASSWORD=$JVB_AUTH_PASSWORD"
    "JIGASI_XMPP_PASSWORD=" = "JIGASI_XMPP_PASSWORD=$JIGASI_XMPP_PASSWORD"
    "JIBRI_RECORDER_PASSWORD=" = "JIBRI_RECORDER_PASSWORD=$JIBRI_RECORDER_PASSWORD"
    "JIBRI_XMPP_PASSWORD=" = "JIBRI_XMPP_PASSWORD=$JIBRI_XMPP_PASSWORD"
    "JIGASI_TRANSCRIBER_PASSWORD=" = "JIGASI_TRANSCRIBER_PASSWORD=$JIGASI_TRANSCRIBER_PASSWORD"
}

foreach ($key in $passwordReplacements.Keys) {
    if ($jitsiEnvContent -match "$key") {
        # Remplacer la valeur existante
        $jitsiEnvContent = $jitsiEnvContent -replace "$key[^\r\n]*", $passwordReplacements[$key]
        Write-Host "   ✓ $key mis à jour" -ForegroundColor Green
    } else {
        # Ajouter la ligne si elle n'existe pas
        $jitsiEnvContent += "$($passwordReplacements[$key])`n"
        Write-Host "   ✓ $key ajouté" -ForegroundColor Green
    }
}

# Sauvegarder le fichier .env de Jitsi
Set-Content -Path $ENV_FILE -Value $jitsiEnvContent -NoNewline
Write-Host "   ✅ Tous les mots de passe ont été générés et configurés!" -ForegroundColor Green

# Créer les dossiers de configuration
Write-Host "📁 Création des dossiers de configuration..." -ForegroundColor Yellow
$CFG_DIR = Join-Path $env:USERPROFILE ".jitsi-meet-cfg"
$DIRS = @(
    "web/letsencrypt",
    "transcripts",
    "prosody/config",
    "prosody/prosody-plugins-custom",
    "jicofo",
    "jvb",
    "jigasi",
    "jibri"
)
foreach ($dir in $DIRS) {
    $fullPath = Join-Path $CFG_DIR $dir
    New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
}

# Configurer le domaine dans .env
Write-Host "⚙️  Configuration du domaine: $JITSI_DOMAIN" -ForegroundColor Yellow

# Déterminer si c'est une IP ou un domaine
$isIP = $JITSI_DOMAIN -match '^\d+\.\d+\.\d+\.\d+$'
if ($isIP) {
    $PUBLIC_URL = "https://$JITSI_DOMAIN"
    $ENABLE_LETSENCRYPT = "0"
    Write-Host "ℹ️  IP détectée. Let's Encrypt sera désactivé." -ForegroundColor Yellow
} else {
    $PUBLIC_URL = "https://$JITSI_DOMAIN"
    $ENABLE_LETSENCRYPT = "1"
    Write-Host "ℹ️  Domaine détecté. Let's Encrypt sera activé." -ForegroundColor Yellow
}

# Vérifier les conflits de ports avec l'application
Write-Host "🔍 Vérification des conflits de ports..." -ForegroundColor Yellow
$APP_PORT = 8000  # Port par défaut de FastAPI
$JITSI_HTTP_PORT = 8001  # Port HTTP pour Jitsi (évite conflit avec FastAPI)
$JITSI_HTTPS_PORT = 8443  # Port HTTPS pour Jitsi

# Vérifier si le port 8000 est utilisé (probablement par FastAPI)
$port8000InUse = $false
try {
    $connection = Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($connection) {
        $port8000InUse = $true
        Write-Host "   ⚠️  Le port 8000 est déjà utilisé (probablement par votre application FastAPI)" -ForegroundColor Yellow
        Write-Host "   ✓ Jitsi utilisera le port $JITSI_HTTP_PORT pour HTTP (au lieu de 8000)" -ForegroundColor Green
    }
} catch {
    # Port non utilisé, on peut utiliser 8000
    $JITSI_HTTP_PORT = 8000
    Write-Host "   ✓ Le port 8000 est libre, Jitsi l'utilisera" -ForegroundColor Green
}

# Modifier le .env
$envContent = Get-Content $ENV_FILE -Raw
$envContent = $envContent -replace '#PUBLIC_URL=', 'PUBLIC_URL='
$envContent = $envContent -replace 'PUBLIC_URL=.*', "PUBLIC_URL=$PUBLIC_URL"
$envContent = $envContent -replace 'ENABLE_AUTH=.*', 'ENABLE_AUTH=0'
$envContent = $envContent -replace 'ENABLE_GUESTS=.*', 'ENABLE_GUESTS=1'

# Configurer les ports HTTP/HTTPS
$envContent = $envContent -replace '#HTTP_PORT=.*', 'HTTP_PORT='
$envContent = $envContent -replace 'HTTP_PORT=.*', "HTTP_PORT=$JITSI_HTTP_PORT"
$envContent = $envContent -replace '#HTTPS_PORT=.*', 'HTTPS_PORT='
$envContent = $envContent -replace 'HTTPS_PORT=.*', "HTTPS_PORT=$JITSI_HTTPS_PORT"

if ($ENABLE_LETSENCRYPT -eq "1") {
    $envContent = $envContent -replace '#ENABLE_LETSENCRYPT=.*', 'ENABLE_LETSENCRYPT=1'
    $envContent = $envContent -replace '#LETSENCRYPT_DOMAIN=.*', "LETSENCRYPT_DOMAIN=$JITSI_DOMAIN"
    $envContent = $envContent -replace '#LETSENCRYPT_EMAIL=.*', "LETSENCRYPT_EMAIL=admin@$JITSI_DOMAIN"
} else {
    $envContent = $envContent -replace '#ENABLE_LETSENCRYPT=.*', 'ENABLE_LETSENCRYPT=0'
}

Set-Content -Path $ENV_FILE -Value $envContent

# Arrêter les conteneurs existants s'ils tournent déjà
Write-Host ""
Write-Host "🛑 Arrêt des conteneurs existants (si présents)..." -ForegroundColor Yellow
try {
    docker-compose down 2>&1 | Out-Null
    Write-Host "   ✓ Conteneurs arrêtés" -ForegroundColor Green
} catch {
    Write-Host "   ℹ️  Aucun conteneur à arrêter" -ForegroundColor Gray
}

# Lancer les conteneurs
Write-Host ""
Write-Host "🐳 Lancement des conteneurs Docker..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors du lancement des conteneurs Docker" -ForegroundColor Red
    Write-Host "   Vérifiez les logs avec: docker-compose logs" -ForegroundColor Yellow
    exit 1
}

# Attendre que les services démarrent
Write-Host "⏳ Attente du démarrage des services (30 secondes)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Vérifier le statut
Write-Host ""
Write-Host "📊 Vérification du statut des services..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "✅ Installation terminée!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Votre instance Jitsi est accessible à:" -ForegroundColor Cyan
if ($isIP) {
    Write-Host "   - HTTP  : http://$JITSI_DOMAIN`:$JITSI_HTTP_PORT" -ForegroundColor White
    Write-Host "   - HTTPS : https://$JITSI_DOMAIN`:$JITSI_HTTPS_PORT" -ForegroundColor White
} else {
    Write-Host "   - HTTP  : http://$JITSI_DOMAIN`:$JITSI_HTTP_PORT (redirige vers HTTPS)" -ForegroundColor White
    Write-Host "   - HTTPS : https://$JITSI_DOMAIN (ou https://$JITSI_DOMAIN`:$JITSI_HTTPS_PORT)" -ForegroundColor White
}
Write-Host ""
Write-Host "📌 Ports utilisés par Jitsi:" -ForegroundColor Yellow
Write-Host "   - HTTP  : $JITSI_HTTP_PORT" -ForegroundColor White
Write-Host "   - HTTPS : $JITSI_HTTPS_PORT" -ForegroundColor White
Write-Host "   - UDP   : 10000 (vidéo/audio)" -ForegroundColor White
if ($port8000InUse) {
    Write-Host ""
    Write-Host "💡 Note: Le port 8000 est utilisé par votre application FastAPI" -ForegroundColor Cyan
    Write-Host "   Jitsi utilise le port $JITSI_HTTP_PORT pour éviter le conflit" -ForegroundColor Cyan
}
Write-Host ""

# Mettre à jour le .env de l'application si trouvé
if ($APP_ENV_FILE) {
    Write-Host "📝 Mise à jour du .env de l'application..." -ForegroundColor Yellow
    $appEnvContent = Get-Content $APP_ENV_FILE -Raw
    
    # Vérifier si JITSI_DOMAIN existe déjà
    if ($appEnvContent -match "JITSI_DOMAIN\s*=") {
        # Remplacer la valeur existante
        $appEnvContent = $appEnvContent -replace "JITSI_DOMAIN\s*=.*", "JITSI_DOMAIN=$JITSI_DOMAIN"
        Write-Host "   ✓ JITSI_DOMAIN mis à jour: $JITSI_DOMAIN" -ForegroundColor Green
    } else {
        # Ajouter la configuration
        if (-not ($appEnvContent -match "# === Visioconférence ===")) {
            $appEnvContent += "`n# === Visioconférence ===`n"
        }
        if (-not ($appEnvContent -match "VIDEO_CONFERENCE_TYPE")) {
            $appEnvContent += "VIDEO_CONFERENCE_TYPE=jitsi`n"
        }
        $appEnvContent += "JITSI_DOMAIN=$JITSI_DOMAIN`n"
        Write-Host "   ✓ JITSI_DOMAIN ajouté: $JITSI_DOMAIN" -ForegroundColor Green
    }
    
    Set-Content -Path $APP_ENV_FILE -Value $appEnvContent -NoNewline
    Write-Host "   ✓ Fichier .env mis à jour!" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "📝 Pour configurer votre application, ajoutez dans votre .env:" -ForegroundColor Yellow
    Write-Host "   JITSI_DOMAIN=$JITSI_DOMAIN" -ForegroundColor White
    Write-Host ""
}
Write-Host "📚 Commandes utiles:" -ForegroundColor Yellow
Write-Host "   - Voir les logs: cd $REPO_DIR ; docker-compose logs -f" -ForegroundColor White
Write-Host "   - Arrêter: cd $REPO_DIR ; docker-compose down" -ForegroundColor White
Write-Host "   - Redémarrer: cd $REPO_DIR ; docker-compose restart" -ForegroundColor White
Write-Host ""

