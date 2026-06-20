"""
Planner agent - converts a work item description into a structured PlanArtifact.
"""
import json
import re
from typing import Any, Dict, List, Optional

from miniondev.agent.base import Agent, AgentContext, AgentResult, AgentType
from miniondev.llm.client import ChatClient
from miniondev.models import PlanArtifact
from miniondev.tools import get_registry

# Planner only looks around the repo to inform its plan - it must not modify
# files or run commands. Making changes is the Executor's job.
PLANNER_TOOL_NAMES = ["read_file", "list_directory", "search_files", "file_exists", "get_file_info"]

PLANNER_SYSTEM_PROMPT = """You are the Planner in an autonomous coding pipeline. Given a work \
item (title and description), break it down into an ordered list of concrete, atomic \
implementation steps.

You may use read-only tools (read_file, list_directory, search_files, file_exists, \
get_file_info) to explore the repository before planning. You cannot modify files or run \
commands - that is the Executor's job.

A file mentioned in the work item NOT existing yet is an expected, common case - it usually \
means a step in your plan should create it. Do not keep searching for a file under different \
names or locations once one targeted search has confirmed it is missing; move on to planning. \
Use at most 3-4 tool calls total to orient yourself, then produce your final JSON plan.

When you are done planning, respond with ONLY a JSON object (no markdown fences, no prose) \
matching this shape:
{
  "summary": "one paragraph describing what this plan accomplishes",
  "steps": [
    {"step_number": 1, "description": "...", "target_files": ["..."], "rationale": "..."}
  ],
  "acceptance_criteria": ["...", "..."]
}

target_files and rationale are optional per step. Keep steps atomic - each step should be \
implementable as a single focused change. Do not include a work_item_id field, it is added \
automatically."""


class PlannerAgent(Agent):
    """
    Converts a work item (title + description) into a PlanArtifact: an ordered list of
    natural-language steps the Executor agent will later implement.
    """

    def __init__(self, llm_client: ChatClient):
        super().__init__(llm_client, AgentType.PLANNER)
        self.max_turns = 15  # Headroom for repo exploration before producing the final plan

    def get_system_prompt(self) -> str:
        return PLANNER_SYSTEM_PROMPT

    def get_available_tools(self) -> Optional[List]:
        registry = get_registry()
        return [
            definition
            for definition in registry.get_tool_definitions()
            if definition.name in PLANNER_TOOL_NAMES
        ]

    def execute(self, context: AgentContext, input_data: Dict[str, Any]) -> AgentResult:
        return self.run_conversation_loop(context, input_data)

    def _build_initial_prompt(self, input_data: Dict[str, Any]) -> str:
        title = input_data.get("title", "")
        description = input_data.get("description", "")
        return f"Work item title: {title}\n\nDescription:\n{description}"

    def _extract_final_result(self) -> AgentResult:
        if not self.messages or self.messages[-1].role != "assistant":
            return AgentResult(
                success=False,
                message="No final response from agent",
                errors=["Missing final response"],
            )

        raw_content = self.messages[-1].content
        try:
            parsed = json.loads(self._extract_json(raw_content))
            plan = PlanArtifact(work_item_id=self.context.work_item_id, **parsed)
        except Exception as e:
            self.logger.error(f"Failed to parse plan from LLM response: {e}")
            return AgentResult(
                success=False,
                message="Planner produced an invalid plan",
                errors=[str(e)],
                data={"raw_response": raw_content},
            )

        return AgentResult(
            success=True,
            message=plan.summary,
            data={"plan": plan},
        )

    _FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

    @classmethod
    def _extract_json(cls, text: str) -> str:
        """
        Pull a JSON object out of an LLM response that may include prose around it,
        despite being told to respond with only JSON - models don't always comply exactly.
        """
        text = text.strip()

        fence_match = cls._FENCE_RE.search(text)
        if fence_match:
            return fence_match.group(1).strip()

        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]

        return text
