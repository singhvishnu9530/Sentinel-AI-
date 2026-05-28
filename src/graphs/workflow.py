"""LangGraph workflow for the Requirement Autopsy project."""

from langgraph.graph import END, StateGraph

from src.agents.business_analyst import business_analyst_agent
from src.models.state import RequirementAutopsyState


def build_workflow_graph():
    """Build the first graph version with only the Business Analyst node."""

    workflow = StateGraph(RequirementAutopsyState)
    workflow.add_node("business_analyst_agent", business_analyst_agent)
    workflow.set_entry_point("business_analyst_agent")
    workflow.add_edge("business_analyst_agent", END)
    return workflow.compile()


graph = build_workflow_graph()
