"""Complexity & Risk agent — what's hard + what could kill it (complexity + risk merged)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from src.prompts.complexity_risk import COMPLEXITY_RISK_PROMPT
from src.tools.web_search import web_search

load_dotenv()


class RiskItem(BaseModel):
    risk: str
    mitigation: str


class ComplexityRiskReport(BaseModel):
    hard_parts: list[str]
    rewrite_triggers: list[str]
    build_vs_buy: list[str]
    key_risks: list[RiskItem]


class ComplexityRiskAgent:

    def __init__(self) -> None:
        api_key = os.getenv("FOUNDRY_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("FOUNDRY_API_KEY is required")

        self._llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "o4-mini"),
            api_key=api_key,
            base_url=os.getenv("azure_endpoint") or None,
        )
        self._structured_llm = self._llm.with_structured_output(ComplexityRiskReport)
        self._agent = create_react_agent(
            model=self._llm,
            tools=[web_search],
            prompt=SystemMessage(content=COMPLEXITY_RISK_PROMPT),
        )

    def run(self, requirement: str) -> ComplexityRiskReport:
        result = self._agent.invoke(
            {"messages": [HumanMessage(content=f"Client requirement:\n{requirement}")]},
            config={"recursion_limit": 10},
        )
        return self._structured_llm.invoke(result["messages"])
