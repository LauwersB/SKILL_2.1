## Helper used for logs and debugging endpoint @app.get("/apps/{app_id}/logs"
## List running deployed apps

import psycopg2
import sys
import subprocess
from typing import List, Dict
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

def _get_web_ports():
    """
    Returns dict: app_id -> web_port
    """
    ports = {}
    try:
        conn = psycopg2.connect(
            host=config.db_host,
            user=config.username,
            password=config.password,
            dbname=config.db_name,
            connect_timeout=5
        )
        cur = conn.cursor()
        cur.execute("SELECT app_id, web_port FROM provisions")
        for app_id, web_port in cur.fetchall():
            ports[app_id] = web_port
        cur.close()
        conn.close()
    except Exception:
        pass  # non-fatal for debugging endpoint
    return ports

def list_running_apps() -> List[Dict[str, object]]:
    """
    Returns deployed apps detected from docker container names:
    <app_id>-app and <app_id>-db
    """
    cmd = ["docker", "ps", "--format", "{{.Names}}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        msg = proc.stderr.strip() or "Could not run docker ps"
        raise RuntimeError(msg)

    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    apps = {}  # app_id -> {app: bool, database: bool}
    for name in names:
        if name.endswith("-app"):
            app_id = name[:-4]
            apps.setdefault(app_id, {"app": False, "database": False})
            apps[app_id]["app"] = True
        elif name.endswith("-db"):
            app_id = name[:-3]
            apps.setdefault(app_id, {"app": False, "database": False})
            apps[app_id]["database"] = True

    ports = _get_web_ports()

    # make it stable & readable
    result = []
    for app_id in sorted(apps.keys()):
        # app_id format: "<client>_<project>" (split on first underscore only)
        if "_" in app_id:
            client, project = app_id.split("_", 1)
        else:
            client, project = None, app_id  # fallback: treat whole as project

        result.append({
            "app_id": {
                "full": app_id,
                "client": client,
                "project": project
            },
            "services": {
                "app": {
                    "running": apps[app_id].get("app", False),
                    "port": ports.get(app_id)
                },
                "database": {
                    "running": apps[app_id].get("database", False)
                }
            }
        })
    return result


