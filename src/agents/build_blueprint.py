"""Build Blueprint synthesis agent — the hero output. Reads all agent reports."""

from __future__ import annotations

import json
import os
from langchain_core.utils.uuid import uuid7

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.agents.middleware.model_retry import ModelRetryMiddleware
from langchain.agents.middleware.tool_retry import ToolRetryMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from src.prompts.build_blueprint import BUILD_BLUEPRINT_PROMPT
from src.tools.web_search import web_search

load_dotenv()


class Alternative(BaseModel):
    name: str                # the alternative tool
    cost: str                # its cost (so the user can compare on price)
    tradeoff: str            # one line: what you gain/give up vs the recommended pick


class BlueprintLayer(BaseModel):
    layer: str               # "Language", "AI Model", "Database", "Frontend", etc.
    choice: str              # the recommended tool
    why: str                 # plain-English reason a newcomer understands
    alternatives: list[Alternative]  # priced options the user can choose instead
    cost: str                # cost of the recommended choice
    basis: str               # "From brief" or "Assumption"


class BudgetTier(BaseModel):
    name: str                # "Lean", "Balanced", "Scale"
    monthly_cost: str        # "~$30/mo"
    summary: str             # one line: the gist of this tier's stack
    best_for: str            # "Validating the idea / MVP"


class TechniqueNote(BaseModel):
    area: str                # the implementation area, whatever it is for THIS project
    recommendation: str      # the specific technique / library / pattern to use
    details: str             # how to apply it — concrete approach, params, libraries


class ToolService(BaseModel):
    name: str                # "OpenAI API", "GitHub", "Docker"
    purpose: str             # what it's for, plain language
    cost: str                # free / paid / estimate


class BuildPhase(BaseModel):
    phase: str               # "Step 1 — Working Slice"
    goal: str                # what this step delivers, plain language
    tasks: list[str]         # concrete tasks


class KeyRisk(BaseModel):
    risk: str
    mitigation: str


class BuildBlueprint(BaseModel):
    # ── Document flow: read top to bottom ──
    project_type: str                       # "AI Chatbot", "HIPAA Patient Portal"
    problem_statement: str                  # 1. what we're building & the problem it solves (plain language)
    overview: str                           # 2. the solution in a nutshell — how it works at a high level
    budget_tiers: list[BudgetTier]          # 3. pick-a-budget: Lean / Balanced / Scale bundles
    stack: list[BlueprintLayer]             # 4. recommended technology with priced alternatives to choose from
    implementation_techniques: list[TechniqueNote]  # 5. expert middle-layer techniques/patterns for THIS project
    tools_and_services: list[ToolService]   # 6. accounts/tools/services to set up
    build_order: list[BuildPhase]           # 6. how to build it, step by step
    deployment: str                         # 7. where & how to host it, explained (paragraph)
    estimated_monthly_cost: str             # 8. monthly cost range with assumption
    cost_breakdown: list[str]               # 8b. per-component cost lines
    decisions_to_make: list[str]            # 9. choices that would change the plan
    assumptions: list[str]                  # what we assumed since the brief was silent
    key_risks: list[KeyRisk]                # things to watch out for
    security_checklist: list[str]           # concrete security actions


class BuildBlueprintAgent:

    def __init__(self) -> None:
        api_key = os.getenv("FOUNDRY_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("FOUNDRY_API_KEY is required")

        self._llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "o4-mini"),
            api_key=api_key,
            base_url=os.getenv("azure_endpoint") or None,
        )
        self._checkpointer = InMemorySaver()
        self._agent = create_agent(
            model=self._llm,
            tools=[web_search],
            system_prompt=BUILD_BLUEPRINT_PROMPT,
            response_format=BuildBlueprint,
            checkpointer=self._checkpointer,
            middleware=[
                ModelRetryMiddleware(max_retries=3),
                ToolRetryMiddleware(max_retries=2),
            ],
        )

    def run(self, all_reports: dict) -> BuildBlueprint:
        thread_id = str(uuid7())
        reports_text = json.dumps(all_reports)
        result = self._agent.invoke(
            {"messages": [HumanMessage(content=f"Specialist agent reports:\n{reports_text}")]},
            config={
                "recursion_limit": 15,
                "configurable": {"thread_id": thread_id},
            },
        )
        return result["structured_response"]
