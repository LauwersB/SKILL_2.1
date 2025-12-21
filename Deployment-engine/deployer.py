import yaml
import os
import logging
from app_detector import detect_application_type  # Detectie van Yassine
from storage import save_provision_record  # Database opslag van yassine
from db_provisioning import _generate_random_string, _find_free_port, PASSWORD_LENGTH

# Configuratie
PASSWORD_LENGTH = 24
PORT_RANGE_START = 8081
PORT_RANGE_END = 9000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_full_deployment(app_id, source_path):
    """
    Voert de volledige workflow uit: poorten zoeken, detectie,
    wachtwoord genereren en opslaan.
    """
    # 1. Zoek vrije poorten
    web_port = _find_free_port(8081)
    db_external_port = _find_free_port(web_port + 1)

    # 2. Haal info op via de API/Detector
    detection_results = detect_application_type(source_path)
    if "error" in detection_results:
        return detection_results

    services = {}
    db_info_for_storage = None

    # 3. Verwerk Web Containers (Extern bereikbaar)
    for web_cont in detection_results.get('containers', {}).get('web', []):
        name = f"web_{web_cont['type']}"
        services[name] = {
            "image": web_cont['image'],
            "ports": [f"{web_port}:80"],
            "volumes": [f"{source_path}:/var/www/html"],
            "networks": ["extern", "intern"],
            "restart": "unless-stopped"
        }

    # 4. Verwerk Database & Sensordata connectie
    for db_cont in detection_results.get('containers', {}).get('db', []):
        db_type = db_cont['type']
        db_pass = _generate_random_string()
        db_user = "admin"
        db_name = f"data_{app_id.replace('-', '_')}"

        # Mapping voor verschillende DB types
        env = {}
        internal_port = ""
        if "postgres" in db_type:
            env = {"POSTGRES_PASSWORD": db_pass, "POSTGRES_USER": db_user, "POSTGRES_DB": db_name}
            internal_port = "5432"
        elif "mysql" in db_type or "mariadb" in db_type:
            env = {"MYSQL_ROOT_PASSWORD": db_pass, "MYSQL_DATABASE": db_name}
            internal_port = "3306"

        services["database"] = {
            "image": db_cont['image'],
            "environment": env,
            "ports": [f"{db_external_port}:{internal_port}"],  # Externe poort voor sensordata
            "networks": ["intern"],  # Intern voor de app, ports voor sensoren
            "restart": "unless-stopped"
        }

        # Voorbereiden voor opslag in platform database
        db_info_for_storage = {
            "app_id": app_id,
            "db_name": db_name,
            "db_user": db_user,
            "db_password": db_pass,
            "db_port": db_external_port
        }

    # 5. Netwerk definitie (Isolatie)
    compose_dict = {
        "version": "3.8",
        "services": services,
        "networks": {
            "extern": {"driver": "bridge"},
            "intern": {"driver": "bridge", "internal": True}
        }
    }

    # 6. Opslaan in Platform DB
    if db_info_for_storage:
        save_provision_record(
            app_id=db_info_for_storage["app_id"],
            db_name=db_info_for_storage["db_name"],
            db_user=db_info_for_storage["db_user"],
            db_password=db_info_for_storage["db_password"],
            db_port=db_info_for_storage["db_port"],
            container_id=f"deployed_{app_id}_db"
        )

    return compose_dict, web_port, db_external_port


# --- UITVOERING ---
if __name__ == "__main__":
    APP_ID = "sensor-project-01"
    PATH = "/tmp/poc-deployments/app_xyz"  # Waar de git files staan

    try:
        config, p_web, p_db = generate_full_deployment(APP_ID, PATH)

        # Schrijf docker-compose.yml naar de projectmap
        with open(os.path.join(PATH, "docker-compose.yml"), "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"✅ Klaar! Web: http://localhost:{p_web}")
        print(f"📡 Database (sensordata): localhost:{p_db}")
    except Exception as e:
        print(f"❌ Fout: {e}")