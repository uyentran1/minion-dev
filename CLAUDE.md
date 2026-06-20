# MinionDev - Claude Code Configuration

## Project Overview

MinionDev is an autonomous AI coding agent that automates the software delivery workflow from ticket to PR with zero human supervision. Inspired by Stripe's Minions project.

## Development Setup

### Dependencies

```bash
pip install -e .
```

### AWS Bedrock Setup

- **Model**: Claude Sonnet 4.5 (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- **Region**: eu-north-1
- **API**: Bedrock Converse API

#### Credential Setup

**Method 1: Environment Variable**

```bash
export AWS_BEARER_TOKEN_BEDROCK=your_token_here
python test_client.py
```

**Method 2: Environment File (Persistent)**

```bash
cp .env.example .env
# Edit .env and add your AWS_BEARER_TOKEN_BEDROCK
python test_client.py
```

### Testing

**Automated Test Suite**

```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests
make test

# Run only unit tests (fast, no AWS needed)
make test-unit

# Run integration tests (requires AWS credentials)
make test-integration

# Run tests with coverage
make test-coverage
```

**Test Organization**

- `tests/` - Automated pytest test suite
- `test_*.py` - Legacy manual tests (being migrated)
- Unit tests: Fast, no external dependencies
- Integration tests: Real AWS Bedrock calls

## Architecture

- **LLM Client**: Abstracted interface supporting Bedrock and mock clients
- **Agent System**: Tool-calling agents with conversation management
- **Workflow**: Planner → Executor → Finalizer pipeline

## Commands to Run

### Test LLM Client

```bash
python -c "from src.miniondev.llm.client import BedrockChatClient, MockChatClient, ChatMessage; print('LLM clients ready')"
```

### Install Dependencies

```bash
pip install boto3 pydantic
```

## Development Notes

- Built with AWS Bedrock Converse API for tool calling
- Uses system inference profiles for EU region
- Mock client enables development without AWS costs
- Pydantic for data validation and type safety

## Known Issues / Technical Debt

### ~~Tool call history is flattened to plain text~~ (fixed)

Previously, `Agent.call_llm()` recorded tool calls in conversation history as plain text
strings (`"[Tool call: {name} with args {args}]"`) instead of as Bedrock Converse's
structured `toolUse`/`toolResult` content blocks, which once caused the model to imitate
that bracket-text convention as plain output instead of issuing a real tool call.

**Fixed**: `ChatMessage` (`src/miniondev/llm/client.py`) now carries structured `tool_calls`
and `tool_results` fields. `call_llm()` builds one assistant message per turn with text and
all `toolUse` blocks together; `run_conversation_loop()` batches all tool results for a turn
into a single user message with one `toolResult` block per `toolUseId`, correlated via
`ToolResult.tool_use_id`/`toolUseId`. `BedrockChatClient.chat_completion()` serializes these
into real Converse content blocks instead of flattening to text. `ToolResult.is_error` is set
from actual tool success/failure (not always `False`), so the model gets a structured
success/failure signal, not just prose. Verified via the full test suite including Bedrock
integration tests for SimpleAgent, PlannerAgent, and ExecutorAgent.
