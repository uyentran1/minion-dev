"""
Test the Finalizer agent
"""
import os
import subprocess
import pytest

from miniondev.agent import FinalizerAgent, FinalizerOptions
from miniondev.models import PlanArtifact, PlanStep, ExecutionResult


def make_plan(work_item_id="wi-1", summary="Add multiply function to calculator module"):
    return PlanArtifact(
        work_item_id=work_item_id,
        summary=summary,
        steps=[PlanStep(step_number=1, description="Add multiply() to calculator.py")],
        acceptance_criteria=["multiply(2, 3) returns 6"],
    )


def make_execution_result(work_item_id="wi-1", modified_files=None):
    return ExecutionResult(
        work_item_id=work_item_id,
        modified_files=modified_files or [],
        summary="Implemented multiply().",
    )


@pytest.fixture
def git_repo(temp_dir):
    """A real git repo with an initial commit, chdir'd into for the duration of the test."""
    subprocess.run(["git", "init", "-q"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_dir, check=True)
    with open(os.path.join(temp_dir, "README.md"), "w") as f:
        f.write("init\n")
    subprocess.run(["git", "add", "README.md"], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=temp_dir, check=True)

    original_cwd = os.getcwd()
    os.chdir(temp_dir)
    try:
        yield temp_dir
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def git_repo_with_remote(git_repo, tmp_path_factory):
    """git_repo with a local bare repo configured as 'origin', so push doesn't need GitHub auth."""
    bare_dir = tmp_path_factory.mktemp("bare") / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare_dir)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare_dir)], cwd=git_repo, check=True)
    return git_repo


class TestFinalizerDryRun:
    def test_dry_run_by_default_makes_no_git_changes(self, git_repo, test_context):
        agent = FinalizerAgent()  # enable_commit defaults to False
        plan = make_plan(work_item_id=test_context.work_item_id)
        execution_result = make_execution_result(work_item_id=test_context.work_item_id)

        result = agent.execute(test_context, {"plan": plan, "execution_result": execution_result})

        assert result.success
        finalization = result.data["finalization_result"]
        assert finalization.dry_run is True
        assert finalization.committed is False

        branches = subprocess.run(["git", "branch"], cwd=git_repo, capture_output=True, text=True).stdout
        assert finalization.branch_name not in branches


class TestFinalizerOptionsNormalization:
    """enable_pr/enable_push must imply the steps they depend on, or they'd silently no-op"""

    def test_enable_pr_implies_enable_push_and_commit(self):
        options = FinalizerOptions(enable_pr=True)
        assert options.enable_push is True
        assert options.enable_commit is True

    def test_enable_push_implies_enable_commit(self):
        options = FinalizerOptions(enable_push=True)
        assert options.enable_commit is True

    def test_enable_commit_alone_does_not_enable_push_or_pr(self):
        options = FinalizerOptions(enable_commit=True)
        assert options.enable_push is False
        assert options.enable_pr is False


class TestFinalizerTemplating:
    def test_branch_name_is_slugified_and_namespaced(self):
        agent = FinalizerAgent()
        name = agent._branch_name("wi-123", "Add a Multiply Function!!")

        assert name.startswith("minion/wi-123-")
        assert "add-a-multiply-function" in name
        assert " " not in name
        assert "!" not in name

    def test_commit_message_is_first_line_truncated(self):
        agent = FinalizerAgent()
        plan = make_plan(summary="This is the first line\nSecond line with more detail")

        assert agent._commit_message(plan) == "This is the first line"

    def test_pr_body_includes_steps_and_criteria(self):
        agent = FinalizerAgent()
        body = agent._pr_body(make_plan(), make_execution_result())

        assert "Add multiply() to calculator.py" in body
        assert "multiply(2, 3) returns 6" in body
        assert "Implemented multiply()." in body


class TestFinalizerCommit:
    def test_enable_commit_creates_branch_and_commit(self, git_repo, test_context):
        agent = FinalizerAgent(FinalizerOptions(enable_commit=True))
        plan = make_plan(work_item_id=test_context.work_item_id)

        with open(os.path.join(git_repo, "calculator.py"), "w") as f:
            f.write("def multiply(a, b):\n    return a * b\n")
        execution_result = make_execution_result(
            work_item_id=test_context.work_item_id, modified_files=["calculator.py"]
        )

        result = agent.execute(test_context, {"plan": plan, "execution_result": execution_result})

        assert result.success, result.errors
        finalization = result.data["finalization_result"]
        assert finalization.committed
        assert not finalization.pushed

        branches = subprocess.run(["git", "branch"], cwd=git_repo, capture_output=True, text=True).stdout
        assert finalization.branch_name in branches

        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=git_repo, capture_output=True, text=True
        ).stdout
        assert log.strip() == agent._commit_message(plan)

    def test_failed_git_command_is_reported_not_swallowed(self, git_repo, test_context):
        """Checking out a branch name that already exists should fail cleanly, not silently succeed."""
        subprocess.run(["git", "branch", "minion/dup-test"], cwd=git_repo, check=True)

        agent = FinalizerAgent(FinalizerOptions(enable_commit=True))
        agent._branch_name = lambda work_item_id, summary: "minion/dup-test"  # force a collision

        result = agent.execute(test_context, {"plan": make_plan(), "execution_result": make_execution_result()})

        assert not result.success
        assert result.errors


class TestFinalizerPush:
    def test_enable_push_pushes_to_remote(self, git_repo_with_remote, test_context):
        agent = FinalizerAgent(FinalizerOptions(enable_commit=True, enable_push=True))
        plan = make_plan(work_item_id=test_context.work_item_id)

        with open(os.path.join(git_repo_with_remote, "calculator.py"), "w") as f:
            f.write("def multiply(a, b):\n    return a * b\n")
        execution_result = make_execution_result(
            work_item_id=test_context.work_item_id, modified_files=["calculator.py"]
        )

        result = agent.execute(test_context, {"plan": plan, "execution_result": execution_result})

        assert result.success, result.errors
        finalization = result.data["finalization_result"]
        assert finalization.pushed

        remote_branches = subprocess.run(
            ["git", "branch", "-r"], cwd=git_repo_with_remote, capture_output=True, text=True
        ).stdout
        assert finalization.branch_name in remote_branches


@pytest.mark.integration
class TestFinalizerPrCreation:
    """Exercises the real `gh pr create` path. Without gh authenticated against a real
    GitHub remote, this is expected to fail - what matters is that the failure is
    reported cleanly (not swallowed) and doesn't erase the commit/push that already
    succeeded."""

    def test_gh_pr_create_failure_is_reported_without_losing_prior_progress(
        self, git_repo_with_remote, test_context
    ):
        agent = FinalizerAgent(FinalizerOptions(enable_commit=True, enable_push=True, enable_pr=True))
        plan = make_plan(work_item_id=test_context.work_item_id)

        with open(os.path.join(git_repo_with_remote, "calculator.py"), "w") as f:
            f.write("def multiply(a, b):\n    return a * b\n")
        execution_result = make_execution_result(
            work_item_id=test_context.work_item_id, modified_files=["calculator.py"]
        )

        result = agent.execute(test_context, {"plan": plan, "execution_result": execution_result})

        finalization = result.data["finalization_result"]
        assert finalization.committed
        assert finalization.pushed
        if not result.success:
            assert finalization.errors
