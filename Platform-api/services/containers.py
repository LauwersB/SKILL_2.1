import subprocess
from datetime import datetime
from typing import List, Dict, Optional


class ContainerProviderError(RuntimeError):
    pass


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise ContainerProviderError("Docker CLI not found. Is Docker installed and on PATH?") from e


def list_containers(all_containers: bool = True) -> List[Dict[str, object]]:
    """
    Returns a lightweight overview of containers.

    Includes:
    - name, image
    - state/status (running/exited)
    - created_at (docker's CreatedAt)
    - started_at + restart_count (via docker inspect)
    - uptime (best-effort from docker ps Status field)
    """
    format_str = "{{.Names}}|{{.Image}}|{{.Status}}|{{.State}}|{{.CreatedAt}}"
    cmd = ["docker", "ps", "--format", format_str]
    if all_containers:
        cmd.insert(2, "-a")

    proc = _run(cmd)
    if proc.returncode != 0:
        msg = proc.stderr.strip() or "Could not run docker ps"
        raise ContainerProviderError(msg)

    rows = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    results: List[Dict[str, object]] = []

    # Enrich each container with inspect fields (StartedAt, RestartCount, Health)
    for row in rows:
        name, image, status, state, created_at = row.split("|", 4)

        inspect = _run([
            "docker", "inspect", name,
            "--format",
            "{{.State.StartedAt}}|{{.RestartCount}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
        ])

        started_at: Optional[str] = None
        restart_count: Optional[int] = None
        health: str = "none"

        if inspect.returncode == 0 and inspect.stdout.strip():
            parts = inspect.stdout.strip().split("|")
            if len(parts) >= 3:
                started_at = parts[0] or None
                try:
                    restart_count = int(parts[1])
                except Exception:
                    restart_count = None
                health = parts[2] or "none"

        results.append({
            "name": name,
            "image": image,
            "state": state,          # running / exited
            "status": status,        # includes uptime text like "Up 38 minutes"
            "created_at": created_at,
            "started_at": started_at,
            "restart_count": restart_count,
            "health": health
        })

    return results
