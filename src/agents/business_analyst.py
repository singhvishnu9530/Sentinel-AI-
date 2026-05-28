"""Business Analyst node for the Requirement Autopsy graph."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from src.models.state import RequirementAutopsyState
from src.prompts.business_analyst import BUSINESS_ANALYST_SYSTEM_PROMPT
from src.tools.web_search import web_search

json_output_parser = JsonOutputParser()


def business_analyst_agent(
    state: RequirementAutopsyState,
) -> RequirementAutopsyState:
    """Create a team-ready business brief from raw client requirements."""

    requirement = state.get("client_requirement", "").strip()
    if not requirement:
        return {
            **state,
            "errors": [*state.get("errors", []), "client_requirement is required"],
        }

    try:
        report = _generate_report(requirement)
    except Exception as exc:
        return {
            **state,
            "errors": [*state.get("errors", []), f"Business Analyst failed: {exc}"],
        }

    return {
        **state,
        "business_analyst_report": report,
        "project_brief": report["team_brief"],
    }


def _generate_report(requirement: str) -> dict[str, Any]:
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    format_instructions = json_output_parser.get_format_instructions()
    llm = ChatOpenAI(
        model=model,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    llm_with_tools = llm.bind_tools([web_search])
    messages = [
        SystemMessage(
            content=(
                f"{BUSINESS_ANALYST_SYSTEM_PROMPT}\n\n"
                f"{format_instructions}"
            )
        ),
        HumanMessage(content=f"Client requirement:\n{requirement}"),
    ]

    response = llm_with_tools.invoke(messages)
    messages.append(response)

    for tool_call in response.tool_calls:
        tool_result = _run_tool(tool_call)
        messages.append(
            ToolMessage(
                content=json.dumps(tool_result),
                tool_call_id=tool_call["id"],
            )
        )

    if response.tool_calls:
        messages.append(
            HumanMessage(
                content=(
                    "Use the tool results if they are relevant. Now return the "
                    "final Business Analyst report as valid JSON only."
                )
            )
        )
        response = llm.invoke(messages)

    content = response.content or "{}"
    parsed_report = json_output_parser.parse(content)
    return _normalize_report(parsed_report, requirement)


def _run_tool(tool_call: dict[str, Any]) -> Any:
    if tool_call["name"] == "web_search":
        return web_search.invoke(tool_call["args"])
    raise ValueError(f"Unknown tool requested: {tool_call['name']}")


def _normalize_report(report: dict[str, Any], requirement: str) -> dict[str, Any]:
    defaults = _empty_report(requirement)
    normalized = {**defaults, **report}

    for key in (
        "target_users",
        "stakeholders",
        "core_features",
        "success_metrics",
        "assumptions",
        "unclear_points",
        "recommended_next_questions",
        "research_sources",
    ):
        value = normalized.get(key, [])
        if isinstance(value, str):
            normalized[key] = [value]
        elif not isinstance(value, list):
            normalized[key] = []

    for key in ("executive_summary", "business_goal", "team_brief"):
        value = normalized.get(key, "")
        normalized[key] = value if isinstance(value, str) else str(value)

    return normalized


def _empty_report(requirement: str) -> dict[str, Any]:
    return {
        "executive_summary": requirement[:220],
        "business_goal": "Clarify the business outcome behind the requirement",
        "target_users": [],
        "stakeholders": [],
        "core_features": [],
        "success_metrics": [],
        "assumptions": [],
        "unclear_points": [],
        "recommended_next_questions": [],
        "research_sources": [],
        "team_brief": requirement[:500],
    }
