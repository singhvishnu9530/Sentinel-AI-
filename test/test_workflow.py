import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Setup environment variables first to pass constructor checks
os.environ["FOUNDRY_API_KEY"] = "mock_foundry_key"
os.environ["OPENAI_API_KEY"] = "mock_openai_key"

# Intercept sqlite3.connect during import to use in-memory database for checkpoints
orig_connect = sqlite3.connect
def mock_connect(database, *args, **kwargs):
    if "checkpoints.db" in str(database):
        # Using a shared in-memory database so multiple connection checks can access the same state
        return orig_connect("file::memory:?cache=shared", uri=True, *args, **kwargs)
    return orig_connect(database, *args, **kwargs)

with patch("sqlite3.connect", side_effect=mock_connect):
    from src.graphs.workflow import graph
    import src.graphs.workflow as wf

from src.agents.requirement_analyst import RequirementAnalystReport
from src.agents.tech_stack_advisor import TechStackAdvisorReport, StackRecommendation
from src.agents.complexity_risk import ComplexityRiskReport, RiskItem
from src.agents.security_analyser import SecurityAnalyserReport
from src.agents.nfr_detector import NFRDetectorReport
from src.agents.build_blueprint import BuildBlueprint, BudgetTier, BlueprintLayer, Alternative, TechniqueNote, ToolService, BuildPhase, KeyRisk, DeploymentGroup, Overview


def test_workflow_orchestration():
    """Verify that LangGraph workflow routes state correctly, aggregates outputs, and executes synthesis."""
    # Setup mock reports returned by each agent's run() method
    req_report = RequirementAnalystReport(
        business_goal="Test Goal",
        target_users=["Test User"],
        core_features=["Feature A"],
        hidden_requirements=["Req B"],
        assumptions=["Assump C"],
        out_of_scope=["Scope D"]
    )
    wf.requirement_analyst.run = MagicMock(return_value=req_report)

    stack_rec = StackRecommendation(
        layer="Database",
        recommendation="PostgreSQL",
        reason="Relational needs",
        alternatives=["MySQL"],
        tradeoff="None",
        estimated_cost="$0",
        lock_in="low"
    )
    tech_report = TechStackAdvisorReport(
        stack_recommendations=[stack_rec],
        deployment_platform="AWS",
        deployment_reason="Scalability",
        estimated_monthly_cost="$10/mo",
        cost_breakdown=["DB: $10/mo"]
    )
    wf.tech_stack_advisor.run = MagicMock(return_value=tech_report)

    comp_report = ComplexityRiskReport(
        hard_parts=["Syncing"],
        rewrite_triggers=["Scaling"],
        build_vs_buy=["Build auth"],
        key_risks=[RiskItem(risk="High load", mitigation="Load balancing")]
    )
    wf.complexity_risk.run = MagicMock(return_value=comp_report)

    sec_report = SecurityAnalyserReport(
        attack_surface=["IPs"],
        data_sensitivity=["PII"],
        auth_requirements=["JWT"],
        owasp_threats=["XSS"],
        secrets_management=["Vault"],
        compliance_requirements=["HIPAA"]
    )
    wf.security_analyser.run = MagicMock(return_value=sec_report)

    nfr_report = NFRDetectorReport(
        performance_requirements=["Latency < 50ms"],
        scalability_requirements=["10k users"],
        availability_requirements=["99.9%"],
        data_volume_requirements=["10GB"],
        missing_nfrs=["None"],
        nfr_conflicts=["None"]
    )
    wf.nfr_detector.run = MagicMock(return_value=nfr_report)

    blueprint_report = BuildBlueprint(
        project_type="Test Project",
        problem_statement="Problem statement",
        overview=Overview(what_it_is="A test product.", how_it_works="It does the thing.", why_this_approach="Because it fits."),
        budget_tiers=[BudgetTier(name="Lean", monthly_cost="$10/mo", summary="Lean option", best_for="Testing")],
        stack=[BlueprintLayer(layer="Database", choice="PostgreSQL", why="Relational needs", alternatives=[Alternative(name="MySQL", cost="Free", tradeoff="None")], cost="Free", basis="Brief")],
        implementation_techniques=[TechniqueNote(area="DB", recommendation="Indexing", details="Add indexes")],
        tools_and_services=[ToolService(name="AWS", purpose="Hosting", cost="Paid")],
        build_order=[BuildPhase(phase="Step 1", goal="DB", tasks=["Setup DB"])],
        deployment=[DeploymentGroup(area="Architecture", points=["AWS ECS Fargate for API + worker"])],
        estimated_monthly_cost="$10/mo",
        cost_breakdown=["DB: $10/mo"],
        decisions_to_make=["Decisions"],
        assumptions=["Assumptions"],
        key_risks=[KeyRisk(risk="None", mitigation="None")],
        security_checklist=["Checklist"]
    )
    wf.build_blueprint.run = MagicMock(return_value=blueprint_report)

    # Invoke workflow graph
    state_input = {"client_requirement": "Build a secure patient database"}
    result = graph.invoke(
        state_input,
        config={"recursion_limit": 20, "configurable": {"thread_id": "test-run-thread"}}
    )

    # Verify agent .run calls were made with correct requirement input
    wf.requirement_analyst.run.assert_called_once_with("Build a secure patient database")
    wf.tech_stack_advisor.run.assert_called_once_with("Build a secure patient database")
    wf.complexity_risk.run.assert_called_once_with("Build a secure patient database")
    wf.security_analyser.run.assert_called_once_with("Build a secure patient database")
    wf.nfr_detector.run.assert_called_once_with("Build a secure patient database")

    # Verify build blueprint was called with aggregated reports from other agents
    expected_reports_passed = {
        "requirement_analyst_report": req_report.model_dump(),
        "tech_stack_advisor_report": tech_report.model_dump(),
        "complexity_risk_report": comp_report.model_dump(),
        "security_analyser_report": sec_report.model_dump(),
        "nfr_detector_report": nfr_report.model_dump(),
    }
    wf.build_blueprint.run.assert_called_once_with(expected_reports_passed)

    # Verify final graph result state contains the synthesis blueprint report
    assert "build_blueprint_report" in result
    assert result["build_blueprint_report"] == blueprint_report.model_dump()
    assert result["build_blueprint_report"]["project_type"] == "Test Project"
