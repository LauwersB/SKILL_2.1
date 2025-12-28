import logging
from fastapi import FastAPI
from pydantic import BaseModel
from services.app_detector import detect_application_type
from services.deployer import generate_full_deployment
from services.storage import save_provision_record

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
    config_info = generate_full_deployment(req.app_id, req.source_path)
    compose_dict = config_info[0]
    web_port = config_info[1]
    db_port = config_info[2]

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