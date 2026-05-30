"""Chat endpoint — LLM proxy with streaming and LangGraph tool call."""

import json
import os

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.prompts.chat_agent import ANALYZE_TOOL, CHAT_SYSTEM_PROMPT

load_dotenv()

router = APIRouter(prefix="/api")


def _azure_endpoint() -> str:
    return os.getenv("azure_endpoint", "")

def _api_key() -> str:
    return os.getenv("FOUNDRY_API_KEY", "")

def _model() -> str:
    return os.getenv("OPENAI_MODEL", "o4-mini")

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:2024")

# Map internal node names to neutral, user-facing phase messages.
# Deliberately does NOT reveal the agent architecture.
PHASE_MESSAGES = {
    "requirement_analyst": "Understanding your requirements…",
    "tech_stack_advisor": "Researching the best technology options…",
    "complexity_risk": "Assessing complexity and risks…",
    "security_analyser": "Reviewing security considerations…",
    "nfr_detector": "Checking performance and scale needs…",
    "build_blueprint": "Assembling your build blueprint…",
}


async def stream_langgraph(requirement: str):
    """Run the graph and yield (progress messages) then the final result.

    Yields dicts: {"type": "progress", "message": ...} for each phase,
    and finally {"type": "analysis", "result": {...}}.
    """
    async with httpx.AsyncClient(timeout=300) as client:
        thread_res = await client.post(
            f"{LANGGRAPH_URL}/threads",
            headers={"Content-Type": "application/json"},
            content=json.dumps({}),
        )
        thread_res.raise_for_status()
        thread_id = thread_res.json()["thread_id"]

        final_state: dict = {}

        async with client.stream(
            "POST",
            f"{LANGGRAPH_URL}/threads/{thread_id}/runs/stream",
            headers={"Content-Type": "application/json"},
            content=json.dumps({
                "assistant_id": "my_agent",
                "input": {"client_requirement": requirement},
                "stream_mode": "updates",
            }),
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    update = json.loads(raw)
                except Exception:
                    continue
                # update is keyed by node name(s) that just finished
                if isinstance(update, dict):
                    for node, node_output in update.items():
                        if node in PHASE_MESSAGES:
                            yield {"type": "progress", "message": PHASE_MESSAGES[node]}
                        if isinstance(node_output, dict):
                            final_state.update(node_output)

        yield {"type": "analysis", "result": final_state}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(req: ChatRequest):
    payload = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for msg in req.messages:
        payload.append({"role": msg.role, "content": msg.content})

    async def generate():
        tool_call_args = ""
        is_tool_call = False

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{_azure_endpoint()}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {_api_key()}",
                },
                content=json.dumps({
                    "model": _model(),
                    "messages": payload,
                    "tools": [ANALYZE_TOOL],
                    "tool_choice": "auto",
                    "stream": True,
                }),
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})

                        if delta.get("tool_calls"):
                            is_tool_call = True
                            for tc in delta["tool_calls"]:
                                if tc.get("function", {}).get("arguments"):
                                    tool_call_args += tc["function"]["arguments"]
                        elif delta.get("content"):
                            yield f"data: {json.dumps(chunk)}\n\n"
                    except Exception:
                        pass

        if is_tool_call:
            try:
                requirement = json.loads(tool_call_args).get("requirement", "")
                async for event in stream_langgraph(requirement):
                    if event["type"] == "progress":
                        yield f"data: {json.dumps({'type': 'progress', 'message': event['message']})}\n\n"
                    elif event["type"] == "analysis":
                        yield f"data: {json.dumps({'type': 'analysis', 'content': json.dumps(event['result'])})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
