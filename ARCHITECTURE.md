# MinionDev Architecture

## Overview

MinionDev is an autonomous AI coding agent that automates the software delivery workflow
from a ticket/prompt to a pull request, inspired by Stripe's Minions project.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MinionDev CLI                          │
├─────────────────────────────────────────────────────────────────┤
│                       Orchestrator (sync)                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │   Planner     │→ │   Executor    │→ │  Finalizer    │      │
│  │  (LLM agent)  │  │  (LLM agent)  │  │ (deterministic)│      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                        Agent Core                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │ Tool Registry │  │ Conversation  │  │ State + Progress│     │
│  │               │  │     Loop      │  │    Callback    │      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                      LLM Client                                │
│         BedrockChatClient (Claude via Converse API)             │
│              or MockChatClient (tests)                         │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Orchestrator (`src/miniondev/orchestrator.py`)

Sequences Planner → Executor → (optional) Finalizer for one `WorkItem`.

```python
class Orchestrator:
    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent,
                 finalizer: Optional[FinalizerAgent] = None):
        ...
    def process_work_item(self, work_item: WorkItem) -> WorkResult: ...
```

Design choices:

- **Agents are injected, not constructed internally.** The Orchestrator doesn't own an
  `llm_client` or build its own agents - callers (the CLI, tests) construct and configure
  agents and hand them in. This lets tests inject agents backed by different mock
  responses per phase, and lets a duck-typed fake stand in for any agent in tests.
- **Finalizer is optional.** Not every caller wants git/PR side effects (unit tests, a
  plan-only preview). If omitted, the pipeline stops after Execute.
- **Failure short-circuits but preserves prior results.** A Planner failure means the
  Executor never runs at all. An Executor or Finalizer failure still returns the
  `plan`/`execution_result` produced so far on `WorkResult`, for debugging.
- The only contract the Orchestrator relies on is `execute(context, input_data) ->
AgentResult` - it doesn't care whether the object is an `Agent` subclass.

### 2. Agent System (`src/miniondev/agent/`)

#### `Agent` base class (`base.py`)

Owns the conversation loop shared by `PlannerAgent` and `ExecutorAgent`:

- `messages: List[ChatMessage]` - the conversation history sent to the LLM each turn.
- `run_conversation_loop()` - calls the LLM, executes any tool calls it requests, feeds
  results back, repeats until the LLM responds with no tool calls and some content, or
  `max_turns` is hit (configurable per agent - Planner needs less headroom than Executor).
- `get_available_tools()` - override to restrict which tools an agent may use (Planner is
  read-only; Executor gets everything including `write_file`/`run_command`).
- `progress_callback: Optional[Callable[[str], None]]` - optional hook called at turn
  start, per tool call, and on completion/failure. No-op by default (silent in tests); the
  CLI wires `print` into it so users see `[planner] turn 2/15: calling write_file(...)`
  style progress in real time. Kept decoupled from core logic on purpose.

**Why tool calls are structured, not flattened to text:** `ChatMessage` carries `tool_calls`
/ `tool_results` as real fields (matching Bedrock Converse's `toolUse`/`toolResult` content
blocks), not text like `"[Tool call: X]"`. An earlier version flattened everything to
strings, which once caused the model to start imitating that bracket-text convention as
plain output instead of issuing a real tool call - a symptom of the model pattern-matching
on its own prior turns once they were indistinguishable from real text. Each `ToolResult`
also carries `is_error`, so the model gets a structured success/failure signal, not just
prose it has to parse.

#### Planner Agent (`planner.py`)

**Input**: `{title, description}` · **Output**: `PlanArtifact`

Read-only tool access (`read_file`, `list_directory`, `search_files`, `file_exists`,
`get_file_info`) - it explores the repo to inform its plan but cannot mutate anything;
that's the Executor's job. Its system prompt explicitly tells it that a missing target
file is expected (a plan step should create it), and caps exploration at a few tool calls -
without this, the model would keep searching different filename variants instead of
concluding "doesn't exist, plan to create it."

Its final response is parsed as JSON into a `PlanArtifact`. Models don't reliably follow
"respond with ONLY JSON" - they sometimes add a prose preamble before a fenced or unfenced
JSON block. `_extract_json()` handles both cases: it looks for a fenced ` ```json ``` `
block anywhere in the text first, then falls back to slicing from the first `{` to the
last `}`. `work_item_id` is injected by our own code after parsing, never trusted from the
LLM's JSON, since getting that wrong would corrupt downstream state.

#### Executor Agent (`executor.py`)

**Input**: `PlanArtifact` · **Output**: `ExecutionResult`

Full tool access (read, write, list, search, run commands) since making changes is its
job. `modified_files` and `errors` on `ExecutionResult` are derived from **real tool
execution** (every successful `write_file`/`create_directory` call), not from asking the
LLM to self-report what it changed - that's ground truth we already have, no need to trust
the model's summary of its own actions. The LLM's final message only needs to be a
plain-text summary (no JSON needed here, since the only thing parsed from the model is
prose, not structured data).

#### Finalizer (`finalizer.py`)

**Input**: `{plan, execution_result}` · **Output**: `FinalizationResult`

**Not an `Agent` subclass, deliberately.** Git/PR operations are exactly the kind of
hard-to-reverse, shared-state actions that should be deterministic and explicitly
opted into, not decided turn-by-turn by an LLM tool-calling loop. It exposes the same
`execute(context, input_data) -> AgentResult` shape purely by duck typing so the
Orchestrator can wire it in identically.

- `FinalizerOptions(enable_commit, enable_push, enable_pr, base_branch)` - defaults to a
  true dry run (no git state touched). `__post_init__` enforces that `enable_pr` implies
  `enable_push` implies `enable_commit`, so a flag combination can never silently no-op.
- Commit messages and PR descriptions are **templated** from `PlanArtifact.summary` /
  `ExecutionResult.summary` - no extra LLM call for this; simpler, deterministic, one fewer
  failure mode in the part of the pipeline meant to be the safe one.
- Every value interpolated into a shell command (`shlex.quote()`) before being passed to
  `run_command`, which shells out with `shell=True` - branch names and commit messages
  contain LLM-generated text, so this is a real command-injection guard, not paranoia.
- PR creation actually calls `gh pr create` (via the same `run_command` tool used
  elsewhere). On a machine without `gh` authenticated, this fails fast and cleanly
  (verified by `test_gh_pr_create_failure_is_reported_without_losing_prior_progress`) -
  the failure is surfaced in `FinalizationResult.errors`, not swallowed, and the
  commit/push that already succeeded are still correctly reflected.

### 3. Tool Registry (`src/miniondev/tools/`)

Decorator-based: `@tool(name=..., description=..., parameters={...})` registers a function
and its JSON schema (auto-derived from the function signature if not given explicitly) in a
global `ToolRegistry`. `registry.get_tool_definitions()` feeds Bedrock's `toolConfig`;
`registry.execute_tool(name, args)` runs it and returns a `ToolResult(success, output,
error)`. Tools: `read_file`, `write_file`, `list_directory`, `create_directory`,
`run_command`, `file_exists`, `search_files`, `get_file_info`.

### 4. LLM Client (`src/miniondev/llm/client.py`)

`ChatClient` abstract base with two implementations:

- `BedrockChatClient` - real calls via the Bedrock Converse API, authenticated with
  `AWS_BEARER_TOKEN_BEDROCK` only (no AWS access key/secret support - simplified
  deliberately).
- `MockChatClient` - configurable canned `content`/`tool_calls`, used throughout the test
  suite so most tests run with no AWS dependency or cost.

`ChatMessage`, `ToolCall`, `ToolResult`, `ToolDefinition` are Pydantic models - used here
(rather than `@dataclass`) because they cross a trust boundary: they're built from JSON
that came back from an LLM API call and need validation, unlike e.g. `AgentContext`/
`AgentResult` (plain dataclasses, since those only ever move Python-to-Python under our
own control).

### 5. Data Models (`src/miniondev/models/`)

All Pydantic, for the same trust-boundary reason - the Planner's and Finalizer's outputs in
particular are parsed from LLM-produced text and need validation:

```python
class WorkItem(BaseModel):
    id: str
    title: str
    description: str

class PlanStep(BaseModel):
    step_number: int
    description: str             # natural-language intent, not a literal tool call -
                                  # the Executor decides how to implement it
    target_files: List[str] = []
    rationale: Optional[str] = None

class PlanArtifact(BaseModel):
    work_item_id: str
    summary: str
    steps: List[PlanStep]         # order *is* the dependency order; no separate graph
    acceptance_criteria: List[str] = []

class ExecutionResult(BaseModel):
    work_item_id: str
    modified_files: List[str] = []  # derived from real tool calls, not LLM self-report
    summary: str
    errors: List[str] = []

class FinalizationResult(BaseModel):
    work_item_id: str
    dry_run: bool
    branch_name: str
    committed: bool = False
    pushed: bool = False
    pr_url: Optional[str] = None
    message: str
    errors: List[str] = []

class WorkResult(BaseModel):       # Orchestrator's end-to-end result
    work_item_id: str
    success: bool
    message: str
    plan: Optional[PlanArtifact] = None
    execution_result: Optional[ExecutionResult] = None
    finalization_result: Optional[FinalizationResult] = None
    errors: List[str] = []
```

These are intentionally smaller than an early sketch of this document had them (no
`dependencies` graph, no `estimated_duration`, no `ValidationPoint`/`TestResult`/
`BuildStatus` types) - those were speculative complexity with no consumer; add them if a
real need for them shows up.

## Workflow Sequence

```
CLI (--prompt, --repo, --enable-commit/--enable-push/--enable-pr)
  → builds WorkItem
  → Orchestrator.process_work_item(work_item)
      → PlannerAgent.execute()   → PlanArtifact   (read-only repo exploration)
      → ExecutorAgent.execute()  → ExecutionResult (read/write/run tools)
      → FinalizerAgent.execute() → FinalizationResult (git/gh, flag-gated)
  → WorkResult printed to stdout, with live progress throughout via progress_callback
```

## Error Handling (as actually implemented)

- Each phase returns `AgentResult(success, message, data, errors)`. A failed phase
  short-circuits the rest of the pipeline but preserves whatever prior phases produced.
- `Agent.run_conversation_loop()` caps turns at `max_turns` (per-agent: 10 default, higher
  for Planner/Executor since they need exploration/implementation headroom) and returns
  `success=False` with `"Max turns exceeded"` rather than looping forever.
- Tool execution failures are caught inside `ToolRegistry.execute_tool()` and returned as
  `ToolResult(success=False, error=...)` rather than raising - a failing tool call becomes
  visible to the LLM as a turn result it can react to, not a crash.
- There is no retry/backoff logic, no rollback mechanism, and no caching layer. If these
  become necessary they should be added when a concrete failure mode demands them, not
  speculatively.

## Security Considerations (as actually implemented)

- Bedrock auth is bearer-token only, loaded from `.env` or env var, never hardcoded.
- Planner's tool access is restricted to read-only tools at the `get_available_tools()`
  level, not just via prompt instruction - the model literally cannot be offered
  `write_file`/`run_command` during planning.
- Every value interpolated into a Finalizer shell command is `shlex.quote()`-escaped, since
  those commands carry LLM-generated text and `run_command` uses `shell=True`.
- Finalizer defaults to a true dry run; `--enable-commit`/`--enable-push`/`--enable-pr` must
  be explicitly passed, and the options object enforces their dependency order so a partial
  flag combination can't silently produce unexpected git state.
- There is no sandboxing of tool execution (file/command tools run with the same
  permissions as the CLI process) and no audit log beyond standard logging - worth
  revisiting before pointing this at anything beyond a disposable repo/branch.

## Future Work

### Additional agent types

The pipeline isn't limited to Planner/Executor/Finalizer. The natural extension point is
between Executor and Finalizer - an additional phase that can gate whether finalization
proceeds, following the same `execute(context, input_data) -> AgentResult` shape:

- **Reviewer agent** - reviews `ExecutionResult` against `PlanArtifact`'s acceptance
  criteria before anything is committed; could return a `ReviewResult(approved: bool,
comments: List[str])` that the Orchestrator checks before calling the Finalizer.
- **Security reviewer** - a specialized reviewer scanning the diff for hardcoded secrets,
  injection patterns, etc.
- **Validator/Tester agent** - runs the full test suite/linting independently rather than
  relying solely on the Executor's own self-verification (separation of concerns: the agent
  that wrote the code shouldn't be the only judge of whether it's correct).
- **Documentation agent** - updates README/CHANGELOG/docstrings for the change.
- **Jira intake agent** - converts a real ticket into the same `WorkItem` the Orchestrator
  already consumes (see README's "Future Jira enhancement") - no orchestrator redesign
  needed, since `WorkItem` is already the integration point.

None of these are implemented. Adding one means: write the agent, give it whatever
tool/LLM access it needs, and add it as another optional phase in `Orchestrator` the same
way `finalizer` was added - not a redesign.

### Explicitly not planned for now

Multi-repository coordination, async/parallel work-item processing, response caching, and
plugin/webhook systems were sketched in an earlier draft of this document but have no
current use case driving them. Revisit if/when a real need shows up rather than building
ahead of it.
