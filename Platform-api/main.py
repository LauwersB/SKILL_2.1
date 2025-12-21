import logging
from fastapi import FastAPI
from pydantic import BaseModel
from services.db_provisioning import provision_database
from services.app_detector import detect_application_type

# Configureer logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI()

class ProvisionRequest(BaseModel):
    app_id: str

class DetectRequest(BaseModel):
    source_path: str

@app.post("/provision/db")
def provision_db(req: ProvisionRequest):
    return provision_database(req.app_id)

@app.post("/detect/application")
def detect_application(req: DetectRequest):
    """
    Detecteer applicatietype en benodigde containers op basis van lokale directory.
    De directory moet al opgehaald zijn (lokaal of via GitHub) door module S1-10.
    """
    return detect_application_type(source_path=req.source_path)

