
This README represents the current global view of the system.

To keep it accurate for everyone, please document any workflow changes here, including new endpoints, services, functions, or significant functional changes.

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

The platform-api gets Docker socket access and mounts ./deployments and ./staging into the container.

- the API container can write generated compose files into `/app/deployments`
- platform-db listens on host port 5433

**2. Step 1: Ingest**

The ingest module is scripts/ingest_app.sh. What it does:
- takes: local <path> or git <url>
- copies/clones into: `/staging/<appName>_<timestamp>`
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
- stores metadata in the platform db with container_id="pending"

**5. Step 4: Persist deployment metadata**

Persistance is in services/storage.py

What is does:

- connects to PostgresQL using values from config.py (PLATFORM_DB_*)
- creates a provisions table if missing
- upserts by app_id 

**6. The API layer**

- endpoints:
  - POST /deploy/full-stack: calls *generate_full_deployment(app_id, source_path) and returns compose + ports
  - POST /detect/only: calls detector directly

**7. Overview functions per service/**

This directory contains the core services responsible for application analysis,
database provisioning, deployment orchestration, and state storage.

High-level flow:

*Analysis → Provisioning → Deployment → Storage*

---

<u>services/app_detector.py</u>

This module is the **analysis step**: it scans a source folder and returns a
structured detection result used by the deployer.


| Function | Description |
|--------|------------|
| `detect_application_type(source_path: str) -> Dict` | Validates input, calls `_analyze_directory()`, ensures output has expected containers: `{web, api, db}`, logs. |
| `_analyze_directory(directory: str) -> Dict` | Core scanner: walks directory, collects "evidence" files/extensions, builds a results dict. |
| `_detect_nodejs_frameworks(files: List[str], results: Dict) -> None` | Detects common Node frameworks (based on markers like dependencies/config patterns) and adds those to detected frameworks. |
| `_detect_python_frameworks(files: List[str], results: Dict) -> None` | Same idea as above but for Python. |
| `_detect_databases(app_type: str, directory: str, results: Dict) -> None` | Same idea as above but for database — populates `detected_databases` and `containers['db']` with recommended DB images. |
| `_get_runtime_image(app_type: str, runtime: str) -> str` | Returns Docker image for runtime when relevant. |
| `_get_web_server_image(web_server: str) -> str` | Returns Docker image for web server layer. |
| `_get_database_image(db_type: str) -> str` | Maps database types to images. |

---

<u>services/db_provisioning.py</u>

This module provides helpers for generating credentials and finding unused ports.
Deployer imports helpers rather than calling `provision_database`.


| Function | Description |
|--------|------------|
| `_generate_random_string(length=16) -> str` | Generates random string used for passwords/secrets. Deployer uses this to create DB passwords. |
| `_find_free_port(start=PORT_RANGE_START, end=PORT_RANGE_END) -> int` | Scans localhost ports and returns first available one. Deployer uses this for choosing external host ports. |
| `_provision_database(app_id: str) -> Dict` | Generator returning `db_name`, `db_user`, `db_pass`, `db_port`. In current code path deployer uses two private helpers instead. |

---

<u>services/deployer.py</u>

This module is the **orchestration layer**: takes detection output and provisioning
helpers and produces a docker-compose definition, writes it to disk, and stores metadata.
Called by `/deploy/full-stack`.


| Function | Description |
|--------|------------|
| `generate_full_deployment(app_id: str, source_path: str) -> (compose_dict, web_port, db_port)` | "Blueprint generator": detects app, decides whether to add DB and web services, assigns free ports, injects env variables, writes `/app/deployments/<app_id>/docker-compose.yml`, and persists a provision record. |
| `_prepare_db_config(app_id: str, db_type: str, db_image: str) -> Dict` | Builds DB service config: generates credentials, chooses external port, decides internal port, produces docker-compose fields and storage_data. Sits between detection ("we need a DB") and compose generation ("here is the DB service definition"). |
| `_write_compose_file(app_id: str, compose_dict: Dict) -> str` | Writes generated compose dict as YAML to `/app/deployments/<app_id>/docker-compose.yml`. |

---

<u>services/storage.py</u>

This module is the **platform state store**: persists provisioning records to the
platform database so the system can track what was generated for which `app_id`.


| Function | Description |
|--------|------------|
| `save_provision_record(app_id, db_name, db_user, db_password, db_port, container_id) -> None` | Connects to platform PostgreSQL using values from `config.py`, creates `provisions` table if missing, and upserts a record keyed by `app_id`. |










