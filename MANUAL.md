## Wat is dit?

Deze manual legt stap-voor-stap uit **hoe het platform praktisch werkt**, hoe een applicatie automatisch gedeployed wordt, en hoe je **elke stap afzonderlijk** kan uitvoeren voor debug- of ontwikkeldoeleinden.


## TUI (user interface)

stappenplan: 
- clone platform vanuit github 
- .env file toevoegen aan root map
- ga naar root map en start platform (docker-compose up -d --build)
- bij opstart zal er een admin gebruiker aangemaakt worden met credentials uit .env
- tui opstarten met docker exec -it platform-tui python3 //app/app.py (hier moet later nog een ssh verbinding voor gemaakt worden)
- eerst gebruiker aanmaken. er kan geen project aangemaakt worden voor admin. admin kan wel een project starten voor een gebruiker

## Happy Path

bash ./scripts/start_project.sh test_client "https://github.com/maarten-wils/crud-php-mysql-simple.git"
bash ./scripts/start_project.sh test_client "https://github.com/maarten-wils/fastapi-postgres-docker-example"

endpoint post/deploy/start is gemaakt zodat docker dit script kan oproepen. deze endpoint kan je testen met:

curl -X 'POST'   'http://localhost:8080/deploy/start'   -H 'Content-Type: application/json'   -d '{
  "client_name": "test_client",
  "git_url": "https://github.com/maarten-wils/crud-php-mysql-simple.git"
}'

Dit script:

- haalt de applicatie op
- registreert ze bij het platform
- genereert database + poorten
- maakt een docker-compose stack
- start de applicatie

bash .scripts/stop_container.sh 'klantnaam' 'projectnaam'

endpoint post/deploy/pauze is gemaakt zodat docker dit script kan oproepen. deze endpoint kan je testen met:

curl -X 'POST'   'http://localhost:8080/deploy/pauze'   -H 'Content-Type: application/json'   -d '{
  "client_name": "test_client",
  "project_name": "crud-php-mysql-simple"
}'

- stopt de compose stack (alle containers) van het project (indien website tijdelijk offline moet)

bash .scripts/verwijder_project.sh 'klantnaam' 'projectnaam'

endpoint post/deploy/pauze is gemaakt zodat docker dit script kan oproepen. deze endpoint kan je testen met:

curl -X 'POST'   'http://localhost:8080/deploy/verwijderen'   -H 'Content-Type: application/json'   -d '{
  "client_name": "test_client",
  "project_name": "crud-php-mysql-simple"
}'

- verwijderd alle containers, docker images en gekoppelde volumes 
-  verifierd of stack weg is
- verwijderd de record uit de platform_db
- verwijderd de projectmap met alle bestanden
- verifierd of alle bestanden weg zijn

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

- Open http://localhost:<web port> (the port is returned by /deploy/full-stack)

_Debugging and verification_

- Use http://localhost:8080/apps to list running deployments
- Use /apps/{app_id}/logs to inspect container logs for debugging
- Use http://localhost:8080/containers to inspect all containers (status, uptime, restarts, health, resource usage)

_database nakijken_

docker exec -it skill_21-platform-db-1 psql -U platform -d platform

(-U en -d zijn db name en db user, kijk in .env of dit overeenkomt)

\dt om te kijken welke tabellen er zijn

SELECT * FROM users; -> data uit user tabel raadplegen
SELECT * FROM provisions; -> data uit project tabel raadplegen


