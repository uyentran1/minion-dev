"""
Test the Planner agent
"""
import pytest

from miniondev.agent import PlannerAgent, AgentType
from miniondev.llm.client import MockChatClient
from miniondev.models import PlanArtifact

VALID_PLAN_JSON = """{
    "summary": "Add a multiply function to the calculator module",
    "steps": [
        {"step_number": 1, "description": "Add multiply() to calculator.py", "target_files": ["calculator.py"]},
        {"step_number": 2, "description": "Add tests for multiply()"}
    ],
    "acceptance_criteria": ["multiply(2, 3) returns 6"]
}"""


class TestPlannerAgent:
    """Test PlannerAgent basics"""

    def test_agent_type(self):
        agent = PlannerAgent(MockChatClient())
        assert agent.agent_type == AgentType.PLANNER

    def test_restricted_tools(self):
        """Planner must not be offered mutating tools like write_file or run_command"""
        agent = PlannerAgent(MockChatClient())
        tool_names = {t.name for t in agent.get_available_tools()}

        assert "write_file" not in tool_names
        assert "run_command" not in tool_names
        assert "read_file" in tool_names


class TestPlannerPlanExtraction:
    """Test parsing the LLM's final response into a PlanArtifact"""

    def test_valid_json_produces_plan(self, test_context):
        agent = PlannerAgent(MockChatClient(content=VALID_PLAN_JSON))

        result = agent.execute(test_context, {"title": "Add multiply", "description": "..."})

        assert result.success
        plan = result.data["plan"]
        assert isinstance(plan, PlanArtifact)
        assert plan.work_item_id == test_context.work_item_id
        assert len(plan.steps) == 2
        assert plan.steps[0].target_files == ["calculator.py"]

    def test_json_wrapped_in_markdown_fences_is_parsed(self, test_context):
        fenced = f"```json\n{VALID_PLAN_JSON}\n```"
        agent = PlannerAgent(MockChatClient(content=fenced))

        result = agent.execute(test_context, {"title": "Add multiply", "description": "..."})

        assert result.success
        assert isinstance(result.data["plan"], PlanArtifact)

    def test_prose_preamble_before_fenced_json_is_parsed(self, test_context):
        """The model doesn't always follow 'respond with ONLY JSON' exactly - it may add
        reasoning text before the fenced block. The parser must handle that, not just the
        ideal case."""
        with_preamble = f"Based on my exploration, here is the plan:\n\n```json\n{VALID_PLAN_JSON}\n```"
        agent = PlannerAgent(MockChatClient(content=with_preamble))

        result = agent.execute(test_context, {"title": "Add multiply", "description": "..."})

        assert result.success, f"Planner failed: {result.errors}, raw: {result.data}"
        assert isinstance(result.data["plan"], PlanArtifact)

    def test_prose_preamble_before_unfenced_json_is_parsed(self, test_context):
        """Same as above, but with no markdown fence at all - just raw JSON after prose."""
        with_preamble = f"Here is my plan:\n\n{VALID_PLAN_JSON}"
        agent = PlannerAgent(MockChatClient(content=with_preamble))

        result = agent.execute(test_context, {"title": "Add multiply", "description": "..."})

        assert result.success, f"Planner failed: {result.errors}, raw: {result.data}"
        assert isinstance(result.data["plan"], PlanArtifact)

    def test_invalid_json_fails_gracefully(self, test_context):
        agent = PlannerAgent(MockChatClient(content="Sure, here's my plan: step one, step two."))

        result = agent.execute(test_context, {"title": "Add multiply", "description": "..."})

        assert not result.success
        assert result.errors
        assert "raw_response" in result.data


@pytest.mark.integration
class TestPlannerAgentWithBedrock:
    """Integration test with a real Bedrock call - verifies the LLM actually follows
    the JSON-only instruction in practice, not just that our parsing code works."""

    def test_produces_valid_plan(self, bedrock_llm_client, test_context):
        agent = PlannerAgent(bedrock_llm_client)

        result = agent.execute(test_context, {
            "title": "Add a multiply function",
            "description": "Add a multiply(a, b) function to calculator.py that returns a * b, "
                            "and add a test for it.",
        })

        print(agent.messages)

        assert result.success, f"Planner failed: {result.errors}, raw: {result.data}"
        plan = result.data["plan"]
        assert isinstance(plan, PlanArtifact)
        assert plan.work_item_id == test_context.work_item_id
        assert len(plan.steps) >= 1
