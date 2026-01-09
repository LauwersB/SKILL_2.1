import logging
import yaml
import os
from pathlib import Path
from typing import Dict, Tuple, Optional

from services.app_detector import detect_application_type
from services.storage import save_provision_record
from services.db_provisioning import _generate_random_string, _find_free_port

logger = logging.getLogger(__name__)

def _prepare_db_config(app_id: str, db_type: str, db_image: str) -> Dict:
    """Genereert technische details en credentials voor de database."""
    db_pass = _generate_random_string(24)
    db_name = f"db_{app_id.replace('-', '_')}"

    ## In Docker, containers with same compose stack communicate over an internal network using the service name as hostname (e.g. "database:3306").
    ## Selecting a free host port from inside a container is unreliable on Windows/WSL and caused deployment failures.

    ## ext_port = _find_free_port(9000)

    ## Bovenstaande code verwijderd door Maarten. Exposen van poorten in deze code moet verder bekeken worden door Bjorn.

    is_postgres = "postgres" in db_type
    internal_port = "5432" if is_postgres else "3306"

    if is_postgres:
        env = {"POSTGRES_PASSWORD": db_pass, "POSTGRES_USER": "admin", "POSTGRES_DB": db_name}
    else:
        env = {"MYSQL_ROOT_PASSWORD": db_pass, "MYSQL_DATABASE": db_name,
               "MYSQL_USER": "admin", "MYSQL_PASSWORD": db_pass}

    return {
        "service_name": "database",
        "image": db_image,
        "environment": env,
        ## "port_mapping": f"{ext_port}:{internal_port}",
        "storage_data": {
            "db_name": db_name, "db_user": "admin",
            "db_password": db_pass, "db_port": internal_port, "db_host": "database"
        }
    }

def _write_compose_file(app_id: str, compose_dict: Dict, source_path: str) -> str:
    """Schrijft de dict naar de deployment map binnen jouw client-structuur."""
    project_root = os.path.dirname(source_path)
    base_path = os.path.join(project_root, "deployment")
    os.makedirs(base_path, exist_ok=True)

    file_path = os.path.join(base_path, "docker-compose.yml")
    with open(file_path, 'w') as f:
        yaml.dump(compose_dict, f, default_flow_style=False)

    logger.info(f"Docker Compose bestand geschreven naar: {file_path}")
    return file_path

def _write_app_dockerfile(app_id: str, source_path: str):
    """Maakt een Dockerfile aan voor PHP apps (Maartens fix)."""
    project_root = os.path.dirname(source_path)
    deploy_path = os.path.join(project_root, "deployment")
    os.makedirs(deploy_path, exist_ok=True)

    dockerfile_path = os.path.join(deploy_path, "Dockerfile.app")
    content = (
        "FROM php:8.2-apache\n"
        "# Install curl (for healthcheck) + mysqli so mysqli_connect() works\n"
        "RUN apt-get update && apt-get install -y curl "
        "&& docker-php-ext-install mysqli "
        "&& rm -rf /var/lib/apt/lists/*\n"
    )
    with open(dockerfile_path, 'w', encoding="utf-8") as f:
        f.write(content)

def generate_full_deployment(app_id: str, source_path: str, user_id: int) -> Tuple[Optional[Dict], Optional[int], Optional[int]]:
    detection = detect_application_type(source_path)
    if "error" in detection:
        logger.error(f"Analyse mislukt voor {app_id}: {detection['error']}")
        return None, None, None

    services = {}
    db_info = None
    network_name = f"net_{app_id.replace('-', '_')}"

    # 1. Database Sectie (Inclusief Maartens .sql import fix)
    db_conts = detection.get('containers', {}).get('db', [])
    if db_conts:
        db_cfg = _prepare_db_config(app_id, db_conts[0]['type'], db_conts[0]['image'])

        db_service = {
            "container_name": f"{app_id}-db",
            "image": db_cfg["image"],
            "environment": db_cfg["environment"],
            ## "ports": [db_cfg["port_mapping"]],
            "networks": [network_name],
            "restart": "unless-stopped"
        }

        ## Minimal healthcheck so Docker reports healthy/unhealthy (instead of none)
        db_type = (db_conts[0].get("type") or "").lower()
        if "mysql" in db_type:
            db_service["healthcheck"] = {
                "test": ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 -uadmin -p$MYSQL_PASSWORD || exit 1"],
                "interval": "10s",
                "timeout": "5s",
                "retries": 10,
                "start_period": "20s",
            }
        elif "postgres" in db_type:
            db_service["healthcheck"] = {
                "test": ["CMD-SHELL", "pg_isready -U admin -d " + db_cfg["storage_data"]["db_name"] + " || exit 1"],
                "interval": "10s",
                "timeout": "5s",
                "retries": 5,
                "start_period": "10s",
            }

        if (Path(source_path) / "database.sql").exists():
            db_service["volumes"] = [
                "../source/database.sql:/docker-entrypoint-initdb.d/init.sql:ro"
            ]

        services[db_cfg["service_name"]] = db_service
        db_info = db_cfg["storage_data"]


    # 2. Web Sectie (Inclusief Maartens PHP/mysqli fix)
    web_conts = detection.get('containers', {}).get('web', [])
    web_port = _find_free_port(8081)

    if web_conts:
        is_php_app = detection.get("app_type") == "php"
        if is_php_app:
            _write_app_dockerfile(app_id, source_path)

        web_env = {}
        if db_info:
            web_env = {
                "DB_HOST": "database",
                "DB_PORT": str(db_info["db_port"]),
                "DB_NAME": db_info["db_name"],
                "DB_USER": db_info["db_user"],
                "DB_PASS": db_info["db_password"]
            }

        app_service = {
            "container_name": f"{app_id}-app",
            "ports": [f"{web_port}:80"],
            "volumes": ["../source:/var/www/html"],
            "environment": web_env,
            "networks": [network_name],
            "restart": "unless-stopped"
        }

        ## Minimal app healthcheck
        app_service["healthcheck"] = {
            "test": ["CMD-SHELL", "curl -sS -o /dev/null http://127.0.0.1/ || exit 1"],
            "interval": "10s",
            "timeout": "3s",
            "retries": 10,
            "start_period": "15s",
        }

        if is_php_app:
            app_service["build"] = {"context": ".", "dockerfile": "Dockerfile.app"}
        else:
            app_service["image"] = web_conts[0]["image"]

        services["app"] = app_service

    # 3. Finaliseer en Opslaan
    compose_dict = {
        "version": "3.8",
        "services": services,
        "networks": {network_name: {"driver": "bridge"}}
    }

    try:
        _write_compose_file(app_id, compose_dict, source_path)
    except Exception as e:
        logger.error(f"Kon compose bestand niet schrijven voor {app_id}: {e}")
        return None, None, None

    # 4. Administratie
    try:
        save_provision_record(
            app_id=app_id,
            db_name=db_info["db_name"] if db_info else None,
            db_user=db_info["db_user"] if db_info else None,
            db_password=db_info["db_password"] if db_info else None,
            db_port=db_info["db_port"] if db_info else 0,
            container_id="pending",
            web_port=web_port,
            user_id=user_id
        )
    except Exception as e:
        logger.critical(f"Administratie fout: {e}")
        return None, None, None

    return compose_dict, web_port, (db_info["db_port"] if db_info else None)