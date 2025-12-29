#!/bin/bash

# --- CONFIGURATIE ---
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_ROOT="$BASE_DIR/clients"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# --- HOOFDPROGRAMMA ---

# Gebruik: ./ingest_app.sh <local|git> <bron> <klantnaam>
if [ "$#" -lt 3 ]; then
    echo "Gebruik: $0 <local|git> <bron_pad_of_url> <klantnaam>"
    exit 1
fi

SOURCE_TYPE=$1
SOURCE_LOCATION=$2
KLANT=$3

# 1. Projectnaam bepalen
# Voor Git: haalt naam uit URL. Voor Local: haalt naam uit de mapnaam.
PROJECT_NAME=$(basename "$SOURCE_LOCATION" .git)

# 2. Doelmap bepalen (Multi-tenant structuur)
TARGET_DIR="$CLIENTS_ROOT/$KLANT/$PROJECT_NAME/source"

# Zorg dat de mappenstructuur bestaat
mkdir -p "$(dirname "$TARGET_DIR")"

log_message "Start inname proces voor Klant: $KLANT, Project: $PROJECT_NAME"

# 3. Inlezen op basis van type
case $SOURCE_TYPE in
    "local")
        log_message "Modus: Lokaal inlezen van $SOURCE_LOCATION"

        if [ ! -d "$SOURCE_LOCATION" ]; then
            log_message "ERROR: Lokale bronmap '$SOURCE_LOCATION' niet gevonden."
            exit 1
        fi

        # Maak de doeltarget leeg als die al bestond (overschrijven)
        rm -rf "$TARGET_DIR"
        mkdir -p "$TARGET_DIR"

        # Kopieer de bestanden
        cp -r "$SOURCE_LOCATION/." "$TARGET_DIR"

        if [ $? -eq 0 ]; then
            log_message "SUCCESS: Bestanden lokaal gekopieerd naar $TARGET_DIR"
        else
            log_message "ERROR: Kopiëren mislukt."
            exit 1
        fi
        ;;

    "git")
        log_message "Modus: Git clone/pull van $SOURCE_LOCATION"

        if [ -d "$TARGET_DIR/.git" ]; then
            log_message "Project bestaat al. Bezig met update (git pull)..."
            cd "$TARGET_DIR" && git pull origin main &> /dev/null
        else
            log_message "Nieuw project. Bezig met git clone..."
            git clone --depth 1 "$SOURCE_LOCATION" "$TARGET_DIR" &> /dev/null
        fi

        if [ $? -eq 0 ]; then
            log_message "SUCCESS: Git operatie voltooid."
        else
            log_message "ERROR: Git operatie mislukt."
            exit 1
        fi
        ;;

    *)
        log_message "ERROR: Ongeldig type. Gebruik 'local' of 'git'."
        exit 1
        ;;
esac

# 4. Output het pad voor het volgende script
echo "$TARGET_DIR"