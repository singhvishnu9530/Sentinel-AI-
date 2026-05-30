"""LangGraph workflow — 5 parallel analysis agents → 1 build blueprint synthesis."""

# load_dotenv MUST run before any LangChain import so LANGCHAIN_TRACING_V2
# is in the environment when the LangSmith tracing client initialises.
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agents.build_blueprint import BuildBlueprintAgent
from src.agents.complexity_risk import ComplexityRiskAgent
from src.agents.nfr_detector import NFRDetectorAgent
from src.agents.requirement_analyst import RequirementAnalystAgent
from src.agents.security_analyser import SecurityAnalyserAgent
from src.agents.tech_stack_advisor import TechStackAdvisorAgent
from src.models.state import RequirementAutopsyState

# Parallel analysis agents
requirement_analyst = RequirementAnalystAgent()
tech_stack_advisor = TechStackAdvisorAgent()
complexity_risk = ComplexityRiskAgent()
security_analyser = SecurityAnalyserAgent()
nfr_detector = NFRDetectorAgent()

# Synthesis agent — the hero output
build_blueprint = BuildBlueprintAgent()

PARALLEL_NODES = [
    "requirement_analyst",
    "tech_stack_advisor",
    "complexity_risk",
    "security_analyser",
    "nfr_detector",
]


def requirement_analyst_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return {"requirement_analyst_report": requirement_analyst.run(state["client_requirement"]).model_dump()}

def tech_stack_advisor_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return {"tech_stack_advisor_report": tech_stack_advisor.run(state["client_requirement"]).model_dump()}

def complexity_risk_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return {"complexity_risk_report": complexity_risk.run(state["client_requirement"]).model_dump()}

def security_analyser_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return {"security_analyser_report": security_analyser.run(state["client_requirement"]).model_dump()}

def nfr_detector_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return {"nfr_detector_report": nfr_detector.run(state["client_requirement"]).model_dump()}


def _collect_reports(state: RequirementAutopsyState) -> dict:
    return {
        k: state.get(k, {}) for k in [
            "requirement_analyst_report",
            "tech_stack_advisor_report",
            "complexity_risk_report",
            "security_analyser_report",
            "nfr_detector_report",
        ]
    }

def build_blueprint_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return {"build_blueprint_report": build_blueprint.run(_collect_reports(state)).model_dump()}


def build_workflow_graph():
    workflow = StateGraph(RequirementAutopsyState)

    node_fns = {
        "requirement_analyst": requirement_analyst_node,
        "tech_stack_advisor": tech_stack_advisor_node,
        "complexity_risk": complexity_risk_node,
        "security_analyser": security_analyser_node,
        "nfr_detector": nfr_detector_node,
        "build_blueprint": build_blueprint_node,
    }

    for name, fn in node_fns.items():
        workflow.add_node(name, fn)

    # Fan out — 5 parallel analysis agents from START
    for name in PARALLEL_NODES:
        workflow.add_edge(START, name)

    # Fan in — blueprint waits for all 5, then synthesises
    for name in PARALLEL_NODES:
        workflow.add_edge(name, "build_blueprint")

    workflow.add_edge("build_blueprint", END)

    import os
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return workflow.compile(checkpointer=checkpointer)


graph = build_workflow_graph()
