"""Graph state shared by all agents."""

from typing import Any, TypedDict


class RequirementAutopsyState(TypedDict, total=False):
    client_requirement: str
    requirement_analyst_report: dict[str, Any]
    tech_stack_advisor_report: dict[str, Any]
    complexity_risk_report: dict[str, Any]
    security_analyser_report: dict[str, Any]
    nfr_detector_report: dict[str, Any]
    build_blueprint_report: dict[str, Any]
    errors: list[str]
