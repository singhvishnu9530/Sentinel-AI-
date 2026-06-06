import os
import pytest
from unittest.mock import MagicMock, patch

# Configure environment variables to pass __init__ checks
os.environ["FOUNDRY_API_KEY"] = "mock_foundry_key"
os.environ["OPENAI_API_KEY"] = "mock_openai_key"

from src.agents.requirement_analyst import RequirementAnalystAgent, RequirementAnalystReport
from src.agents.tech_stack_advisor import TechStackAdvisorAgent, TechStackAdvisorReport, StackRecommendation
from src.agents.complexity_risk import ComplexityRiskAgent, ComplexityRiskReport, RiskItem
from src.agents.security_analyser import SecurityAnalyserAgent, SecurityAnalyserReport
from src.agents.nfr_detector import NFRDetectorAgent, NFRDetectorReport
from src.agents.build_blueprint import BuildBlueprintAgent, BuildBlueprint, Alternative, BlueprintLayer, BudgetTier, TechniqueNote, ToolService, BuildPhase, KeyRisk, DeploymentGroup, Overview


@patch("src.agents.requirement_analyst.create_agent")
def test_requirement_analyst_agent(mock_create_agent):
    """Test RequirementAnalystAgent run invokes create_agent and returns correct report structure."""
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance
    
    expected_report = RequirementAnalystReport(
        business_goal="Build a high performance task manager",
        target_users=["Product managers", "Software teams"],
        core_features=["Kanban boards", "Timeline view", "Real-time updates"],
        hidden_requirements=["Caching layer for high-throughput reads"],
        assumptions=["Users have internet access", "Desktop-first experience"],
        out_of_scope=["Mobile application version"]
    )
    
    mock_agent_instance.invoke.return_value = {"structured_response": expected_report}
    
    agent = RequirementAnalystAgent()
    result = agent.run("Task manager app brief")
    
    assert result == expected_report
    assert result.business_goal == "Build a high performance task manager"
    assert len(result.core_features) == 3
    mock_create_agent.assert_called_once()
    mock_agent_instance.invoke.assert_called_once()


@patch("src.agents.tech_stack_advisor.create_agent")
def test_tech_stack_advisor_agent(mock_create_agent):
    """Test TechStackAdvisorAgent run invokes agent and returns TechStackAdvisorReport."""
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance
    
    rec = StackRecommendation(
        layer="Frontend",
        recommendation="Next.js App Router",
        reason="Server-side rendering and search optimization support",
        alternatives=["React SPA (Vite)", "Vue.js"],
        tradeoff="Higher learning curve compared to simple SPA",
        estimated_cost="$0 (Open Source, Vercel hosting hobby tier)",
        lock_in="medium"
    )
    
    expected_report = TechStackAdvisorReport(
        stack_recommendations=[rec],
        deployment_platform="Vercel",
        deployment_reason="Easiest hosting for Next.js with CD pipelines built-in",
        estimated_monthly_cost="~$0-$20/mo",
        cost_breakdown=["Frontend hosting: $0", "Database (Supabase): $10/mo"]
    )
    
    mock_agent_instance.invoke.return_value = {"structured_response": expected_report}
    
    agent = TechStackAdvisorAgent()
    result = agent.run("Task manager app brief")
    
    assert result == expected_report
    assert len(result.stack_recommendations) == 1
    assert result.stack_recommendations[0].recommendation == "Next.js App Router"
    assert result.deployment_platform == "Vercel"
    mock_create_agent.assert_called_once()
    mock_agent_instance.invoke.assert_called_once()


@patch("src.agents.complexity_risk.create_agent")
def test_complexity_risk_agent(mock_create_agent):
    """Test ComplexityRiskAgent run invokes agent and returns ComplexityRiskReport."""
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance
    
    expected_report = ComplexityRiskReport(
        hard_parts=["Real-time drag and drop synchronization across client sessions"],
        rewrite_triggers=["Scaling beyond 10,000 active concurrent WebSocket threads"],
        build_vs_buy=["Buy Auth0 instead of building custom OAuth provider"],
        key_risks=[RiskItem(risk="Concurrent write conflicts", mitigation="Operational Transformation or CRDTs")]
    )
    
    mock_agent_instance.invoke.return_value = {"structured_response": expected_report}
    
    agent = ComplexityRiskAgent()
    result = agent.run("Task manager app brief")
    
    assert result == expected_report
    assert len(result.key_risks) == 1
    assert result.key_risks[0].risk == "Concurrent write conflicts"
    mock_create_agent.assert_called_once()
    mock_agent_instance.invoke.assert_called_once()


@patch("src.agents.security_analyser.create_agent")
def test_security_analyser_agent(mock_create_agent):
    """Test SecurityAnalyserAgent run invokes agent and returns SecurityAnalyserReport."""
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance
    
    expected_report = SecurityAnalyserReport(
        attack_surface=["Public login endpoint", "File attachment storage URLs"],
        data_sensitivity=["User emails", "Access tokens", "Task descriptions"],
        auth_requirements=["JWT authorization headers", "Strict RBAC rules"],
        owasp_threats=["A01:2021-Broken Access Control in Kanban routes"],
        secrets_management=["Use Azure Key Vault / Github secrets for deployment"],
        compliance_requirements=["GDPR Right to Be Forgotten compliance for deleted users"]
    )
    
    mock_agent_instance.invoke.return_value = {"structured_response": expected_report}
    
    agent = SecurityAnalyserAgent()
    result = agent.run("Task manager app brief")
    
    assert result == expected_report
    assert "Public login endpoint" in result.attack_surface
    assert len(result.owasp_threats) == 1
    mock_create_agent.assert_called_once()
    mock_agent_instance.invoke.assert_called_once()


@patch("src.agents.nfr_detector.create_agent")
def test_nfr_detector_agent(mock_create_agent):
    """Test NFRDetectorAgent run invokes agent and returns NFRDetectorReport."""
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance
    
    expected_report = NFRDetectorReport(
        performance_requirements=["API responses in under 200ms"],
        scalability_requirements=["Handle up to 1,000 daily active users initially"],
        availability_requirements=["99.9% uptime requirement"],
        data_volume_requirements=["~100MB database growth per month"],
        missing_nfrs=["Uptime SLA and disaster recovery strategy is undefined in brief"],
        nfr_conflicts=["Real-time sync may increase API response latency on weak network connections"]
    )
    
    mock_agent_instance.invoke.return_value = {"structured_response": expected_report}
    
    agent = NFRDetectorAgent()
    result = agent.run("Task manager app brief")
    
    assert result == expected_report
    assert "99.9% uptime requirement" in result.availability_requirements
    mock_create_agent.assert_called_once()
    mock_agent_instance.invoke.assert_called_once()


@patch("src.agents.build_blueprint.create_agent")
def test_build_blueprint_agent(mock_create_agent):
    """Test BuildBlueprintAgent run invokes agent and returns BuildBlueprint."""
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance
    
    expected_report = BuildBlueprint(
        project_type="AI Task Manager",
        problem_statement="Team coordination is slow and manual.",
        overview=Overview(what_it_is="A task manager.", how_it_works="Users create and track tasks.", why_this_approach="Simple and fast to ship."),
        budget_tiers=[BudgetTier(name="Lean", monthly_cost="$5/mo", summary="Free frontend hosting + Supabase free tier", best_for="MVP validation")],
        stack=[BlueprintLayer(layer="Frontend", choice="Next.js", why="SEO and SSR", alternatives=[Alternative(name="Vite React", cost="Free", tradeoff="No SSR")], cost="Free", basis="Assumption")],
        implementation_techniques=[TechniqueNote(area="State Management", recommendation="Zustand", details="Lightweight global store")],
        tools_and_services=[ToolService(name="OpenAI API", purpose="Smart task categorization", cost="Usage-based (~$10/mo)")],
        build_order=[BuildPhase(phase="Step 1", goal="Database setup", tasks=["Design PostgreSQL schemas", "Configure indexes"])],
        deployment=[DeploymentGroup(area="Architecture", points=["Vercel for frontend", "Supabase for backend"])],
        estimated_monthly_cost="~$15/mo",
        cost_breakdown=["Supabase db: $10/mo", "OpenAI usage: $5/mo"],
        decisions_to_make=["Decide if real-time WebSockets are required or long-polling is sufficient"],
        assumptions=["Users do not require off-line support initially"],
        key_risks=[KeyRisk(risk="Database cost scaling", mitigation="Add strict rate limiting to OpenAI calls")],
        security_checklist=["Enable TLS on Supabase connection pool", "Store OpenAI keys in GitHub Secrets"]
    )
    
    mock_agent_instance.invoke.return_value = {"structured_response": expected_report}
    
    agent = BuildBlueprintAgent()
    result = agent.run({"some_specialist_report": "data"})
    
    assert result == expected_report
    assert result.project_type == "AI Task Manager"
    assert len(result.budget_tiers) == 1
    assert result.budget_tiers[0].name == "Lean"
    mock_create_agent.assert_called_once()
    mock_agent_instance.invoke.assert_called_once()
