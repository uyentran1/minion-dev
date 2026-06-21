"""
Executor agent - implements a PlanArtifact by making tool calls (file edits, commands).
"""
from typing import Any, Dict

from miniondev.agent.base import Agent, AgentContext, AgentResult, AgentType
from miniondev.llm.client import ChatClient, ToolCall
from miniondev.models import ExecutionResult, PlanArtifact
from miniondev.tools import get_registry

# Tool calls whose first path-like argument represents a file/directory being created or
# changed. Used to derive modified_files from ground truth instead of asking the LLM.
WRITE_TOOL_PATH_ARGS = {
    "write_file": "file_path",
    "create_directory": "directory_path",
}

EXECUTOR_SYSTEM_PROMPT = """You are the Executor in an autonomous coding pipeline. You are \
given a plan (an ordered list of steps) produced by the Planner agent, and your job is to \
implement it using the available tools: read_file, write_file, create_directory, \
list_directory, search_files, file_exists, get_file_info, run_command.

Work through the plan steps in order. Read a file before modifying it so you don't overwrite \
content you didn't intend to change. After making changes, use run_command to run any \
relevant tests (e.g. pytest) to verify your work, when appropriate.

When you have implemented all steps and verified your work, respond with a concise plain-text \
summary of what you did and the result of any verification you ran. Do not respond in JSON - \
a plain summary is all that's needed."""


class ExecutorAgent(Agent):
    """
    Implements a PlanArtifact's steps via tool calls. Unlike the Planner, has full tool
    access (including write_file and run_command) since making changes is its job.
    """

    def __init__(self, llm_client: ChatClient):
        super().__init__(llm_client, AgentType.EXECUTOR)
        self.max_turns = 40  # Implementing multiple steps needs more turns than planning
        self._modified_files = []
        self._tool_errors = []

    def get_system_prompt(self) -> str:
        return EXECUTOR_SYSTEM_PROMPT

    def execute(self, context: AgentContext, input_data: Dict[str, Any]) -> AgentResult:
        self._modified_files = []
        self._tool_errors = []
        return self.run_conversation_loop(context, input_data)

    def _build_initial_prompt(self, input_data: Dict[str, Any]) -> str:
        plan: PlanArtifact = input_data["plan"]

        steps_text = "\n".join(
            f"{step.step_number}. {step.description}"
            + (f" (target files: {', '.join(step.target_files)})" if step.target_files else "")
            for step in plan.steps
        )
        criteria_text = "\n".join(f"- {c}" for c in plan.acceptance_criteria)

        return (
            f"Plan summary: {plan.summary}\n\n"
            f"Steps to implement:\n{steps_text}\n\n"
            f"Acceptance criteria:\n{criteria_text}"
        )

    def _execute_tool_call(self, tool_call: ToolCall) -> tuple[str, bool]:
        registry = get_registry()
        result = registry.execute_tool(tool_call.name, tool_call.arguments)

        if not result.success:
            self._tool_errors.append(f"{tool_call.name}: {result.error}")
            return f"Tool execution failed: {result.error}", True

        path_arg = WRITE_TOOL_PATH_ARGS.get(tool_call.name)
        if path_arg:
            path = tool_call.arguments.get(path_arg)
            if path and path not in self._modified_files:
                self._modified_files.append(path)

        return str(result.output), False

    def _extract_final_result(self) -> AgentResult:
        if not self.messages or self.messages[-1].role != "assistant":
            return AgentResult(
                success=False,
                message="No final response from agent",
                errors=["Missing final response"],
            )

        execution_result = ExecutionResult(
            work_item_id=self.context.work_item_id,
            modified_files=self._modified_files,
            summary=self.messages[-1].content,
            errors=self._tool_errors,
        )

        return AgentResult(
            success=not self._tool_errors,
            message=execution_result.summary,
            data={"execution_result": execution_result},
            errors=self._tool_errors,
        )
