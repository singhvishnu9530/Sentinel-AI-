"""Complexity & Risk agent — what's hard + what could kill it (complexity + risk merged)."""

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
# Required for tracking internal error states during iteration self-correction
from langgraph.checkpoint.memory import InMemorySaver

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

        # Added: An ephemeral in-memory saver to persist the state during retry loops
        self._checkpointer = InMemorySaver()

        self._agent = create_agent(
            model=self._llm,
            tools=[web_search],
            system_prompt=COMPLEXITY_RISK_PROMPT,
            response_format=ComplexityRiskReport,
            checkpointer=self._checkpointer,
            middleware=[
                ModelRetryMiddleware(max_retries=3),
                ToolRetryMiddleware(max_retries=2)
            ]
        )

    def run(self, requirement: str) -> ComplexityRiskReport:
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
