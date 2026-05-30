"""Web search tool backed by Tavily."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient


@tool
def web_search(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Search the web for similar products, competitors, and market patterns."""

    load_dotenv()
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is required")

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
    )

    results = response.get("results", [])
    return [
        {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", ""),
        }
        for result in results
    ]
