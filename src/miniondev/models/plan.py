"""
Data contracts produced by the Planner agent and consumed by the Executor agent.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """
    A single atomic unit of work within a plan.

    Intentionally describes *intent*, not the tool calls needed to fulfill it -
    the Executor agent decides how to implement each step at execution time.
    """
    step_number: int
    description: str
    target_files: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None


class PlanArtifact(BaseModel):
    """Structured plan produced by the Planner agent from a work item."""
    work_item_id: str
    summary: str
    steps: List[PlanStep] = Field(min_length=1)
    acceptance_criteria: List[str] = Field(default_factory=list)
