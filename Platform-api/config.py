import os
from pathlib import Path
from dotenv import load_dotenv

# Vind de .env in de map van platform-api
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

# Platform DB instellingen
# We halen de db_credentials uit de .env en slaan ze op als variabelen
db_host = os.getenv("PLATFORM_DB_HOST", "host")
db_name = os.getenv("PLATFORM_DB_NAME", "dbname")
username = os.getenv("PLATFORM_DB_USER", "username")
password = os.getenv("PLATFORM_DB_PASSWORD", "password")

# Credentials platform_admin
admin_user = os.getenv("PLATFORM_ADMIN_USERNAME", "admin")
admin_pass = os.getenv("PLATFORM_ADMIN_PASSWORD", "admin")