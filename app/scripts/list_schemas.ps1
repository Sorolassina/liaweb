# Script PowerShell pour exécuter le script SQL de liste des schémas
# Utilisation: .\scripts\list_schemas.ps1

# Configuration de la base de données (modifier selon vos besoins)
$DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
$DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }
$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "lia_coaching" }
$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "liauser" }

Write-Host "🔍 Liste des schémas de la base de données $DB_NAME" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = Join-Path $PSScriptRoot "list_schemas.sql"

# Vérifier si psql est disponible
if (Get-Command psql -ErrorAction SilentlyContinue) {
    $env:PGPASSWORD = if ($env:PGPASSWORD) { $env:PGPASSWORD } else { "liapass123" }
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $scriptPath
} else {
    Write-Host "❌ psql n'est pas trouvé dans le PATH" -ForegroundColor Red
    Write-Host "💡 Assurez-vous que PostgreSQL est installé et que psql est dans votre PATH" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternative: Exécutez le script SQL directement avec:" -ForegroundColor Yellow
    Write-Host "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $scriptPath" -ForegroundColor Cyan
}

