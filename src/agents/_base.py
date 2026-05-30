"""Shared base for research agents — guarantees web_search usage, then structured output.

Why not create_react_agent: with tool_choice="auto" the model (gpt-5.2) skips the
tool entirely and answers from memory — no live research, nothing in observability.

This base FORCES at least one web_search, allows a few more, then produces the
structured report. Guaranteed tool usage + accurate current data + clean schema.
"""

from __future__ import annotations

import json
import os
from typing import Type, TypeVar

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.tools.web_search import web_search

load_dotenv()

T = TypeVar("T", bound=BaseModel)

MAX_SEARCH_ROUNDS = 4  # 1 forced + up to 3 more


def _make_llm() -> ChatOpenAI:
    api_key = os.getenv("FOUNDRY_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("FOUNDRY_API_KEY is required")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "o4-mini"),
        api_key=api_key,
        base_url=os.getenv("azure_endpoint") or None,
    )


class ResearchAgent:
    """Base: system prompt + output schema. Forces research, returns structured report."""

    def __init__(self, system_prompt: str, schema: Type[T]) -> None:
        self._schema = schema
        self._prompt = system_prompt
        llm = _make_llm()
        # First call: force a tool call so the agent always researches.
        self._forced = llm.bind_tools([web_search], tool_choice="required")
        # Later calls: let it decide whether to search again.
        self._auto = llm.bind_tools([web_search], tool_choice="auto")
        # Final: structured output.
        self._structured = llm.with_structured_output(schema)

    def run(self, requirement: str) -> T:
        messages = [
            SystemMessage(content=self._prompt),
            HumanMessage(content=f"Client requirement:\n{requirement}"),
        ]

        # Round 1 — forced search
        ai: AIMessage = self._forced.invoke(messages)
        messages.append(ai)
        self._run_tools(ai, messages)

        # Rounds 2..N — optional further searches the model chooses
        for _ in range(MAX_SEARCH_ROUNDS - 1):
            ai = self._auto.invoke(messages)
            messages.append(ai)
            if not ai.tool_calls:
                break
            self._run_tools(ai, messages)

        # Final — structured report from everything gathered
        messages.append(HumanMessage(
            content="Using the research above, produce the final report now."
        ))
        return self._structured.invoke(messages)

    @staticmethod
    def _run_tools(ai: AIMessage, messages: list) -> None:
        for tc in ai.tool_calls:
            try:
                result = web_search.invoke(tc["args"])
            except Exception as exc:
                result = [{"error": str(exc)}]
            messages.append(ToolMessage(
                content=json.dumps(result)[:6000],
                tool_call_id=tc["id"],
            ))
