"""
Orchestrator - sequences the Planner -> Executor -> Finalizer pipeline for a work item.
"""
import uuid
from typing import Optional

from miniondev.agent import AgentContext, PlannerAgent, ExecutorAgent, FinalizerAgent
from miniondev.models import WorkItem, WorkResult


class Orchestrator:
    """
    Coordinates Planner -> Executor -> (optional) Finalizer for a work item. Agents are
    injected rather than constructed internally, so callers control their configuration
    (e.g. which LLM client) and tests can inject agents backed by different mock
    responses per phase. Finalizer is optional since not every caller wants git/PR
    side effects (e.g. unit tests, or a dry-run-only workflow).
    """

    def __init__(
        self,
        planner: PlannerAgent,
        executor: ExecutorAgent,
        finalizer: Optional[FinalizerAgent] = None,
    ):
        self.planner = planner
        self.executor = executor
        self.finalizer = finalizer

    def process_work_item(self, work_item: WorkItem) -> WorkResult:
        context = AgentContext(work_item_id=work_item.id, session_id=str(uuid.uuid4()))

        plan_result = self.planner.execute(context, {
            "title": work_item.title,
            "description": work_item.description,
        })
        if not plan_result.success:
            return WorkResult(
                work_item_id=work_item.id,
                success=False,
                message=plan_result.message,
                errors=plan_result.errors,
            )
        plan = plan_result.data["plan"]

        execution_agent_result = self.executor.execute(context, {"plan": plan})
        if not execution_agent_result.success:
            return WorkResult(
                work_item_id=work_item.id,
                success=False,
                message=execution_agent_result.message,
                plan=plan,
                errors=execution_agent_result.errors,
            )
        execution_result = execution_agent_result.data["execution_result"]

        if not self.finalizer:
            return WorkResult(
                work_item_id=work_item.id,
                success=True,
                message=execution_result.summary,
                plan=plan,
                execution_result=execution_result,
            )

        finalize_agent_result = self.finalizer.execute(context, {
            "plan": plan,
            "execution_result": execution_result,
        })
        if not finalize_agent_result.success:
            return WorkResult(
                work_item_id=work_item.id,
                success=False,
                message=finalize_agent_result.message,
                plan=plan,
                execution_result=execution_result,
                finalization_result=finalize_agent_result.data.get("finalization_result"),
                errors=finalize_agent_result.errors,
            )
        finalization_result = finalize_agent_result.data["finalization_result"]

        return WorkResult(
            work_item_id=work_item.id,
            success=True,
            message=finalization_result.message,
            plan=plan,
            execution_result=execution_result,
            finalization_result=finalization_result,
        )
