"""LangGraph workflow — 5 parallel analysis agents → 1 build blueprint synthesis."""

# load_dotenv MUST run before any LangChain import so LANGCHAIN_TRACING_V2
# is in the environment when the LangSmith tracing client initialises.
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import END, START, StateGraph

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


def _run_agent(report_key: str, agent, state: RequirementAutopsyState) -> RequirementAutopsyState:
    """Run one analysis agent safely. A failure here must NOT kill the other
    agents or the synthesis — record the error and return an empty report."""
    requirement = state.get("client_requirement", "").strip()
    if not requirement:
        return {report_key: {}, "errors": [f"{report_key}: no client_requirement provided"]}
    try:
        report = agent.run(requirement).model_dump()
        return {report_key: report, "agent_tokens": getattr(agent, "last_tokens", 0)}
    except Exception as exc:  # noqa: BLE001 — we want to catch everything
        return {report_key: {}, "errors": [f"{report_key} failed: {exc}"]}


def requirement_analyst_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return _run_agent("requirement_analyst_report", requirement_analyst, state)

def tech_stack_advisor_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return _run_agent("tech_stack_advisor_report", tech_stack_advisor, state)

def complexity_risk_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return _run_agent("complexity_risk_report", complexity_risk, state)

def security_analyser_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return _run_agent("security_analyser_report", security_analyser, state)

def nfr_detector_node(state: RequirementAutopsyState) -> RequirementAutopsyState:
    return _run_agent("nfr_detector_report", nfr_detector, state)


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
    try:
        report = build_blueprint.run(_collect_reports(state)).model_dump()
        return {"build_blueprint_report": report, "agent_tokens": getattr(build_blueprint, "last_tokens", 0)}
    except Exception as exc:  # noqa: BLE001
        return {
            "build_blueprint_report": {},
            "errors": [f"build_blueprint failed: {exc}"],
        }


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

    # No checkpointer on the orchestration graph — it's a single-pass fan-out →
    # synthesis. Each agent keeps its own checkpointer for its retry loop.
    return workflow.compile()


graph = build_workflow_graph()
