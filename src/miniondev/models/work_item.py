"""
Data contract for a unit of work fed into the orchestrator (a ticket, CLI prompt, etc.).
"""
from pydantic import BaseModel


class WorkItem(BaseModel):
    id: str
    title: str
    description: str
