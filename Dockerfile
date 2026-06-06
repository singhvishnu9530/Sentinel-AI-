# Sentinel AI backend — FastAPI + in-process LangGraph workflow
FROM python:3.12-slim

# System deps occasionally needed by lxml / pdf / bcrypt wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# SQLite lives here; mount a volume in production to persist it
RUN mkdir -p data

# Cloud platforms inject $PORT; default to 8001 locally
ENV PORT=8001
EXPOSE 8001

# Start the single backend service (serves auth, chat, extract, sessions + runs the graph in-process)
CMD ["sh", "-c", "uvicorn auth_server:app --host 0.0.0.0 --port ${PORT}"]
