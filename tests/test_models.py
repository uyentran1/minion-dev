"""
Test data contracts (PlanArtifact, PlanStep)
"""
import pytest
from pydantic import ValidationError

from miniondev.models import PlanArtifact, PlanStep


class TestPlanStep:
    """Test PlanStep validation and defaults"""

    def test_minimal_step(self):
        step = PlanStep(step_number=1, description="Add multiply() to calculator.py")

        assert step.step_number == 1
        assert step.target_files == []
        assert step.rationale is None

    def test_full_step(self):
        step = PlanStep(
            step_number=1,
            description="Add multiply() to calculator.py",
            target_files=["calculator.py"],
            rationale="Required by the ticket's acceptance criteria",
        )

        assert step.target_files == ["calculator.py"]
        assert step.rationale == "Required by the ticket's acceptance criteria"


class TestPlanArtifact:
    """Test PlanArtifact validation and defaults"""

    def test_valid_plan(self):
        plan = PlanArtifact(
            work_item_id="TICKET-123",
            summary="Add multiply function to calculator module",
            steps=[
                PlanStep(step_number=1, description="Add multiply() to calculator.py"),
                PlanStep(step_number=2, description="Add tests for multiply()"),
            ],
        )

        assert plan.work_item_id == "TICKET-123"
        assert len(plan.steps) == 2
        assert plan.acceptance_criteria == []

    def test_empty_steps_rejected(self):
        with pytest.raises(ValidationError):
            PlanArtifact(
                work_item_id="TICKET-123",
                summary="Empty plan",
                steps=[],
            )

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            PlanArtifact(
                summary="Missing work_item_id",
                steps=[PlanStep(step_number=1, description="Do something")],
            )

    def test_parses_from_llm_style_json(self):
        """PlanArtifact's real entry point is LLM-returned JSON, not Python kwargs"""
        raw_json = """
        {
            "work_item_id": "TICKET-123",
            "summary": "Add multiply function to calculator module",
            "steps": [
                {"step_number": 1, "description": "Add multiply() to calculator.py"},
                {"step_number": 2, "description": "Add tests for multiply()"}
            ],
            "acceptance_criteria": ["multiply(2, 3) returns 6", "tests pass"]
        }
        """
        plan = PlanArtifact.model_validate_json(raw_json)

        assert plan.work_item_id == "TICKET-123"
        assert len(plan.steps) == 2
        assert plan.steps[0].description == "Add multiply() to calculator.py"
        assert plan.acceptance_criteria == ["multiply(2, 3) returns 6", "tests pass"]
