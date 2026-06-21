"""
Orchestrator - sequences the Planner -> Executor pipeline for a single work item.
"""
import uuid

from miniondev.agent import AgentContext, PlannerAgent, ExecutorAgent
from miniondev.models import WorkItem, WorkResult


class Orchestrator:
    """
    Coordinates Planner -> Executor for a work item. Agents are injected rather than
    constructed internally, so callers control their configuration (e.g. which LLM
    client) and tests can inject agents backed by different mock responses per phase.
    """

    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent):
        self.planner = planner
        self.executor = executor

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

        return WorkResult(
            work_item_id=work_item.id,
            success=True,
            message=execution_result.summary,
            plan=plan,
            execution_result=execution_result,
        )
