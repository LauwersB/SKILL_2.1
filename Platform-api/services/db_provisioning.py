import psycopg2
import logging
import sys
import socket
from pathlib import Path

# Zorg dat we config.py kunnen vinden
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger(__name__)

PASSWORD_LENGTH = 24
PORT_RANGE_START = 3000
PORT_RANGE_END = 9000

def _find_free_port(start_port=PORT_RANGE_START, end_port=PORT_RANGE_END):
    """
    Bepaalt de eerstvolgende vrije poort op basis van de database historie.
    """
    next_port = start_port
    conn = None

    try:
        # 1. Check de database voor de hoogst gebruikte poort
        conn = psycopg2.connect(
            host=config.db_host,
            user=config.username,
            password=config.password,
            dbname=config.db_name,
            connect_timeout=5
        )
        cur = conn.cursor()

        # Haal de allerhoogste web_port op die we ooit hebben uitgedeeld
        cur.execute("SELECT MAX(web_port) FROM provisions")
        row = cur.fetchone()

        if row and row[0] is not None:
            max_used_port = int(row[0])
            # Als de hoogste poort in de DB groter of gelijk is aan start_port,
            # pakken we er eentje hoger.
            if max_used_port >= start_port:
                next_port = max_used_port + 1

        cur.close()

    except Exception as e:
        logger.warning(f"Kon database niet checken voor poorten: {e}")
        pass  # Fallback naar socket check
    finally:
        if conn:
            conn.close()

    # 2. Dubbelcheck op het OS (voor de zekerheid)
    return _socket_check_fallback(next_port, end_port)


def _socket_check_fallback(start, end):
    """
    Probeert fysiek verbinding te maken met een poort.
    Als dat lukt, is de poort BEZET. Als het mislukt, is de poort VRIJ.
    """
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # We proberen de poort te 'binden'. Als dit lukt, is de poort echt vrij.
            try:
                s.bind(("0.0.0.0", port))
                return port # Succes! Poort is vrij en beschikbaar.
            except OSError:
                # OSError betekent dat de poort al in gebruik is.
                continue
    raise RuntimeError("Geen vrije poort gevonden in het opgegeven bereik.")


def _generate_random_string(length=16):
    import random
    import string
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def provision_database(app_id: str):
    """Genereer alleen de benodigde gegevens voor de database."""
    safe_app_id = "".join(c for c in app_id if c.isalnum() or c in ("-", "_")).lower()

    return {
        "db_name": f"appdb_{safe_app_id}",
        "db_user": f"user_{safe_app_id}",
        "db_pass": _generate_random_string(PASSWORD_LENGTH),
        "db_port": _find_free_port()
    }

