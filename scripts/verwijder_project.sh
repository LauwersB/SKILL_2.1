#!/bin/bash

cd "$(dirname "$0")/.."

# 1. Variabelen ophalen
KLANTNAAM=$1
PROJECTNAAM=$2
STACK_NAAM="${KLANTNAAM}_${PROJECTNAAM}"
PROJECT_PAD="$(pwd)/clients/${KLANTNAAM}/${PROJECTNAAM}"

# Controle of argumenten aanwezig zijn
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Fout: Gebruik $0 <klantnaam> <projectnaam>"
    exit 1
fi

echo "--- START CLEANUP VOOR PROJECT: $STACK_NAAM ---"

# 2. Docker resources verwijderen
# 'down' stopt containers en verwijdert ze + het netwerk.
# --rmi all verwijdert ook alle gebruikte images van dit project.
# --volumes verwijdert ook de gekoppelde volumes (data).
echo "Stap 1: Docker containers en images verwijderen..."
docker compose -p "$STACK_NAAM" down --rmi all --volumes > /dev/null 2>&1

# Verificatie of Docker stack weg is
RUNNING_COUNT=$(docker compose -p "$STACK_NAAM" ps -q | wc -l)

if [ "$RUNNING_COUNT" -eq 0 ]; then
    echo "Succes: Docker resources voor $STACK_NAAM zijn opgeruimd."
else
    echo "Fout: Docker kon niet alle resources van $STACK_NAAM verwijderen."
    exit 1
fi

# 3. Database record verwijderen uit de platform database
echo "Stap 2: Record verwijderen uit platform database (app_id: $APP_ID)..."

# We voeren het SQL commando direct uit via de platform-db container
docker exec skill_21-platform-db-1 psql -U platform -d platform -c "DELETE FROM provisions WHERE app_id = '$STACK_NAAM';" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "Succes: Record verwijderd uit de database."
else
    echo "Fout: Kon record niet verwijderen uit de database (is de platform-db container online?)"
fi

# 4. Projectmap verwijderen
echo "Stap 3: Bestanden verwijderen in $PROJECT_PAD..."

if [ -d "$PROJECT_PAD" ]; then
    # Forceer permissies op de map die we willen verwijderen
    chmod -R 777 "$PROJECT_PAD" 2>/dev/null

    # Verwijder de inhoud eerst, dan de map zelf
    find "$PROJECT_PAD" -mindepth 1 -delete 2>/dev/null
    rm -rf "$PROJECT_PAD"

    # Controleren of de map nu echt weg is
    if [ ! -d "$PROJECT_PAD" ]; then
        echo "Succes: Map $PROJECT_PAD is verwijderd."
    else
        echo "Fout: Kon de map $PROJECT_PAD niet verwijderen (check permissies)."
        exit 1
    fi
else
    echo "Waarschuwing: Map $PROJECT_PAD bestond al niet."
fi

echo "--- CLEANUP VOLTOOID ---"