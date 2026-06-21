"""
Data contract produced by the Finalizer after (optionally) committing/pushing/opening a PR.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class FinalizationResult(BaseModel):
    work_item_id: str
    dry_run: bool
    branch_name: str
    committed: bool = False
    pushed: bool = False
    pr_url: Optional[str] = None
    message: str
    errors: List[str] = Field(default_factory=list)
