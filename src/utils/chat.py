"""Chat endpoint — LLM proxy with streaming and LangGraph tool call."""

import json
import os

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.prompts.chat_agent import ANALYZE_TOOL, CHAT_SYSTEM_PROMPT, WEB_SEARCH_TOOL
from src.tools.web_search import web_search

load_dotenv()

router = APIRouter(prefix="/api")


def _azure_endpoint() -> str:
    return os.getenv("azure_endpoint", "")

def _api_key() -> str:
    return os.getenv("FOUNDRY_API_KEY", "")

def _model() -> str:
    return os.getenv("OPENAI_MODEL", "o4-mini")

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:2024")

# Pricing per 1M tokens (USD). Override in .env with your real Azure rates.
PRICE_INPUT_PER_1M = float(os.getenv("LLM_PRICE_INPUT_PER_1M", "1.25"))
PRICE_OUTPUT_PER_1M = float(os.getenv("LLM_PRICE_OUTPUT_PER_1M", "10.0"))


def _usd(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens / 1_000_000 * PRICE_INPUT_PER_1M
        + completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M,
        6,
    )

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


async def _stream_one_turn(client, messages, tool_calls, usage_acc):
    """One Azure streaming turn. Forwards content chunks; accumulates tool calls
    into `tool_calls` (index -> {id, name, args}) and token usage into `usage_acc`.
    Yields SSE lines to forward."""
    async with client.stream(
        "POST",
        f"{_azure_endpoint()}/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
        },
        content=json.dumps({
            "model": _model(),
            "messages": messages,
            "tools": [ANALYZE_TOOL, WEB_SEARCH_TOOL],
            "tool_choice": "auto",
            "stream": True,
            "stream_options": {"include_usage": True},
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
                usage = chunk.get("usage")
                if usage:
                    usage_acc["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    usage_acc["completion_tokens"] += usage.get("completion_tokens", 0)
                if not chunk.get("choices"):
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        slot = tool_calls.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["args"] += fn["arguments"]
                elif delta.get("content"):
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception:
                pass


@router.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for msg in req.messages:
        messages.append({"role": msg.role, "content": msg.content})

    async def generate():
        usage_acc = {"prompt_tokens": 0, "completion_tokens": 0}
        async with httpx.AsyncClient(timeout=120) as client:
            # Tool loop: web_search runs and continues; analyze_project is terminal.
            for _ in range(5):
                tool_calls: dict = {}
                async for sse in _stream_one_turn(client, messages, tool_calls, usage_acc):
                    yield sse

                if not tool_calls:
                    break  # plain text answer was streamed — done

                # analyze_project is terminal — run the full pipeline
                analyze = next((t for t in tool_calls.values() if t["name"] == "analyze_project"), None)
                if analyze:
                    try:
                        requirement = json.loads(analyze["args"]).get("requirement", "")
                        async for event in stream_langgraph(requirement):
                            if event["type"] == "progress":
                                yield f"data: {json.dumps({'type': 'progress', 'message': event['message']})}\n\n"
                            elif event["type"] == "analysis":
                                yield f"data: {json.dumps({'type': 'analysis', 'content': json.dumps(event['result'])})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                    break

                # Otherwise: execute web_search calls, feed results back, loop
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": t["id"], "type": "function",
                         "function": {"name": t["name"], "arguments": t["args"]}}
                        for t in tool_calls.values()
                    ],
                })
                for t in tool_calls.values():
                    if t["name"] == "web_search":
                        yield f"data: {json.dumps({'type': 'progress', 'message': 'Searching the web…'})}\n\n"
                        try:
                            query = json.loads(t["args"]).get("query", "")
                            results = web_search.invoke({"query": query})
                            content = json.dumps(results)[:6000]
                        except Exception as e:
                            content = json.dumps([{"error": str(e)}])
                        messages.append({"role": "tool", "tool_call_id": t["id"], "content": content})

        # Emit token usage + estimated cost for this turn
        cost_event = {
            "type": "cost",
            "prompt_tokens": usage_acc["prompt_tokens"],
            "completion_tokens": usage_acc["completion_tokens"],
            "total_tokens": usage_acc["prompt_tokens"] + usage_acc["completion_tokens"],
            "usd": _usd(usage_acc["prompt_tokens"], usage_acc["completion_tokens"]),
        }
        yield f"data: {json.dumps(cost_event)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
