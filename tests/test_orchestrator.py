"""
Test the Orchestrator
"""
from miniondev.agent import AgentResult, ExecutorAgent, PlannerAgent
from miniondev.llm.client import MockChatClient
from miniondev.models import WorkItem, WorkResult
from miniondev.orchestrator import Orchestrator

VALID_PLAN_JSON = """{
    "summary": "Add a multiply function to the calculator module",
    "steps": [
        {"step_number": 1, "description": "Add multiply() to calculator.py", "target_files": ["calculator.py"]}
    ],
    "acceptance_criteria": ["multiply(2, 3) returns 6"]
}"""


class _FakeAgent:
    """Minimal stand-in for an Agent - Orchestrator only relies on execute(context, input_data) -> AgentResult"""

    def __init__(self, result: AgentResult):
        self._result = result
        self.called = False

    def execute(self, context, input_data):
        self.called = True
        return self._result


def make_work_item():
    return WorkItem(id="WI-1", title="Add multiply", description="Add multiply(a, b) to calculator.py")


class TestOrchestratorHappyPath:
    def test_planner_and_executor_run_in_sequence(self):
        planner = PlannerAgent(MockChatClient(content=VALID_PLAN_JSON))
        executor = ExecutorAgent(MockChatClient(content="Implemented multiply()."))
        orchestrator = Orchestrator(planner=planner, executor=executor)

        result = orchestrator.process_work_item(make_work_item())

        assert isinstance(result, WorkResult)
        assert result.success
        assert result.work_item_id == "WI-1"
        assert result.plan is not None
        assert result.execution_result is not None
        assert result.execution_result.summary == "Implemented multiply()."


class TestOrchestratorFailurePropagation:
    def test_planner_failure_short_circuits_before_executor(self):
        planner = PlannerAgent(MockChatClient(content="not valid json"))
        executor = _FakeAgent(AgentResult(success=True, message="should not run"))
        orchestrator = Orchestrator(planner=planner, executor=executor)

        result = orchestrator.process_work_item(make_work_item())

        assert not result.success
        assert result.plan is None
        assert result.execution_result is None
        assert not executor.called

    def test_executor_failure_is_reported_with_plan_attached(self):
        planner = PlannerAgent(MockChatClient(content=VALID_PLAN_JSON))
        executor = _FakeAgent(AgentResult(success=False, message="Tool failed", errors=["boom"]))
        orchestrator = Orchestrator(planner=planner, executor=executor)

        result = orchestrator.process_work_item(make_work_item())

        assert not result.success
        assert result.plan is not None  # Planner's output is preserved even though execution failed
        assert result.execution_result is None
        assert "boom" in result.errors
