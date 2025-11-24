# Script PowerShell pour générer les mots de passe Jitsi
# Alternative à gen-passwords.sh pour Windows

$ENV_FILE = Join-Path (Get-Location) ".env"

if (-not (Test-Path $ENV_FILE)) {
    Write-Host "❌ Fichier .env introuvable dans le répertoire courant" -ForegroundColor Red
    Write-Host "   Exécutez ce script depuis le dossier docker-jitsi-meet" -ForegroundColor Yellow
    exit 1
}

Write-Host "🔐 Génération des mots de passe Jitsi..." -ForegroundColor Cyan
Write-Host ""

# Fonction pour générer un mot de passe aléatoire
function Generate-Password {
    param([int]$Length = 32)
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    $password = ""
    for ($i = 0; $i -lt $Length; $i++) {
        $password += $chars[(Get-Random -Maximum $chars.Length)]
    }
    return $password
}

# Générer les mots de passe (32 caractères hexadécimaux comme dans le script bash)
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

# Lire le contenu actuel du .env
$envContent = Get-Content $ENV_FILE -Raw

# Remplacer ou ajouter les mots de passe
$replacements = @{
    "JICOFO_AUTH_PASSWORD=" = "JICOFO_AUTH_PASSWORD=$JICOFO_AUTH_PASSWORD"
    "JVB_AUTH_PASSWORD=" = "JVB_AUTH_PASSWORD=$JVB_AUTH_PASSWORD"
    "JIGASI_XMPP_PASSWORD=" = "JIGASI_XMPP_PASSWORD=$JIGASI_XMPP_PASSWORD"
    "JIBRI_RECORDER_PASSWORD=" = "JIBRI_RECORDER_PASSWORD=$JIBRI_RECORDER_PASSWORD"
    "JIBRI_XMPP_PASSWORD=" = "JIBRI_XMPP_PASSWORD=$JIBRI_XMPP_PASSWORD"
    "JIGASI_TRANSCRIBER_PASSWORD=" = "JIGASI_TRANSCRIBER_PASSWORD=$JIGASI_TRANSCRIBER_PASSWORD"
}

foreach ($key in $replacements.Keys) {
    if ($envContent -match "$key") {
        # Remplacer la valeur existante
        $envContent = $envContent -replace "$key[^\r\n]*", $replacements[$key]
        Write-Host "   ✓ $key mis à jour" -ForegroundColor Green
    } else {
        # Ajouter la ligne si elle n'existe pas
        $envContent += "$($replacements[$key])`n"
        Write-Host "   ✓ $key ajouté" -ForegroundColor Green
    }
}

# Sauvegarder le fichier
Set-Content -Path $ENV_FILE -Value $envContent -NoNewline

Write-Host ""
Write-Host "✅ Mots de passe générés avec succès!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Les mots de passe ont été ajoutés/mis à jour dans le fichier .env" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Pour appliquer les changements, redémarrez les conteneurs:" -ForegroundColor Yellow
Write-Host "   docker-compose down" -ForegroundColor White
Write-Host "   docker-compose up -d" -ForegroundColor White
Write-Host ""

