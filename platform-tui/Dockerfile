FROM python:3.11-slim

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kopieer requirements uit de TUI map
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer alle bestanden van platform-tui naar /app in de container
COPY . .

# Hou container open
CMD ["tail", "-f", "/dev/null"]