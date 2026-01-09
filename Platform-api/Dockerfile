FROM python:3.11-slim

# 1. Installeer Git, Docker CLI EN Docker Compose
RUN apt-get update && apt-get install -y \
    git \
    docker.io \
    docker-compose \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Python dependencies
COPY platform-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Kopieer mappen
COPY scripts/ /app/scripts/
COPY platform-api/ /app/platform-api/

# 4. Rechten voor scripts en werkmap
RUN chmod +x /app/scripts/*.sh
RUN mkdir -p /app/clients && chmod -R 777 /app/clients

# 5. Start de API
CMD ["uvicorn", "main:app", "--app-dir", "platform-api", "--host", "0.0.0.0", "--port", "8080"]