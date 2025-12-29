import logging
import yaml
import os
from typing import Dict, Tuple, Optional

from services.app_detector import detect_application_type
from services.storage import save_provision_record
from services.db_provisioning import _generate_random_string, _find_free_port

logger = logging.getLogger(__name__)


def _prepare_db_config(app_id: str, db_type: str, db_image: str) -> Dict:
    """Genereert technische details en credentials voor de database."""
    db_pass = _generate_random_string(24)
    db_name = f"db_{app_id.replace('-', '_')}"
    ext_port = _find_free_port(9000)

    # Bepaal poort en env op basis van type
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
        "port_mapping": f"{ext_port}:{internal_port}",
        "storage_data": {
            "db_name": db_name, "db_user": "admin",
            "db_password": db_pass, "db_port": ext_port
        }
    }


def _write_compose_file(app_id: str, compose_dict: Dict, source_path: str) -> str:
    """Schrijft de dict naar een fysieke docker-compose.yml file in de client-structuur."""

    # 1. Navigeer van .../source naar de bovenliggende projectmap
    project_root = os.path.dirname(source_path)

    # 2. Bepaal het pad naar de 'deployment' map (naast de 'source' map)
    base_path = os.path.join(project_root, "deployment")

    # 3. Maak de map aan als deze nog niet bestaat
    os.makedirs(base_path, exist_ok=True)

    file_path = os.path.join(base_path, "docker-compose.yml")

    with open(file_path, 'w') as f:
        yaml.dump(compose_dict, f, default_flow_style=False)

    logger.info(f"Docker Compose bestand geschreven naar: {file_path}")
    return file_path


def generate_full_deployment(app_id: str, source_path: str) -> Tuple[Optional[Dict], Optional[int], Optional[int]]:
    """
    Coördineert de volledige deployment blueprint creatie.
    """
    # 1. Analyse (roept functie op om APP_DETECTOR te starten)
    detection = detect_application_type(source_path)
    if "error" in detection:
        logger.error(f"Analyse mislukt voor {app_id}: {detection['error']}")
        return None, None, None

    services = {}
    db_info = None
    network_name = f"net_{app_id.replace('-', '_')}"

    # 2. Database Sectie
    db_conts = detection.get('containers', {}).get('db', [])
    if db_conts:
        # We pakken de eerste gedetecteerde DB
        db_cfg = _prepare_db_config(app_id, db_conts[0]['type'], db_conts[0]['image'])

        services[db_cfg["service_name"]] = {
            "container_name": f"{app_id}-db",
            "image": db_cfg["image"],
            "environment": db_cfg["environment"],
            "ports": [db_cfg["port_mapping"]],
            "networks": [network_name],
            "restart": "unless-stopped"
        }
        db_info = db_cfg["storage_data"]

    # 3. Web Sectie
    web_conts = detection.get('containers', {}).get('web', [])
    web_port = _find_free_port(8081)

    if web_conts:
        web_env = {}
        if db_info:
            web_env = {
                "DB_HOST": "database",
                "DB_NAME": db_info["db_name"],
                "DB_USER": db_info["db_user"],
                "DB_PASS": db_info["db_password"]
            }

        services["app"] = {
            "container_name": f"{app_id}-app",
            "image": web_conts[0]['image'],
            "ports": [f"{web_port}:80"],
            "volumes": [f"{source_path}:/var/www/html"],
            "environment": web_env,
            "networks": [network_name],
            "restart": "unless-stopped"
        }

    # 4. Finaliseer Compose
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

    # 5. Administratie (alle projectinfo (app_id, container_id, db_name, db_user, db_password, db_port) wordt opgeslagen in DB van platform)
    try:
        # We halen de waarden uit db_info als die bestaat, anders None/0
        save_provision_record(
            app_id=app_id,
            db_name=db_info["db_name"] if db_info else None,
            db_user=db_info["db_user"] if db_info else None,
            db_password=db_info["db_password"] if db_info else None,
            db_port=db_info["db_port"] if db_info else 0,
            container_id="pending"
        )
        logger.info(f"Administratie voor {app_id} succesvol verwerkt.")

    except Exception as e:
        # NOODSCENARIO: Als de database-opslag mislukt, stoppen we de deployment
        logger.critical(f"FATALE FOUT: Kon administratie niet opslaan voor {app_id}: {e}")
        return None, None, None

        # Alles is gelukt, geef de data terug aan main.py
    return compose_dict, web_port, (db_info["db_port"] if db_info else None)
