#!/bin/bash

# --- CONFIGURATIE ---
# Determine the staging directory relative to this script. This ensures script always uses the repo's staging folder, regardless of the current working directory or operating system.
STAGING_ROOT="$(cd "$(dirname "$0")/.." && pwd)/staging"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# --- FUNCTIES ---

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

cleanup_staging() {
    local folder=$1
    if [ -d "$folder" ]; then
        rm -rf "$folder"
        log_message "Oude staging map opgeruimd: $folder"
    fi
}

# --- HOOFDPROGRAMMA ---

# 1. Validatie van input
if [ "$#" -lt 2 ]; 
then
    echo "Gebruik: $0 <type: local|git> <bron_locatie>"
    exit 1
fi

SOURCE_TYPE=$1
SOURCE_LOCATION=$2

# Dynamische naamgeving: extraheer de naam uit de bronlocatie
# Bijv: /home/user/project-abc -> project-abc
# Bijv: https://github.com/user/web-app.git -> web-app
APP_NAME=$(basename "$SOURCE_LOCATION" .git)

TARGET_DIR="$STAGING_ROOT/${APP_NAME}_$TIMESTAMP"

# Zorg dat de staging root bestaat 
mkdir -p "$STAGING_ROOT"

log_message "Start inname proces (Type: $SOURCE_TYPE, Bron: $SOURCE_LOCATION)..."

# 2. Inlezen van bestanden 
case $SOURCE_TYPE in
    "local")
        # Validatie: Bestaat de bronmap? 
        if [ ! -d "$SOURCE_LOCATION" ]; then
            log_message "ERROR: Lokale bronmap '$SOURCE_LOCATION' niet gevonden." 
            exit 1
        fi
        
        cp -r "$SOURCE_LOCATION/." "$TARGET_DIR"
        ;;
        
    "git")
        # Inlezen via Git URL 
        log_message "Clonen van repository..."
        git clone --depth 1 "$SOURCE_LOCATION" "$TARGET_DIR" &> /dev/null
        
        # Error handling bij niet-bereikbare bron 
        if [ $? -ne 0 ]; then
            log_message "ERROR: Git clone mislukt. Controleer de URL of verbinding." 
            exit 1
        fi
        ;;
        
    *)
        log_message "ERROR: Ongeldig bron-type opgegeven. Gebruik 'local' of 'git'."
        exit 1
        ;;
esac

# 3. Validatie van resultaat 
if [ -d "$TARGET_DIR" ] && [ "$(ls -A "$TARGET_DIR")" ]; then
    log_message "SUCCESS: Applicatiebestanden succesvol ingelezen in $TARGET_DIR" 
    # Systeem valideert toegankelijkheid 
    chmod -R 755 "$TARGET_DIR" 
else
    log_message "ERROR: Staging map is leeg of niet aangemaakt." 
    exit 1
fi

echo "$TARGET_DIR" # Output voor de volgende module (POC-ANA-02)