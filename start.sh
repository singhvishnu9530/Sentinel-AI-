#!/bin/bash
# Single backend service — FastAPI serves auth, chat, extraction AND runs the
# LangGraph workflow in-process (no separate `langgraph dev` server needed).
source venv/bin/activate

echo "Starting Sentinel AI backend on http://localhost:8001 …"
python auth_server.py
