"""Graph state shared by Requirement Autopsy agents."""

from typing import Any, TypedDict


class RequirementAutopsyState(TypedDict, total=False):
    """State passed between graph nodes.

    For now the graph has one node. Later nodes can append their own reports
    without changing the input contract.
    """

    client_requirement: str
    project_brief: str
    business_analyst_report: dict[str, Any]
    errors: list[str]
