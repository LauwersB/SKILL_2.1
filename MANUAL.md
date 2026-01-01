## Wat is dit?

Deze manual legt stap-voor-stap uit **hoe het platform praktisch werkt**, hoe een applicatie automatisch gedeployed wordt, en hoe je **elke stap afzonderlijk** kan uitvoeren voor debug- of ontwikkeldoeleinden.


## Happy Path

bash ./scripts/start_project.sh klantnaam "https://github.com/maarten-wils/crud-php-mysql-simple.git"

Dit script:

- haalt de applicatie op
- registreert ze bij het platform
- genereert database + poorten
- maakt een docker-compose stack
- start de applicatie

👉 Gebruik dit als alles “gewoon moet werken”.

👉 Voorbeeld PHP + MySQL repo: https://github.com/maarten-wils/crud-php-mysql-simple.git

## Stap voor stap (debug, dev)

_Prereqs_

- Docker Desktop running
- Repo cloned
- .env exists with the platform db-credentials used by docker-compose.yml (platform-db is Postgres)

_Step A - Start het platform (API + platform-db)_

From repo root: docker compose up -d --build

Result:
- API reachable on http://localhost:8080
- platform-db reachable on http://localhost:5433

_Step B - Ingest the app into the shared clients folder_

bash ./scripts/ingest_app.sh git "`github url`" klantnaam

Result:
- App source code is cloned into the clients/klantnaam folder
- directory is created

_Step C - Call the API to generate the deployment_

curl -X POST http://localhost:8080/deploy/full-stack \
   -H "Content-Type: application/json" \
   -d '{
    "app_id": "klantnaam",
    "source_path": "/app/clients/klantnaam/projectnaam/source"
}'

Result:
- docker-compose file generated in `/app/clients/klantnaam/projectnaam/deployments`

_Step D - Start the generated stack_

- docker compose up -d in `/app/clients/klantnaam/projectnaam/deployments`

_Step E - Verify in browser_

Open http://localhost:<web port> (the port is returned by /deploy/full-stack)



