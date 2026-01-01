import logging
from fastapi import FastAPI, HTTPException, status
from fastapi import HTTPException ## debugging and logs
from fastapi.responses import PlainTextResponse ## debugging and logs
from pydantic import BaseModel
from services.app_detector import detect_application_type
from services.deployer import generate_full_deployment
from services.storage import save_provision_record
from services.logs import get_container_logs, LogProviderError
from services.apps import list_running_apps

# algemene logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
app = FastAPI()


# bij het aanroepen van de API moet er een projectnaam en path meegegeven worden
class DeployRequest(BaseModel):
    app_id: str
    source_path: str


# Start van de deployment. als deze endpoint opgeroepen wordt zal de applicatie gescand worden,
# de nodige services en poorten worden toegekend en een docker-compose wordt op maat aangemaakt
@app.post("/deploy/full-stack")
def deploy_app(req: DeployRequest):
    # 1. Genereer de configuratie
    config_info = generate_full_deployment(req.app_id, req.source_path)

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
