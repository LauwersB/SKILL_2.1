# Platform System Documentation

This README serves as the global technical documentation for the platform. It details the scripts, API endpoints, and internal services that drive the application deployment pipeline.

## Table of Contents
1. Walkthrough
2. Shell Scripts
3. API Reference (main.py)
4. Configuration (config.py)
5. Services Overview
   * app_detector.py
   * apps.py
   * containers.py
   * db_init.py
   * db_provisioning.py
   * deployer.py
   * logs.py
   * storage.py
6. Terminal user interface (TUI)
7. TUIApplication Logic (Functions)

---

## 1. Walkthrough

### 1.1 De Start: Het Platform Aanzetten
Voordat er ook maar één app gedeployed kan worden, moet het platform zelf draaien.
* **Actie:** Je start de platform-api container en de platform-db (PostgreSQL).
* **Wat gebeurt er onder water?**
    * De API start op (main.py).
    * De lifespan functie activeert services/db_init.py.
    * Dit script checkt of de database tabellen (users, provisions) bestaan. Zo niet, maakt hij ze aan.
    * Het script checkt of de admin user bestaat. Zo niet, maakt hij deze aan met een gehasht wachtwoord.
* **Resultaat:** Het platform is "klaar voor ontvangst".

### 1.2 De Input: Een Project Aanleveren
Een gebruiker (of jij) wil een nieuwe website of app lanceren.
* **Actie:** Je voert het commando uit: `./scripts/start_project.sh "klant_a" "git_repo_url"`
* **Wat gebeurt er?**
    * Het script roept eerst ingest_app.sh aan.
    * Deze downloadt (git clone) of kopieert de broncode naar een gestandaardiseerde map: `/app/clients/klant_a/projectnaam/source`.
    * De rechten worden goed gezet (chmod 755) zodat de containers er straks bij kunnen.

### 1.3 De Analyse: Wat hebben we hier?
Nu de code op de schijf staat, moet het platform weten wat het is (PHP? Python? Node?).
* **Actie:** Het script stuurt een verzoek naar de API: `POST /deploy/full-stack`.
* **De intelligentie (services/app_detector.py):**
    * De API kijkt in de map.
    * Ziet hij een composer.json? -> "Dit is PHP."
    * Ziet hij requirements.txt? -> "Dit is Python."
    * Ziet hij in de code referenties naar mysql of pdo? -> "We hebben een Database nodig."

### 1.4 De Constructie: Het Bouwplan Maken
Nu het platform weet wat er nodig is, gaat de architect aan de slag.
* **De Architect (services/deployer.py):**
    * Het berekent welke poorten vrij zijn (via db_provisioning.py en de database historie).
    * Als er een database nodig is, genereert het een wachtwoord en gebruikersnaam.
    * Het genereert een docker-compose.yml bestand specifiek voor deze app.
    * Het schrijft dit bestand weg in `/app/clients/klant_a/projectnaam/deployment/`.
* **De Administratie (services/storage.py):**
    * Alle details (welke poort, welk wachtwoord, welke app-ID) worden opgeslagen in de provisions tabel in Postgres. Zo raken we nooit gegevens kwijt.

### 1.5 De Uitrol: De Motoren Starten
Alles staat klaar op papier (in de YAML files), nu moet het gaan draaien.
* **Actie:** Het start_project.sh script (dat nog steeds bezig is) krijgt een "OK" terug van de API.
* **De Uitvoering:**
    * Het script navigeert naar de deployment map.
    * Het voert uit: `docker-compose up -d --build`.
* **Resultaat:**
    * Docker downloadt de images (bijv. PHP-Apache en MySQL).
    * De containers starten op: `klant_a_project-app` en `klant_a_project-db`.
    * De app is nu bereikbaar via de browser op de toegewezen poort (bijv. `localhost:8081`).

### 1.7 Operationeel: Beheer & Monitoring
De app draait. Wat nu?
* **Status Checken:**
    * Jij roept `GET /apps` aan.
    * `services/apps.py` vraagt aan Docker: "Wie draait er allemaal?" en matcht dit met de database om te laten zien welke poorten bij welke app horen.
* **Logs Bekijken:**
    * Er gaat iets mis in de app. Je roept `GET /apps/{id}/logs` aan.
    * `services/logs.py` haalt de live output uit de container op zonder dat je in te hoeft loggen op de server.
* **Onderhoud:**
    * Wil je de app even pauzeren? -> `stop_container.sh`.
    * Wil je de app voorgoed verwijderen? -> `verwijder_project.sh` (dit ruimt zowel de Docker containers, de bestanden als de database records op).

---

## 2. Shell Scripts
Located in the `./scripts` directory, these scripts handle the physical manipulation of files and Docker states.

| Script | Description | Usage / Arguments |
| :--- | :--- | :--- |
| `start_project.sh` | Main Entry Point. Orchestrates the ingestion of an app, calls the API to generate the configuration, and starts the Docker Compose stack. | `./start_project.sh "<client_name>" "<github_repo_link>"` |
| `ingest_app.sh` | Internal Utility. Clones/Copies the source code to the target directory (/app/clients/...) and sets correct permissions (755). | Called automatically by start_project.sh. |
| `stop_container.sh` | Stops the Docker Compose stack for a specific project. Useful for maintenance or taking a site offline temporarily. | `bash ./stop_container.sh '<client_name>' '<project_name>'` |
| `verwijder_project.sh` | Destructive. Stops containers, removes Docker images/volumes, deletes the project database record, and wipes the physical project directory. | `bash ./verwijder_project.sh '<client_name>' '<project_name>'` |

---

## 3. API Reference (main.py)
The platform-api (FastAPI) acts as the bridge between the scripts, the database, and the Docker daemon.

* **POST /deploy/full-stack**
    * Purpose: Generates a full Docker deployment for an ingested application.
    * Input: app_id, source_path, user_id.
    * Action: Triggers detection, generates docker-compose.yml, provisions database credentials, and saves metadata.
* **POST /detect/only**
    * Purpose: Runs the analysis logic on a source folder without deploying.
    * Returns: JSON object with detected languages, frameworks, and required databases.
* **GET /apps**
    * Purpose: Lists all currently deployed applications.
    * Logic: Derives state from running Docker containers and combines it with metadata (like exposed ports).
* **GET /apps/{app_id}/logs**
    * Purpose: Fetches logs for a running container.
    * Params: tail (lines), since (time), service ("app" or "database").
* **GET /containers**
    * Purpose: Returns a high-level overview of all containers managed by the platform (uptime, CPU usage, health status).
* **GET /containers/{app_id}**
    * Purpose: Returns specific status and resource usage for a single application's containers (App & DB).
* **POST /users**
    * Purpose: creates a user in the user database
    * Action: Invokes the db_init.create_user_if_not_exists function
* **POST /deploy/start**
    * Purpose: Main Entry Point. Orchestrates the ingestion of an app, calls the API to generate the configuration, and starts the Docker Compose stack.
    * Action: Invokes the start_project.sh script to start a new project
* **POST /deploy/pauze**
    * Purpose: Stops the Docker Compose stack for a specific project. Useful for maintenance or taking a site offline temporarily.
    * Action: Invokes the stop_container.sh script to pauze a project
* **POST /deploy/verwijderen**
    * Purpose: Stops containers, removes Docker images/volumes, deletes the project database record, and wipes the physical project directory.
    * Action: Invokes the verwijder_project.sh script to delete a project

---

## 4. Configuration (config.py)
This module loads environment variables from the .env file and exposes them as Python variables for the rest of the application.
* **Database Config:** Loads PLATFORM_DB_HOST, USER, PASSWORD, NAME.
* **Admin Config:** Loads default PLATFORM_ADMIN_USERNAME and PASSWORD used for the initial bootstrap in db_init.

---

## 5. Services Overview
The `services/` directory contains the core logic modules.

### 5.1 app_detector.py
The analysis engine. It scans the source code to determine how to run it.
**What it detects:**
* php (composer.json or .php files)
* nodejs (package.json or .js files)
* python (requirements.txt or .py files)
* html (index.html or html files)
* db types via dependency keywords/drivers/config patterns (mysql, postgresql or influxdb)

The detector returns a dict that includes:
* app_type, confidence, detected_files, detected_databases, etc
* containers: {web: [], api: [], db: [] }

| Function | Description |
| :--- | :--- |
| `detect_application_type(source_path: str) -> Dict` | Validates input, calls _analyze_directory(), ensures output has expected containers: {web, api, db}, logs. |
| `_analyze_directory(directory: str) -> Dict` | Core scanner: walks directory, collects "evidence" files/extensions, builds a results dict. |
| `_detect_nodejs_frameworks(files: List[str], results: Dict) -> None` | Detects common Node frameworks (based on markers like dependencies/config patterns) and adds those to detected frameworks. |
| `_detect_python_frameworks(files: List[str], results: Dict) -> None` | Same idea as above but for Python. |
| `_detect_databases(app_type: str, directory: str, results: Dict) -> None` | Same idea as above but for database — populates detected_databases and containers['db'] with recommended DB images. |
| `_get_runtime_image(app_type: str, runtime: str) -> str` | Returns Docker image for runtime when relevant. |
| `_get_web_server_image(web_server: str) -> str` | Returns Docker image for web server layer. |
| `_get_database_image(db_type: str) -> str` | Maps database types to images. |

### 5.2 apps.py
Provides runtime introspection of deployed applications.
* **List running apps:** `curl http://localhost:8080/apps`
* This module provides runtime introspection of deployed applications. It derives state from running containers and combines it with stored platform metadata.

| Function | Description |
| :--- | :--- |
| `list_running_apps() -> List[Dict]` | Lists running applications by inspecting container names (<app_id>-app, <app_id>-db). Returns which services are running, the externally exposed application port. |
| `_get_web_ports() -> Dict[str, int]` | Best-effort helper that reads application ports from the platform database (provisions.web_port). Never raises errors to keep debugging endpoints stable. |

### 5.3 containers.py
Provides low-level container status and metrics (similar to docker stats).
The platform integrates Docker health checks to provide accurate runtime status.
* **Health states:**
    * healthy -> health check succeeded
    * unhealthy -> health check failed
    * none -> no health check defined

Health is independent of container state. A container can be running but still unhealthy.
**Implemented checks:**
* Database containers:
    * MySQL: 'mysqladmin ping'
    * PostgreSQL: 'ping_isready'
* Application containers:
    * HTTP availability check on Apache ('curl http://127.0.0.1/')

| Function | Description |
| :--- | :--- |
| `list_containers(all_containers: bool = True) -> List[Dict[str, object]]` | Lists containers with name/image/state/status/created_at and enriches with started_at, restart_count, health, plus basic CPU/memory stats. |
| `get_container_stats() -> dict` | Reads CPU% and memory usage per container using docker stats --no-stream. |

### 5.4 db_init.py
Initialization & Migration. Runs automatically when the API starts.

| Function | Description |
| :--- | :--- |
| `init_platform_db()` | Connects to the platform PostgreSQL instance (with retry logic). Creates the users and provisions tables if they do not exist. |
| `create_user_if_not_exists(...)` | Seeds the database with the default admin user using bcrypt password hashing, can be used to create new users |

### 5.5 db_provisioning.py
Helpers for database credentials and port management.
This module provides helpers for generating credentials and finding unused ports. Deployer imports helpers rather than calling provision_database.

| Function | Description |
| :--- | :--- |
| `_generate_random_string(length=16) -> str` | Generates random string used for passwords/secrets. Deployer uses this to create DB passwords. |
| `_find_free_port(start=PORT_RANGE_START, end=PORT_RANGE_END) -> int` | Scans localhost ports and returns first available one. Deployer uses this for choosing external host ports. |
| `_provision_database(app_id: str) -> Dict` | Generator returning db_name, db_user, db_pass, db_port. In current code path deployer uses two private helpers instead. |

### 5.6 deployer.py
The orchestration layer. It ties detection and provisioning together to create the deployment artifacts.

| Function                                                                                       | Description                                                                                                                                                                                                                                           |
|:-----------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `generate_full_deployment(app_id: str, source_path: str) -> (compose_dict, web_port, db_port)` | "Blueprint generator": detects app, decides whether to add DB and web services, assigns free ports, injects env variables, writes /app/deployments/<app_id>/docker-compose.yml, and persists a provision record.                                      |
| `_prepare_db_config(app_id: str, db_type: str, db_image: str) -> Dict`                         | Builds DB service config: generates credentials, chooses external port, decides internal port, produces docker-compose fields and storage_data. Sits between detection ("we need a DB") and compose generation ("here is the DB service definition"). |
| `_write_compose_file(app_id: str, compose_dict: Dict) -> str`                                  | Writes generated compose dict as YAML to /app/deployments/<app_id>/docker-compose.yml.                                                                                                                                                                |
| `_write_app_dockerfile(app_id: str)`                                                           | Writes generated Dockerfile with msqli PHP-requirements to /app/deployments/<app_id>/Dockerfile.app.                                                                                                                                                  |
| `_write_python_dockerfile(app_id: str)`                                                        | Writes generated Dockerfile with Python-requirements to /app/deployments/<app_id>/Dockerfile.app.                                                                                                                                                     |

### 5.7 logs.py
This module provides read-only log access for running containers. It hides Docker-specific commands behind a small helper so the API layer remains portable (e.g. Kubernetes later).

| Function | Description |
| :--- | :--- |
| `get_container_logs(app_id, service="app", tail=200, since=None, query=None) -> str` | Fetches logs from a running container (<app_id>-app or <app_id>-db) using Docker. Supports tailing, time filtering, and simple text search. Raises clear errors if containers are missing. |

### 5.8 storage.py
The Persistence Layer. Handles CRUD operations for the platform database.
This module is the platform state store: persists provisioning records to the platform database so the system can track what was generated for which app_id.

| Function | Description |
| :--- | :--- |
| `save_provision_record(app_id, db_name, db_user, db_password, db_port, container_id) -> None` | Connects to platform PostgreSQL using values from config.py, creates provisions table if missing, and upserts a record keyed by app_id. |

---

## 6. The Terminal User Interface (TUI)
The platform includes a Textual-based TUI that provides a visual dashboard for managing clients, projects, and containers directly from the terminal.
**How the TUI works:**
* **Authentication:** The app starts with a login screen that verifies credentials against the users table in the platform database (using bcrypt).
* **Role-based UI:**
    * Admins see a client management section where they can create new users and switch between different client project views.
    * Users are taken directly to their own project overview.
* **Reactive UI:** The interface is built with reactive components. Selecting a project in the DataTable automatically triggers API calls to fetch live container stats.
* **Asynchronous Workers:** Heavy tasks (like deploying a project or fetching logs) are run as @work threads. This prevents the terminal UI from "freezing" while waiting for the server/Docker response.

---

## 7. TUI Application Logic (Functions)
The TuiApp class contains several key functions that orchestrate the interaction between the user and the Platform API.

| Function | Description |
| :--- | :--- |
| `check_login()` | Connects to the platform database to verify the username and compare the hashed password. Sets the current_user context. |
| `load_clients()` | (Admin only) Queries the database for all registered users and populates the client management table. |
| `load_projects(user_id, client_name)` | Fetches all deployment records for a specific user from the provisions table. |
| `load_containers(app_id)` | API Call. Fetches live status (CPU, RAM, Health) for the specific Docker stack of the selected project. |
| `action_deploy_project()` | API Call. Sends a POST request to /deploy/start with a GitHub URL. Displays a LoadingIndicator until the deployment is confirmed. |
| `action_pause_project()` | API Call. Sends a request to the API to temporarily stop the project containers without deleting them. |
| `action_delete_project()` | API Call. Triggers the full removal of a project (containers, files, and database records). |
| `action_fetch_logs()` | API Call. Retrieves the last 100 log lines of a project and displays them in a dedicated LogScreen modal. |
| `action_create_user()` | Allows admins to add new users to the platform database via the API. |