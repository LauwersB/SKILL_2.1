import logging
import subprocess
import os
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import PlainTextResponse ## debugging and logs
from pydantic import BaseModel
from contextlib import asynccontextmanager
from services.app_detector import detect_application_type
from services.deployer import generate_full_deployment
from services.logs import get_container_logs, LogProviderError
from services.apps import list_running_apps
from services.containers import list_containers, ContainerProviderError
from services.db_init import init_platform_db, create_user_if_not_exists

# algemene logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alles hierboven gebeurt bij OPSTARTEN
    print("API start op, database controleren...")
    init_platform_db()
    yield
    # Alles hieronder gebeurt bij AFSLUITEN
    print("API sluit af...")

app = FastAPI(lifespan=lifespan)


# bij het aanroepen van de API moet er een projectnaam, path en user_id meegegeven worden
class DeployRequest(BaseModel):
    app_id: str
    source_path: str
    user_id: int


# Start van de deployment. als deze endpoint opgeroepen wordt zal de applicatie gescand worden,
# de nodige services en poorten worden toegekend en een docker-compose wordt op maat aangemaakt
@app.post("/deploy/full-stack")
def deploy_app(req: DeployRequest):
    # 1. Genereer de configuratie
    config_info = generate_full_deployment(req.app_id, req.source_path, req.user_id)

    # 2. Controleer of de functie überhaupt iets heeft teruggegeven
    if not config_info:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="De deployment configuratie kon niet worden gegenereerd."
        )

    compose_dict = config_info[0]
    web_port = config_info[1]
    db_port = config_info[2]

    # 3. Controleer of een van de specifieke waarden None is
    if compose_dict is None or web_port is None or db_port is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Deployment mislukt: Een of meerdere configuratiewaarden zijn leeg."
        )

    # 4. Als alles in orde is, stuur het succesbericht
    return {
        "message": "Deployment configuratie gegenereerd",
        "web_port": web_port,
        "db_port": db_port,
        "compose": compose_dict
    }

# endpoint om te testen of de applicatie juist gescand is
@app.post("/detect/only")
def detect_only(req: DeployRequest):
    return detect_application_type(source_path=req.source_path)

## Endpoint for logs and debugging

@app.get("/apps/{app_id}/logs")
def logs(
    app_id: str,
    service: str = "app",
    tail: int = 200,
    since: str | None = None,
    q: str | None = None,
    format: str = "json",
):
    try:
        output = get_container_logs(
            app_id=app_id,
            service=service,
            tail=tail,
            since=since,
            query=q,
        )

        if format == "raw":
            return PlainTextResponse(output)

        if format != "json":
            raise HTTPException(status_code=400, detail="format must be 'json' or 'raw'")

        return {
            "app_id": app_id,
            "service": service,
            "tail": tail,
            "since": since,
            "query": q,
            "lines": output.splitlines(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LogProviderError as e:
        raise HTTPException(status_code=404, detail=str(e))

## Endpoint that lists running apps

@app.get("/apps")
def apps():
    return {"apps": list_running_apps()}

## Endpoint that lists running containers

@app.get("/containers")
def containers(all: bool = True):
    try:
        return {"containers": list_containers(all_containers=all)}
    except ContainerProviderError as e:
        raise HTTPException(status_code=500, detail=str(e))


class UserRequest(BaseModel):
    username: str
    password: str
    role: str
    client_name: str


@app.post("/users", status_code=201)
async def add_user(req: UserRequest):
    import psycopg2
    import config

    conn = None
    try:
        # We openen hier een verbinding specifiek voor dit verzoek
        conn = psycopg2.connect(
            host=config.db_host,
            user=config.username,
            password=config.password,
            dbname=config.db_name
        )
        cur = conn.cursor()

        # Roep je functie aan uit db_init (die nu cur als argument verwacht)
        create_user_if_not_exists(cur, req.username, req.password, req.role, req.client_name)

        conn.commit()
        cur.close()
        return {"message": f"Gebruiker {req.username} succesvol aangemaakt"}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()
## Endpoint that lists running containers per app_id

@app.get("/containers/{app_id}")
def containers_for_app(app_id: str, all: bool = True):
    """
    Return the same structure as /containers, but filtered to one app_id.
    Matches container names:
      {app_id}-app
      {app_id}-db
    """
    try:
        containers = list_containers(all_containers=all)
        allowed = {f"{app_id}-app", f"{app_id}-db"}
        filtered = [c for c in containers if c.get("name") in allowed]
        return {"containers": filtered}
    except ContainerProviderError as e:
        raise HTTPException(status_code=500, detail=str(e))


class FrontendDeployRequest(BaseModel):
    client_name: str
    github_url: str


@app.post("/deploy/start")
def trigger_deployment_script(req: FrontendDeployRequest):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    script_path = os.path.join(project_root, "scripts", "start_project.sh")

    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail=f"Script niet gevonden op: {script_path}")

    try:
        # 1. Voer het script uit
        result = subprocess.run(
            [script_path, req.client_name, req.github_url],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )

        # 2. RECHTEN BINNEN DE CONTAINER FIXEN
        # De naam moet exact overeenkomen met je docker-compose container_name
        pure_project_name = req.github_url.split('/')[-1].replace('.git', '')
        container_name = f"{req.client_name}_{pure_project_name}-app"

        # Geef Docker de tijd om de container te starten
        import time
        time.sleep(3)

        try:
            # We voeren dit uit via de Docker CLI die in je API-container is geïnstalleerd
            subprocess.run(["docker", "exec", "-u", "root", container_name, "chmod", "-R", "755", "/var/www/html"], check=True)
            subprocess.run(["docker", "exec", "-u", "root", container_name, "chown", "-R", "www-data:www-data", "/var/www/html"], check=True)
            logging.info(f"✅ Rechten succesvol aangepast in container: {container_name}")
        except Exception as e:
            logging.error(f"⚠️ Kon rechten in container niet aanpassen: {e}")

        return {
            "message": "Deployment succesvol en permissies hersteld",
            "output": result.stdout
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Script execution failed: {e.stderr or e.stdout}")


# Model voor de pauze aanvraag
class PauseRequest(BaseModel):
    client_name: str
    project_name: str

@app.post("/deploy/pauze")
def pause_project(req: PauseRequest):
    """
    Dit endpoint stopt een draaiende stack zonder de containers te verwijderen.
    """
    # 1. Paden bepalen
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    # Zorg dat de naam van het script exact overeenkomt met je bestand in /scripts/
    script_path = os.path.join(project_root, "scripts", "stop_container.sh")

    # 2. Check of het script bestaat
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail=f"Pauze-script niet gevonden op: {script_path}"
        )

    try:
        # 3. Voer het script uit met de 2 argumenten
        # We zetten de CWD op project_root voor het geval het script relatieve paden gebruikt
        result = subprocess.run(
            [script_path, req.client_name, req.project_name],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )

        # 4. Succesvol resultaat teruggeven
        return {
            "message": f"Project {req.project_name} van klant {req.client_name} gepauzeerd.",
            "script_output": result.stdout
        }

    except subprocess.CalledProcessError as e:
        # Als het script een 'exit 1' geeft (bijv. als stoppen mislukt)
        print(f"Pauze Error: {e.stderr}")
        raise HTTPException(
            status_code=500,
            detail=f"Fout bij pauzeren van project: {e.stdout if e.stdout else e.stderr}"
        )


class DeleteRequest(BaseModel):
    client_name: str
    project_name: str

@app.post("/deploy/verwijderen")
def delete_project(req: DeleteRequest):
    """
    Dit endpoint verwijdert de volledige stack, inclusief images,
    database-records en fysieke bestanden.
    """
    # 1. Paden bepalen
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    script_path = os.path.join(project_root, "scripts", "verwijder_project.sh")

    # 2. Veiligheidscheck: voorkom dat vitale mappen worden verwijderd
    if not req.client_name or not req.project_name:
        raise HTTPException(
            status_code=400,
            detail="Klantnaam en projectnaam zijn verplicht voor verwijdering."
        )

    # 3. Check of het script bestaat
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail="Verwijder-script niet gevonden."
        )

    try:
        # 4. Voer het script uit
        # We geven klantnaam en projectnaam mee als argumenten
        result = subprocess.run(
            [script_path, req.client_name, req.project_name],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )

        return {
            "message": f"Project {req.project_name} succesvol volledig verwijderd.",
            "script_output": result.stdout
        }

    except subprocess.CalledProcessError as e:
        print(f"Delete Error: {e.stderr}")
        raise HTTPException(
            status_code=500,
            detail=f"Fout tijdens cleanup: {e.stdout if e.stdout else e.stderr}"
        )
