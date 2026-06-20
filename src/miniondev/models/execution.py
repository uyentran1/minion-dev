"""
Data contract produced by the Executor agent after implementing a PlanArtifact.
"""
from typing import List
from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    """
    Result of executing a plan. modified_files and errors are derived from actual tool
    execution (ground truth), not parsed from the LLM's response - only summary is.
    """
    work_item_id: str
    modified_files: List[str] = Field(default_factory=list)
    summary: str
    errors: List[str] = Field(default_factory=list)
