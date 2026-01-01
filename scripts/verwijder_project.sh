#!/bin/bash

# 1. Variabelen ophalen
KLANTNAAM=$1
PROJECTNAAM=$2
STACK_NAAM="${KLANTNAAM}_${PROJECTNAAM}"
PROJECT_PAD="./clients/${KLANTNAAM}/${PROJECTNAAM}"

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

# 3. Projectmap verwijderen
echo "Stap 2: Bestanden verwijderen in $PROJECT_PAD..."
if [ -d "$PROJECT_PAD" ]; then
    rm -rf "$PROJECT_PAD"

    # Controleren of de map echt weg is
    if [ ! -d "$PROJECT_PAD" ]; then
        echo "Succes: Map $PROJECT_PAD is verwijderd."
    else
        echo "Fout: Kon de map $PROJECT_PAD niet verwijderen (check permissies)."
    fi
else
    echo "Waarschuwing: Map $PROJECT_PAD bestond al niet."
fi

echo "--- CLEANUP VOLTOOID ---"