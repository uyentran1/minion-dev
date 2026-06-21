"""
Finalizer - turns a successful ExecutionResult into a git branch, commit, push, and PR.

Deliberately not an Agent subclass: git/PR operations are exactly the kind of hard-to-reverse,
shared-state actions that should be deterministic and explicitly opted into via flags, not
decided by an LLM tool-calling loop. Commit/PR text is templated from data the Planner/Executor
already produced rather than another LLM call. It exposes the same execute(context, input_data)
-> AgentResult shape as the other agents purely by duck typing, so the Orchestrator can wire it
in the same way.
"""
import shlex
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from miniondev.agent.base import AgentContext, AgentResult
from miniondev.models import ExecutionResult, FinalizationResult, PlanArtifact
from miniondev.tools import get_registry


@dataclass
class FinalizerOptions:
    enable_commit: bool = False
    enable_push: bool = False
    enable_pr: bool = False
    base_branch: str = "main"

    def __post_init__(self):
        # Each step depends on the previous one having happened (can't open a PR for a
        # branch that was never pushed, can't push a branch that was never committed) -
        # enforce that here so callers can't end up with a silent no-op flag combination.
        if self.enable_pr:
            self.enable_push = True
        if self.enable_push:
            self.enable_commit = True


class FinalizerAgent:
    def __init__(self, options: Optional[FinalizerOptions] = None):
        self.options = options or FinalizerOptions()
        self.progress_callback = None

    def execute(self, context: AgentContext, input_data: Dict[str, Any]) -> AgentResult:
        plan: PlanArtifact = input_data["plan"]
        execution_result: ExecutionResult = input_data["execution_result"]

        branch_name = self._branch_name(context.work_item_id, plan.summary)

        if not self.options.enable_commit:
            message = "Dry run: no git changes made. Pass --enable-commit to commit."
            self._report(message)
            result = FinalizationResult(
                work_item_id=context.work_item_id,
                dry_run=True,
                branch_name=branch_name,
                message=message,
            )
            return AgentResult(success=True, message=message, data={"finalization_result": result})

        self._report(f"creating branch {branch_name}")
        ok, err = self._run(f"git checkout -b {shlex.quote(branch_name)}")
        if not ok:
            return self._fail(context.work_item_id, branch_name, [err])

        if execution_result.modified_files:
            file_args = " ".join(shlex.quote(f) for f in execution_result.modified_files)
            ok, err = self._run(f"git add {file_args}")
            if not ok:
                return self._fail(context.work_item_id, branch_name, [err])

        commit_message = self._commit_message(plan)
        self._report("committing changes")
        ok, err = self._run(f"git commit -m {shlex.quote(commit_message)}")
        if not ok:
            return self._fail(context.work_item_id, branch_name, [err])

        pushed = False
        pr_url = None
        errors = []

        if self.options.enable_push:
            self._report(f"pushing branch {branch_name}")
            ok, err = self._run(f"git push -u origin {shlex.quote(branch_name)}")
            if not ok:
                return self._fail(context.work_item_id, branch_name, [err], committed=True)
            pushed = True

            if self.options.enable_pr:
                self._report("creating pull request")
                pr_body = self._pr_body(plan, execution_result)
                ok, output = self._run(
                    f"gh pr create --title {shlex.quote(commit_message)} "
                    f"--body {shlex.quote(pr_body)} "
                    f"--base {shlex.quote(self.options.base_branch)} "
                    f"--head {shlex.quote(branch_name)}"
                )
                if not ok:
                    errors.append(f"PR creation failed: {output}")
                else:
                    pr_url = self._extract_pr_url(output)

        message = f"Committed to branch {branch_name}"
        if pushed:
            message += ", pushed"
        if pr_url:
            message += f", PR: {pr_url}"

        result = FinalizationResult(
            work_item_id=context.work_item_id,
            dry_run=False,
            branch_name=branch_name,
            committed=True,
            pushed=pushed,
            pr_url=pr_url,
            message=message,
            errors=errors,
        )
        return AgentResult(
            success=not errors, message=message, data={"finalization_result": result}, errors=errors
        )

    def _branch_name(self, work_item_id: str, summary: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")[:40]
        work_item_slug = re.sub(r"[^a-zA-Z0-9]+", "-", work_item_id).strip("-")[:8]
        return f"minion/{work_item_slug}-{slug}" if slug else f"minion/{work_item_slug}"

    def _commit_message(self, plan: PlanArtifact) -> str:
        return plan.summary.strip().splitlines()[0][:72]

    def _pr_body(self, plan: PlanArtifact, execution_result: ExecutionResult) -> str:
        steps = "\n".join(f"- {s.description}" for s in plan.steps)
        criteria = "\n".join(f"- {c}" for c in plan.acceptance_criteria) or "- (none specified)"
        return (
            f"## Summary\n{plan.summary}\n\n"
            f"## Steps\n{steps}\n\n"
            f"## Acceptance criteria\n{criteria}\n\n"
            f"## Execution notes\n{execution_result.summary}"
        )

    def _run(self, command: str) -> Tuple[bool, str]:
        result = get_registry().execute_tool("run_command", {"command": command})
        if not result.success:
            return False, result.error or "command execution error"

        output = result.output
        if isinstance(output, dict):
            if output.get("success"):
                return True, output.get("stdout", "")
            return False, output.get("stderr") or output.get("stdout") or "command failed"
        return True, str(output)

    @staticmethod
    def _extract_pr_url(output: str) -> Optional[str]:
        lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
        return lines[-1] if lines else None

    def _fail(self, work_item_id: str, branch_name: str, errors: list, committed: bool = False) -> AgentResult:
        message = "Finalization failed"
        result = FinalizationResult(
            work_item_id=work_item_id,
            dry_run=False,
            branch_name=branch_name,
            committed=committed,
            message=message,
            errors=errors,
        )
        return AgentResult(success=False, message=message, data={"finalization_result": result}, errors=errors)

    def _report(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(f"[finalizer] {message}")
