"""Build Blueprint synthesis agent — the hero output. Reads all agent reports."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.prompts.build_blueprint import BUILD_BLUEPRINT_PROMPT

load_dotenv()


class BlueprintLayer(BaseModel):
    layer: str               # "LLM", "Vector DB", "Frontend", etc.
    choice: str              # the ONE tool to use
    why: str                 # one-line justification
    alternatives: list[str]  # real swappable options the team can choose instead
    cost: str                # real monthly/usage cost or labelled estimate
    basis: str               # "From brief" or "Assumption"


class BuildPhase(BaseModel):
    phase: str               # "Phase 1 — Working Slice"
    goal: str                # what this phase proves
    tasks: list[str]         # concrete tasks


class KeyRisk(BaseModel):
    risk: str
    mitigation: str


class BuildBlueprint(BaseModel):
    project_type: str                 # "RAG Chatbot", "Payment Platform"
    summary: str                      # one paragraph: what we're building
    stack: list[BlueprintLayer]       # the full prescriptive stack
    assumptions: list[str]            # defaults we chose that weren't in the brief
    key_questions: list[str]          # answers that would change this blueprint
    build_order: list[BuildPhase]     # phased plan
    security_checklist: list[str]     # concrete security actions
    key_risks: list[KeyRisk]          # top risks + mitigations
    estimated_monthly_cost: str       # total range at launch with assumption
    cost_breakdown: list[str]         # per-component costs


class BuildBlueprintAgent:

    def __init__(self) -> None:
        api_key = os.getenv("FOUNDRY_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("FOUNDRY_API_KEY is required")

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "o4-mini"),
            api_key=api_key,
            base_url=os.getenv("azure_endpoint") or None,
        )
        self._llm = llm.with_structured_output(BuildBlueprint)

    def run(self, all_reports: dict) -> BuildBlueprint:
        reports_text = json.dumps(all_reports, indent=2)
        return self._llm.invoke([
            SystemMessage(content=BUILD_BLUEPRINT_PROMPT),
            HumanMessage(content=f"Specialist agent reports:\n{reports_text}"),
        ])
