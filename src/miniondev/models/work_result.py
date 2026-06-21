"""
Data contract for the orchestrator's end-to-end result of processing a WorkItem.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from miniondev.models.plan import PlanArtifact
from miniondev.models.execution import ExecutionResult
from miniondev.models.finalization import FinalizationResult


class WorkResult(BaseModel):
    work_item_id: str
    success: bool
    message: str
    plan: Optional[PlanArtifact] = None
    execution_result: Optional[ExecutionResult] = None
    finalization_result: Optional[FinalizationResult] = None
    errors: List[str] = Field(default_factory=list)
