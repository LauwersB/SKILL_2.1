This README represents the current global view of the system.

To keep it accurate for everyone, please document any workflow changes here, including new endpoints, services,
functions, or significant functional changes.

**0 What we're building**

A pipeline that:

    1. ingests an app (local folder or Git repo)
    2. detects what it is and what it needs
    3. generates a per-app docker-compose.yml
    4. stores deployment metadata in a platform database
    5. (later) should also start/stop/validate deployments via API

**1. The "platform" runtime (Docker Compose at repo root)**

The root docker-compose.yml defines the platform itself:

- platform-api (FastAPI app)
- platform-db (PostgreSQL database)

The platform-api gets Docker socket access and mounts ./clients into the container.

- the API container can write generated compose files into `/app/clients/name_client/name_project/deployment`
- platform-db listens on host port 5433

**1.scripts

- The start_project script**

    - ./scripts/start_project.sh "<client_name>" "<github_repo_link>"
    - starts the ingest_app script
    - uses the api to generate a docker-compose file
    - starts the compose-stack
    - controle if containers has started and info is added to platform_db

- The stop container script**

    - bash .scripts/stop_container.sh 'klantnaam' 'projectnaam'
    - stopt de compose stack (alle containers) van het project (indien website tijdelijk offline moet)

- the verwijder project script**

    - bash .scripts/verwijder_project.sh 'klantnaam' 'projectnaam'
    - verwijderd alle containers, docker images en gekoppelde volumes
    - verifierd of stack weg is
    - verwijderd de record uit de platform_db
    - verwijderd de projectmap met alle bestanden
    - verifierd of alle bestanden weg zijn

**2. Step 1: Ingest**

The ingest module is scripts/ingest_app.sh. What it does:

- takes: local <path> or git <url>
- copies/clones into: `/app/clients/name_client/name_project/source/<appName>`
- sets permissions: chmod -R 755 <target_dir>
- prints the resulting path

**3. Step 2: Detect application type**

Detection lives in services/app_detector.py

What it detects:

- php (composer.json or .php files)
- nodejs (package.json or .js files)
- python (requirements.txt or .py files)
- html (index.html or html files)
- db types via dependency keywords/drivers/config patterns (mysql, postgresql or influxdb)

The detector returns a dict that includes:

- app_type, confidence, detected_files, detected_databases, etc
- containers: {web: [], api: [], db: [] }

**4. Step 3: Generate full docker-compose**

This happens in services/deployer.py via *generate_full_deployment(app_id, source_path)*.

What it does:

- calls the detector on source_path
- builds a per-app network name: net_<app_id>
- if a db container is detected, it:
    - picks a free web port (starting from 8081)
    - mounts the source folder into `/var/www/html`
    - injects db env vars if db exists (DB_HOST, DB_NAME etc.)
- writes compose to `app/deployments/<app_id>/docker-compose.yml`
- if PHP is detected, writes Dockerfile to `app/deployments/<app_id>/Dockerfile.app`
- stores metadata in the platform db with container_id="pending"

**5. Step 4: Persist deployment metadata**

Persistance is in services/storage.py

What is does:

- connects to PostgresQL using values from config.py (PLATFORM_DB_*)
- creates a provisions table if missing
- upserts by app_id

**6. The API layer**

- endpoints:
    - POST /deploy/full-stack  
      Generates a full docker-compose deployment for an app and stores metadata.
    - POST /detect/only  
      Runs application detection without generating a deployment.
    - GET /apps  
      Lists currently running deployed apps (derived from running containers).
    - GET /apps/{app_id}/logs  
      Fetches logs for a deployed app or database container (debugging).
    - GET /containers

      Shows an overview of containers (name/image/state/status/uptime-ish, started_at, restart_count, health if
      available) and basic resource usage (CPU%, memory).
    - GET /containers/{app_id}

      Returns container status and resource usage for a single application. Matches containers by name prefix:
      - `{app_id}-app`
      - `{app_id}-db`

**6.1 Debugging & Logs**

The platform exposes read-only endpoints to help developers debug running deployments
without executing into containers.

- List running apps:
  curl http://localhost:8080/apps

- Fetch application logs:
  curl "http://localhost:8080/apps/<app_id>/logs?tail=50"

- Fetch database logs:
  curl "http://localhost:8080/apps/<app_id>/logs?service=database&tail=50"

- Plain text output (recommended for terminals):
  curl "http://localhost:8080/apps/<app_id>/logs?format=raw"

Supported query parameters:

- tail: number of log lines (default: 200)
- since: Docker duration (e.g. 10m, 1h)
- q: simple text filter
- format: json | raw

**7. Overview functions per service/**

This directory contains the core services responsible for application analysis,
database provisioning, deployment orchestration, and state storage.

High-level flow:

*Analysis → Provisioning → Deployment → Storage*

---

<u>services/app_detector.py</u>

This module is the **analysis step**: it scans a source folder and returns a
structured detection result used by the deployer.

| Function                                                                  | Description                                                                                                                |
|---------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `detect_application_type(source_path: str) -> Dict`                       | Validates input, calls `_analyze_directory()`, ensures output has expected containers: `{web, api, db}`, logs.             |
| `_analyze_directory(directory: str) -> Dict`                              | Core scanner: walks directory, collects "evidence" files/extensions, builds a results dict.                                |
| `_detect_nodejs_frameworks(files: List[str], results: Dict) -> None`      | Detects common Node frameworks (based on markers like dependencies/config patterns) and adds those to detected frameworks. |
| `_detect_python_frameworks(files: List[str], results: Dict) -> None`      | Same idea as above but for Python.                                                                                         |
| `_detect_databases(app_type: str, directory: str, results: Dict) -> None` | Same idea as above but for database — populates `detected_databases` and `containers['db']` with recommended DB images.    |
| `_get_runtime_image(app_type: str, runtime: str) -> str`                  | Returns Docker image for runtime when relevant.                                                                            |
| `_get_web_server_image(web_server: str) -> str`                           | Returns Docker image for web server layer.                                                                                 |
| `_get_database_image(db_type: str) -> str`                                | Maps database types to images.                                                                                             |

---

<u>services/db_provisioning.py</u>

This module provides helpers for generating credentials and finding unused ports.
Deployer imports helpers rather than calling `provision_database`.

| Function                                                             | Description                                                                                                                     |
|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| `_generate_random_string(length=16) -> str`                          | Generates random string used for passwords/secrets. Deployer uses this to create DB passwords.                                  |
| `_find_free_port(start=PORT_RANGE_START, end=PORT_RANGE_END) -> int` | Scans localhost ports and returns first available one. Deployer uses this for choosing external host ports.                     |
| `_provision_database(app_id: str) -> Dict`                           | Generator returning `db_name`, `db_user`, `db_pass`, `db_port`. In current code path deployer uses two private helpers instead. |

---

<u>services/deployer.py</u>

This module is the **orchestration layer**: takes detection output and provisioning
helpers and produces a docker-compose definition, writes it to disk, and stores metadata.
Called by `/deploy/full-stack`.

| Function                                                                                       | Description                                                                                                                                                                                                                                           |
|------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `generate_full_deployment(app_id: str, source_path: str) -> (compose_dict, web_port, db_port)` | "Blueprint generator": detects app, decides whether to add DB and web services, assigns free ports, injects env variables, writes `/app/deployments/<app_id>/docker-compose.yml`, and persists a provision record.                                    |
| `_prepare_db_config(app_id: str, db_type: str, db_image: str) -> Dict`                         | Builds DB service config: generates credentials, chooses external port, decides internal port, produces docker-compose fields and storage_data. Sits between detection ("we need a DB") and compose generation ("here is the DB service definition"). |
| `_write_compose_file(app_id: str, compose_dict: Dict) -> str`                                  | Writes generated compose dict as YAML to `/app/deployments/<app_id>/docker-compose.yml`.                                                                                                                                                              |
| `_write_app_dockerfile(app_id: str)`                                                           | Writes generated Dockerfile with msqli PHP-requirements to `/app/deployments/<app_id>/Dockerfile.app`.                                                                                                                                                |

---

<u>services/storage.py</u>

This module is the **platform state store**: persists provisioning records to the
platform database so the system can track what was generated for which `app_id`.

| Function                                                                                      | Description                                                                                                                                   |
|-----------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| `save_provision_record(app_id, db_name, db_user, db_password, db_port, container_id) -> None` | Connects to platform PostgreSQL using values from `config.py`, creates `provisions` table if missing, and upserts a record keyed by `app_id`. |

<u>services/logs.py</u>

This module provides **read-only log access** for running containers.
It hides Docker-specific commands behind a small helper so the API layer
remains portable (e.g. Kubernetes later).

| Function                                                                             | Description                                                                                                                                                                                    |
|--------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `get_container_logs(app_id, service="app", tail=200, since=None, query=None) -> str` | Fetches logs from a running container (`<app_id>-app` or `<app_id>-db`) using Docker. Supports tailing, time filtering, and simple text search. Raises clear errors if containers are missing. |

Used by:

- `GET /apps/{app_id}/logs`

<u>services/apps.py</u>

This module provides **runtime introspection** of deployed applications.
It derives state from running containers and combines it with stored
platform metadata.

| Function                             | Description                                                                                                                                                            |
|--------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `list_running_apps() -> List[Dict]`  | Lists running applications by inspecting container names (`<app_id>-app`, `<app_id>-db`). Returns which services are running, the externally exposed application port. |
| `_get_web_ports() -> Dict[str, int]` | Best-effort helper that reads application ports from the platform database (`provisions.web_port`). Never raises errors to keep debugging endpoints stable.            |

Used by:

- `GET /apps`

---

<u>services/containers.py</u>

Provides container status overview for debugging (similar to `docker ps` + `docker inspect` + `docker stats`).

| Function                                                                  | Description                                                                                                                                |
|---------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `list_containers(all_containers: bool = True) -> List[Dict[str, object]]` | Lists containers with name/image/state/status/created_at and enriches with started_at, restart_count, health, plus basic CPU/memory stats. |
| `get_container_stats() -> dict`                                           | Reads CPU% and memory usage per container using `docker stats --no-stream`.                                                                |








