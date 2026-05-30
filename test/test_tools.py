import os
from unittest.mock import MagicMock, patch
import pytest

from src.tools.web_search import web_search


@pytest.fixture
def mock_tavily_env():
    """Ensure TAVILY_API_KEY is present in env for standard tests."""
    old_key = os.environ.get("TAVILY_API_KEY")
    os.environ["TAVILY_API_KEY"] = "mock_tavily_key"
    yield
    if old_key is not None:
        os.environ["TAVILY_API_KEY"] = old_key
    else:
        os.environ.pop("TAVILY_API_KEY", None)


@patch("src.tools.web_search.TavilyClient")
def test_web_search_success(mock_tavily_class, mock_tavily_env):
    """Verify web_search tool returns parsed results correctly when Tavily API succeeds."""
    mock_client = MagicMock()
    mock_tavily_class.return_value = mock_client
    
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Search Result 1",
                "url": "http://example.com/1",
                "content": "Content of search result 1",
                "score": 0.99
            },
            {
                "title": "Search Result 2",
                "url": "http://example.com/2",
                "content": "Content of search result 2",
                "score": 0.85
            }
        ]
    }

    # Call the tool using LangChain tool interface
    results = web_search.invoke({"query": "test query", "max_results": 5})

    # Assert TavilyClient was created with the API key from environment
    mock_tavily_class.assert_called_once_with(api_key="mock_tavily_key")
    
    # Assert search was called with correct arguments
    mock_client.search.assert_called_once_with(
        query="test query",
        search_depth="basic",
        max_results=5,
        include_answer=False,
        include_raw_content=False
    )

    # Assert formatting structure matches the expectation
    assert len(results) == 2
    assert results[0] == {
        "title": "Search Result 1",
        "url": "http://example.com/1",
        "content": "Content of search result 1"
    }
    assert results[1] == {
        "title": "Search Result 2",
        "url": "http://example.com/2",
        "content": "Content of search result 2"
    }


@patch("src.tools.web_search.os.getenv")
def test_web_search_missing_api_key(mock_getenv):
    """Verify web_search raises ValueError when TAVILY_API_KEY is missing from env."""
    # Ensure os.getenv("TAVILY_API_KEY") returns None, but other keys resolve normally
    mock_getenv.side_effect = lambda key, default=None: None if key == "TAVILY_API_KEY" else os.environ.get(key, default)

    with pytest.raises(ValueError, match="TAVILY_API_KEY is required"):
        web_search.invoke({"query": "test query"})
