"""Tech Stack Advisor agent — What should we use and what will it cost?"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from src.prompts.tech_stack_advisor import TECH_STACK_ADVISOR_PROMPT
from src.tools.web_search import web_search

load_dotenv()


class StackRecommendation(BaseModel):
    layer: str               # e.g. "LLM", "Vector DB", "Frontend", "Cache"
    recommendation: str      # the specific tool chosen, e.g. "GPT-4o-mini"
    reason: str              # why this wins for THIS requirement
    alternatives: list[str]  # 2-3 real alternatives considered
    tradeoff: str            # what you give up vs the alternatives
    estimated_cost: str      # real number from web search
    lock_in: str             # "low" | "medium" | "high"


class TechStackAdvisorReport(BaseModel):
    stack_recommendations: list[StackRecommendation]
    deployment_platform: str
    deployment_reason: str
    estimated_monthly_cost: str
    cost_breakdown: list[str]


class TechStackAdvisorAgent:

    def __init__(self) -> None:
        api_key = os.getenv("FOUNDRY_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("FOUNDRY_API_KEY is required")

        self._llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "o4-mini"),
            api_key=api_key,
            base_url=os.getenv("azure_endpoint") or None,
        )
        self._structured_llm = self._llm.with_structured_output(TechStackAdvisorReport)
        self._agent = create_react_agent(
            model=self._llm,
            tools=[web_search],
            prompt=SystemMessage(content=TECH_STACK_ADVISOR_PROMPT),
        )

    def run(self, requirement: str) -> TechStackAdvisorReport:
        result = self._agent.invoke(
            {"messages": [HumanMessage(content=f"Client requirement:\n{requirement}")]},
            config={"recursion_limit": 10},
        )
        return self._structured_llm.invoke(result["messages"])
