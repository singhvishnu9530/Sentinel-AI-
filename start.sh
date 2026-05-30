#!/bin/bash
source venv/bin/activate

echo "Starting Sentinel AI backend..."

python auth_server.py &
AUTH_PID=$!

langgraph dev &
LANGGRAPH_PID=$!

echo "Auth server running (PID $AUTH_PID)"
echo "LangGraph running (PID $LANGGRAPH_PID)"
echo "Press Ctrl+C to stop both"

trap "kill $AUTH_PID $LANGGRAPH_PID 2>/dev/null; exit" SIGINT SIGTERM

wait
