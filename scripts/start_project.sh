#!/bin/bash
# --- start_project.sh ---

# Configuratie
API_URL="http://127.0.0.1:8080/deploy/full-stack"
PLATFORM_DB_CONTAINER="skill_21-platform-db-1"

KLANT=$1
GITHUB_URL=$2
USER_ID=$(docker exec -i "$PLATFORM_DB_CONTAINER" psql -U platform -d platform -t -A -c "SELECT id FROM users WHERE client_name='$KLANT' LIMIT 1;")

# Controleer of er wel een ID gevonden is
if [ -z "$USER_ID" ]; then
    echo "ERROR: Geen user_id gevonden voor klant '$KLANT'. Bestaat deze klant wel in de 'users' tabel?"
    exit 1
fi

echo "Gevonden User ID: $USER_ID"

if [ "$#" -lt 2 ]; then
    echo "Gebruik: $0 <klantnaam> <github_url>"
    exit 1
fi

RAW_PROJECT_NAME=$(basename "$GITHUB_URL" .git)
# Omzetten naar kleine letters met tr
PROJECT_NAME=$(echo "$RAW_PROJECT_NAME" | tr '[:upper:]' '[:lower:]')

# Doe hetzelfde voor de APP_ID
APP_ID=$(echo "${KLANT}_${PROJECT_NAME}" | tr '[:upper:]' '[:lower:]')

echo "--- Start Automatisatie voor Klant: $KLANT ---"
echo "Project: $PROJECT_NAME (ID: $APP_ID)"

# 1. Project ophalen
LOCAL_PATH=$(./scripts/ingest_app.sh git "$GITHUB_URL" "$KLANT" | tail -n 1)

if [ ! -d "$LOCAL_PATH" ]; then
    echo "ERROR: Ingest mislukt."
    exit 1
fi

# 2. Vertaal naar API pad
API_PATH="/app/clients/$KLANT/$PROJECT_NAME/source"

# --- 3. API Aanspreken ---
echo "[2/4] API configureren..."
RESPONSE=$(curl -s -X POST "$API_URL" \
     -H "Content-Type: application/json" \
     -d "{\"app_id\": \"$APP_ID\", \"source_path\": \"$API_PATH\", \"user_id\": $USER_ID}")

# 4. Docker-compose opstarten
# Gebruik nu de PROJECT_NAME variabele voor het juiste pad
DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)/clients/$KLANT/$PROJECT_NAME/deployment"

echo "[3/4] Opstarten in $DEPLOY_DIR..."
if [ -d "$DEPLOY_DIR" ]; then
    cd "$DEPLOY_DIR" && docker-compose -p "$APP_ID" up -d
    # ... rest van je script ...
else
    echo "ERROR: Deployment map $DEPLOY_DIR bestaat niet."
    exit 1
fi