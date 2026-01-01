## Helper used for logs and debugging endpoint @app.get("/apps/{app_id}/logs"
## Key idea: hide Docker specifics in tiny helper so we can swap it for Kubernetes later.

import subprocess
from typing import Optional

class LogProviderError(RuntimeError):
    pass

def get_container_logs(
        app_id: str,
        service: str = "app",
        tail: int = 200,
        since: Optional[str] = None,
        query: Optional[str] = None,
) -> str:
    """
    Fetch logs for a deployed app/service.

    service: "app", "database"
    since: docker-compatible duration string like "10m", 1h" (optional)
    query: simple substring filter (optional)
    """

    if service not in ("app", "database"):
        raise ValueError("service must be 'app' or 'database'")

    container_name = f"{app_id}-app" if service == "app" else f"{app_id}-db"

    cmd = ["docker", "logs", "--tail", str(tail)]
    if since:
        cmd += ["--since", since]
    cmd.append(container_name)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise LogProviderError("Docker CLI not found. Is Docker installed and on PATH?") from e

    # docker logs returns non-zero if container doesn't exist, etc.
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown docker logs error"
        raise LogProviderError(f"Could not read logs for {container_name}: {msg}")

    output = proc.stdout

    if query:
        q = query.lower()
        output = "\n".join(line for line in output.splitlines() if q in line.lower())

    return output