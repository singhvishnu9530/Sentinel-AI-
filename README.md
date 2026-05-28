# Requirement Autopsy

Multi-agent requirement analysis system. The first implemented node is the
Business Analyst agent, which turns a raw client requirement into a clear team
brief before implementation starts.

## Current Graph

```text
client_requirement -> business_analyst_agent -> project_brief
```

## Run Locally

```bash
./venv/bin/python -m src.graphs.workflow
```

Quick invocation:

```bash
./venv/bin/python - <<'PY'
from src.graphs.workflow import graph

result = graph.invoke({
    "client_requirement": "We need a portal where clients upload documents, admins review them, and managers can see status reports."
})

print(result["project_brief"])
print(result["business_analyst_report"])
PY
```

If `OPENAI_API_KEY` is set, the agent uses OpenAI for analysis. Without it, the
node still returns a structured local draft so the workflow can be tested.
