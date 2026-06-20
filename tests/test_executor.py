"""
Test the Executor agent
"""
import os
import pytest

from miniondev.agent import ExecutorAgent, AgentType
from miniondev.llm.client import MockChatClient, ToolCall
from miniondev.models import PlanArtifact, PlanStep, ExecutionResult


def make_plan(work_item_id="test-001"):
    return PlanArtifact(
        work_item_id=work_item_id,
        summary="Add multiply function",
        steps=[
            PlanStep(step_number=1, description="Add multiply() to calculator.py", target_files=["calculator.py"]),
            PlanStep(step_number=2, description="Add tests for multiply()"),
        ],
        acceptance_criteria=["multiply(2, 3) returns 6"],
    )


class TestExecutorAgent:
    """Test ExecutorAgent basics"""

    def test_agent_type(self):
        agent = ExecutorAgent(MockChatClient())
        assert agent.agent_type == AgentType.EXECUTOR

    def test_has_full_tool_access(self):
        """Unlike the Planner, the Executor needs write/run tools to implement the plan"""
        agent = ExecutorAgent(MockChatClient())
        assert agent.get_available_tools() is None

    def test_initial_prompt_includes_plan_steps(self):
        agent = ExecutorAgent(MockChatClient())
        plan = make_plan()

        prompt = agent._build_initial_prompt({"plan": plan})

        assert "Add multiply() to calculator.py" in prompt
        assert "multiply(2, 3) returns 6" in prompt


class TestExecutorToolTracking:
    """Test that modified_files/errors are derived from real tool execution, not LLM self-report"""

    def test_successful_write_file_is_tracked(self, temp_dir):
        agent = ExecutorAgent(MockChatClient())
        file_path = os.path.join(temp_dir, "calculator.py")

        result = agent._execute_tool_call(ToolCall(
            id="1",
            name="write_file",
            arguments={"file_path": file_path, "content": "def multiply(a, b): return a * b"},
        ))

        assert "Successfully wrote" in result
        assert file_path in agent._modified_files

    def test_failed_tool_call_is_recorded_as_error(self):
        agent = ExecutorAgent(MockChatClient())

        result = agent._execute_tool_call(ToolCall(
            id="1", name="read_file", arguments={"file_path": "/nonexistent/path.txt"}
        ))

        assert "Tool execution failed" in result
        assert agent._tool_errors
        assert "read_file" in agent._tool_errors[0]

    def test_read_only_tool_is_not_tracked_as_modified(self, temp_file):
        agent = ExecutorAgent(MockChatClient())

        agent._execute_tool_call(ToolCall(id="1", name="read_file", arguments={"file_path": temp_file}))

        assert agent._modified_files == []


class TestExecutorExecution:
    """Test the full execute() flow"""

    def test_basic_execution_produces_execution_result(self, test_context):
        agent = ExecutorAgent(MockChatClient(content="Done. All steps implemented."))
        plan = make_plan(work_item_id=test_context.work_item_id)

        result = agent.execute(test_context, {"plan": plan})

        assert result.success
        exec_result = result.data["execution_result"]
        assert isinstance(exec_result, ExecutionResult)
        assert exec_result.work_item_id == test_context.work_item_id
        assert exec_result.summary == "Done. All steps implemented."
        assert exec_result.errors == []


@pytest.mark.integration
class TestExecutorAgentWithBedrock:
    """Integration test with a real Bedrock call - verifies the Executor can actually
    implement a plan step end-to-end, not just that our bookkeeping code works."""

    def test_implements_plan_and_creates_file(self, bedrock_llm_client, test_context, temp_dir):
        agent = ExecutorAgent(bedrock_llm_client)
        file_path = os.path.join(temp_dir, "calculator.py")
        plan = PlanArtifact(
            work_item_id=test_context.work_item_id,
            summary="Add multiply function to calculator module",
            steps=[
                PlanStep(
                    step_number=1,
                    description=f"Create a file at {file_path} with a multiply(a, b) function that returns a * b",
                    target_files=[file_path],
                )
            ],
            acceptance_criteria=[f"{file_path} exists and defines a multiply(a, b) function"],
        )

        result = agent.execute(test_context, {"plan": plan})

        assert result.success, f"Executor failed: {result.errors}"
        assert os.path.exists(file_path)
        with open(file_path) as f:
            content = f.read()
        assert "multiply" in content
