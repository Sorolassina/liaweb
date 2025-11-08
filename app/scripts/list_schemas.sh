#!/bin/bash
# Script shell pour exécuter le script SQL de liste des schémas
# Utilisation: ./scripts/list_schemas.sh

# Configuration de la base de données (modifier selon vos besoins)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-lia_coaching}"
DB_USER="${DB_USER:-liauser}"

echo "🔍 Liste des schémas de la base de données ${DB_NAME}"
echo "=========================================="
echo ""

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$(dirname "$0")/list_schemas.sql"

