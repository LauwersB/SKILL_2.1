import random
import socket
import string
import docker
from .storage import save_provision_record

PASSWORD_LENGTH = 24
PORT_RANGE_START = 3000
PORT_RANGE_END = 9000

docker_client = docker.from_env()


def _generate_random_string(length=16):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _find_free_port(start=PORT_RANGE_START, end=PORT_RANGE_END):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            result = s.connect_ex(("127.0.0.1", port))
            if result != 0:
                return port
    raise RuntimeError("Geen vrije poort gevonden")


def provision_database(app_id: str):
    safe_app_id = "".join(c for c in app_id if c.isalnum() or c in ("-", "_")).lower()

    db_name = f"appdb_{safe_app_id}"
    db_user = f"user_{safe_app_id}"
    db_pass = _generate_random_string(PASSWORD_LENGTH)
    db_port = _find_free_port()

    # Start alleen de database container
    db_container = docker_client.containers.run(
        "postgres:16",
        name=f"db_{safe_app_id}",
        detach=True,
        environment={
            "POSTGRES_DB": db_name,
            "POSTGRES_USER": db_user,
            "POSTGRES_PASSWORD": db_pass,
        },
        ports={"5432/tcp": db_port},
        restart_policy={"Name": "unless-stopped"}
    )

    # Opslaan in platform database
    save_provision_record(
        app_id=app_id,
        db_name=db_name,
        db_user=db_user,
        db_password=db_pass,
        db_port=db_port,
        container_id=db_container.id
    )

    return {
        "status": "ok",
        "db_port": db_port,
        "container_id": db_container.id
    }

