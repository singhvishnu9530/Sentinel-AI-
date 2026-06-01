"""Helper to total token usage from a create_agent result.

Each AIMessage produced inside an agent's tool-calling loop carries
`usage_metadata` ({'input_tokens', 'output_tokens', 'total_tokens'}). Summing
total_tokens across all messages gives the true cost of one agent run.
"""

from __future__ import annotations


def sum_tokens(result: dict) -> int:
    total = 0
    for msg in result.get("messages", []):
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total += usage.get("total_tokens", 0) or 0
    return total
