"""Tech Stack Advisor agent — what to use at every layer + cost."""

from __future__ import annotations

import os
from langchain_core.utils.uuid import uuid7

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langchain.agents import create_agent
# Corrected Imports: Exact path resolution for LangChain Middleware
from langchain.agents.middleware.model_retry import ModelRetryMiddleware
from langchain.agents.middleware.tool_retry import ToolRetryMiddleware
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from src.prompts.tech_stack_advisor import TECH_STACK_ADVISOR_PROMPT
from src.tools.web_search import web_search

load_dotenv()


class StackRecommendation(BaseModel):
    layer: str               # "LLM", "Vector DB", "Frontend", "Cache"
    recommendation: str      # specific tool, e.g. "GPT-4o-mini"
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

        # Added: An ephemeral in-memory saver to persist the state during retry loops
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect("data/agent_checkpoints.db", check_same_thread=False)
        self._checkpointer = SqliteSaver(conn)

        self._agent = create_agent(
            model=self._llm,
            tools=[web_search],
            system_prompt=TECH_STACK_ADVISOR_PROMPT,
            response_format=TechStackAdvisorReport,
            checkpointer=self._checkpointer,
            middleware=[
                ModelRetryMiddleware(max_retries=3),
                ToolRetryMiddleware(max_retries=2)
            ]
        )

    def run(self, requirement: str) -> TechStackAdvisorReport:
        # Generate a unique thread ID so this specific run has isolated memory
        thread_id = str(uuid7())

        result = self._agent.invoke(
            {"messages": [HumanMessage(content=f"Client requirement:\n{requirement}")]},
            config={
                "recursion_limit": 10,
                "configurable": {"thread_id": thread_id}  # Binds memory state to the thread
            }
        )

        return result["structured_response"]
