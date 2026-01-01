#!/bin/bash

# --- CONFIGURATIE ---
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_ROOT="$BASE_DIR/clients"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2  # >&2 stuurt logs naar stderr zodat ze niet in de variabele komen
}

# --- HOOFDPROGRAMMA ---

if [ "$#" -lt 3 ]; then
    echo "Gebruik: $0 <local|git> <bron_pad_of_url> <klantnaam>"
    exit 1
fi

SOURCE_TYPE=$1
SOURCE_LOCATION=$2
KLANT=$3

# 1. Projectnaam bepalen
PROJECT_NAME=$(basename "$SOURCE_LOCATION" .git)

# 2. Doelmap bepalen
# PROJECT_ROOT is bijv: .../clients/bla/crud-php-mysql-simple
PROJECT_ROOT="$CLIENTS_ROOT/$KLANT/$PROJECT_NAME"
TARGET_DIR="$PROJECT_ROOT/source"

# FIX: Maak de hele boomstructuur aan in één keer
# Als de map al bestaat maar een raar bestand is, verwijder het dan eerst
if [ -e "$PROJECT_ROOT" ] && [ ! -d "$PROJECT_ROOT" ]; then
    rm -f "$PROJECT_ROOT"
fi

mkdir -p "$TARGET_DIR"

# 3. Inlezen
case $SOURCE_TYPE in
    "local")
        if [ ! -d "$SOURCE_LOCATION" ]; then
            log_message "ERROR: Lokale map niet gevonden."
            exit 1
        fi
        rm -rf "$TARGET_DIR"
        mkdir -p "$TARGET_DIR"
        cp -r "$SOURCE_LOCATION/." "$TARGET_DIR"
        ;;
    "git")
        if [ -d "$TARGET_DIR/.git" ]; then
            cd "$TARGET_DIR" && git pull origin main &> /dev/null
        else
            git clone --depth 1 "$SOURCE_LOCATION" "$TARGET_DIR" &> /dev/null
        fi
        ;;
    *)
        log_message "ERROR: Type moet 'local' of 'git' zijn."
        exit 1
        ;;
esac

# 4. CRUCIAAL: Print ALLEEN het pad naar stdout
echo "$TARGET_DIR"