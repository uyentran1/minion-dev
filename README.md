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

2. Configure AWS credentials (optional - mock mode available):
```bash
aws configure
# OR set environment variables:
# export AWS_ACCESS_KEY_ID="your-key"
# export AWS_SECRET_ACCESS_KEY="your-secret"
# export AWS_DEFAULT_REGION="us-east-1"
```

3. Test the setup:
```bash
python test_bedrock.py
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
