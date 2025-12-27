import random
import socket
import string
import logging

logger = logging.getLogger(__name__)

PASSWORD_LENGTH = 24
PORT_RANGE_START = 3000
PORT_RANGE_END = 9000


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
    """Genereer alleen de benodigde gegevens voor de database."""
    safe_app_id = "".join(c for c in app_id if c.isalnum() or c in ("-", "_")).lower()

    return {
        "db_name": f"appdb_{safe_app_id}",
        "db_user": f"user_{safe_app_id}",
        "db_pass": _generate_random_string(PASSWORD_LENGTH),
        "db_port": _find_free_port()
    }
