# MinionDev

MinionDev is an autonomous coding pipeline inspired by Stripe Minions.
From ticket to PR with zero human touch - automates the entire software delivery workflow from Jira ticket pickup to pull request submission.

## What MinionDev does

- **Reads** Jira tickets (or CLI prompts)
- **Plans** implementation with structured breakdown
- **Codes** solution using AI agents with tool access
- **Tests** and validates the implementation
- **Commits** and opens pull request for review

## Architecture

- **Deterministic orchestrator** with explicit workflow states
- **Planner agent** - converts requirements to structured implementation plan
- **Executor agent** - implements plan through iterative coding with tool calls
- **Finalizer** - handles git operations, commits, and PR creation
- **Tool registry** - file operations, command execution, directory listing
- **LLM backend** - AWS Bedrock (Claude) with mock fallback for development

## Quick start

1. Install dependencies:

```bash
pip install -e .
```

2. Configure AWS Bedrock credentials (optional - mock mode available):

```bash
# Option 1: Bearer Token (Recommended)
export AWS_BEARER_TOKEN_BEDROCK="your-bearer-token"

# Option 2: Environment File
cp .env.example .env
# Add your AWS_BEARER_TOKEN_BEDROCK to .env
```

3. Test the setup:

```bash
source .venv/bin/activate
pytest tests/test_llm_client.py -m integration
```

4. Run MinionDev:

```bash
python -m miniondev.cli run --prompt "Add healthcheck endpoint and tests" --repo .
```

## Safe default

By default, the finalizer runs in dry-run mode. It does not commit/push/open PR unless you pass:

- `--enable-commit`
- `--enable-push`
- `--enable-pr`

## Future Jira enhancement

Add a Jira intake adapter that converts a ticket into the same `WorkItem` object used by the orchestrator. No orchestrator redesign is required.

## Future work: additional agents

The pipeline is intentionally not limited to Planner/Executor/Finalizer. Candidates for
future agents, plugged in as additional Orchestrator phases (most naturally between
Executor and Finalizer, gating whether finalization proceeds):

- **Reviewer agent** - reviews the Executor's changes against the plan and acceptance
  criteria before anything is committed; can block finalization on serious issues.
- **Security reviewer** - scans the diff for obvious issues (hardcoded secrets, injection
  patterns) as a specialized reviewer.
- **Validator/Tester agent** - runs the full test suite/linting independently, rather than
  relying solely on the Executor's own self-verification.
- **Documentation agent** - updates README/CHANGELOG/docstrings to reflect the change.

None of these are implemented yet. The existing `Agent`/`AgentResult` interface and the
Orchestrator's dependency-injection pattern (agents are passed in, not constructed
internally) are designed to make adding one a matter of writing the agent and wiring it
into the Orchestrator's phase sequence, not a redesign.
