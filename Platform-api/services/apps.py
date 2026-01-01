## Helper used for logs and debugging endpoint @app.get("/apps/{app_id}/logs"
## List running deployed apps

import subprocess
from typing import List, Dict

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

    # make it stable & readable
    result = []
    for app_id in sorted(apps.keys()):
        result.append({"app_id": app_id, "services": apps[app_id]})
    return result
