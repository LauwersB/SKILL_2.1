FROM python:3.11-slim

# 1. Installeer Git, Docker CLI EN Docker Compose plugin
RUN apt-get update && apt-get install -y \
    git \
    docker.io \
    docker-compose \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Python afhankelijkheden
COPY platform-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Kopieer de mappen vanaf de root van je project naar de container
# We kopiëren de scripts naar /app/scripts en de api naar /app/platform-api
COPY scripts/ /app/scripts/
COPY platform-api/ /app/platform-api/

# 4. Zorg dat alle scripts uitvoerbaar zijn
# We doen dit recursief voor de zekerheid
RUN chmod +x /app/scripts/*.sh
RUN chmod -R 777 /app/clients

# 5. Start de API vanuit de juiste map
# Let op: als main.py in /app/platform-api/ staat,
# moet je Uvicorn vertellen waar hij moet kijken.
# We verplaatsen de CMD naar de map waar main.py staat
CMD ["uvicorn", "main:app", "--app-dir", "platform-api", "--host", "0.0.0.0", "--port", "8080"]