#!/bin/bash

# 1. Controleren of er wel argumenten zijn meegegeven
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Fout: Gebruik de juiste schrijfwijze: $0 <klantnaam> <projectnaam>"
    exit 1
fi

# 2. Variabelen ophalen uit de input ($1 is de eerste, $2 de tweede)
KLANTNAAM=$1
PROJECTNAAM=$2

# 3. De stacknaam samenstellen
STACK_NAAM="${KLANTNAAM}_${PROJECTNAAM}"

echo "Bezig met het stoppen van stack: $STACK_NAAM..."

# 4. Het Docker commando uitvoeren
# De -p vlag vertelt Docker exact welke stack (project) gezocht moet worden
docker compose -p "$STACK_NAAM" stop

# 5. VERIFICATIE: Controleer of er nog containers draaien
# we zoeken naar containers met de status 'running' binnen dit project
RUNNING_COUNT=$(docker compose -p "$STACK_NAAM" ps --filter "status=running" -q | wc -l)

echo "-----------------------------------------------"

# 4. Logica op basis van de werkelijke status
if [ "$RUNNING_COUNT" -eq 0 ]; then
    echo "Succes: Alle containers van $STACK_NAAM zijn succesvol gestopt."
    # Toon de uiteindelijke status ter bevestiging
    docker compose -p "$STACK_NAAM" ps --format "table {{.Name}}\t{{.Status}}"
else
    echo "Fout: Er draaien nog $RUNNING_COUNT container(s) in stack $STACK_NAAM."
    echo "Controleer de output van 'docker ps' voor meer details."
fi

echo "-----------------------------------------------"