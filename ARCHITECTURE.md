# MinionDev Architecture

## Overview
MinionDev is an autonomous AI coding agent that automates the entire software delivery workflow from Jira ticket pickup to pull request submission, inspired by Stripe's Minions project.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MinionDev CLI                          │
├─────────────────────────────────────────────────────────────────┤
│                       Orchestrator                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │   Planner     │→ │   Executor    │→ │  Finalizer    │      │
│  │   Agent       │  │    Agent      │  │    Agent      │      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                        Agent Core                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │  Tool Registry│  │ Message Loop  │  │  State Mgmt   │      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
├─────────────────────────────────────────────────────────────────┤
│                      LLM Client                               │
│                   (AWS Bedrock)                               │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Orchestrator
**Purpose**: Manages the overall workflow and coordinates between agents.

**Responsibilities**:
- Initialize agents in sequence
- Pass work items between agents
- Handle error recovery and rollbacks
- Maintain global state and context

**Key Methods**:
```python
class Orchestrator:
    async def process_work_item(self, work_item: WorkItem) -> WorkResult
    async def plan_phase(self, work_item: WorkItem) -> PlanArtifact
    async def execute_phase(self, plan: PlanArtifact) -> ExecutionResult
    async def finalize_phase(self, result: ExecutionResult) -> FinalResult
```

### 2. Agent System

#### Planner Agent
**Purpose**: Converts high-level prompts/tickets into structured execution plans.

**Input**: WorkItem (Jira ticket, user request, etc.)
**Output**: PlanArtifact (structured list of tasks and dependencies)

**Process**:
1. Analyze work item requirements
2. Break down into atomic tasks
3. Identify dependencies and ordering
4. Generate file modification plan
5. Create validation checkpoints

#### Executor Agent
**Purpose**: Implements the plan via tool calls and code generation.

**Input**: PlanArtifact
**Output**: ExecutionResult (modified files, test results, etc.)

**Process**:
1. Execute tasks from plan in dependency order
2. Use tools for file operations, command execution
3. Validate each step before proceeding
4. Handle errors and retry logic
5. Maintain execution state

#### Finalizer Agent
**Purpose**: Handles git operations and pull request creation.

**Input**: ExecutionResult
**Output**: FinalResult (PR URL, commit hash, etc.)

**Process**:
1. Run final validation (tests, linting)
2. Create git branch and commits
3. Push to remote repository
4. Create pull request with description
5. Add reviewers and labels

### 3. Tool System

#### Tool Registry
Central registry of available tools that agents can use:

```python
@tool
def read_file(path: str) -> str:
    """Read contents of a file"""

@tool  
def write_file(path: str, content: str) -> None:
    """Write content to a file"""

@tool
def run_command(cmd: str) -> CommandResult:
    """Execute shell command"""

@tool
def run_tests(pattern: str = None) -> TestResult:
    """Run test suite"""
```

#### Tool Categories
- **File Operations**: read, write, create, delete, search
- **Command Execution**: shell commands, build tools, test runners
- **Code Analysis**: AST parsing, dependency analysis
- **Git Operations**: branch, commit, push, PR creation
- **External APIs**: Jira, GitHub, CI/CD systems

### 4. Data Models

#### WorkItem
```python
@dataclass
class WorkItem:
    id: str
    title: str
    description: str
    type: WorkItemType  # FEATURE, BUG, REFACTOR, etc.
    priority: Priority
    repository: str
    branch: Optional[str] = None
    assignee: Optional[str] = None
```

#### PlanArtifact
```python
@dataclass  
class PlanArtifact:
    work_item_id: str
    tasks: List[Task]
    dependencies: Dict[str, List[str]]
    estimated_duration: timedelta
    validation_points: List[ValidationPoint]
```

#### ExecutionResult
```python
@dataclass
class ExecutionResult:
    work_item_id: str
    plan_id: str
    modified_files: List[str]
    test_results: TestResult
    build_status: BuildStatus
    errors: List[ExecutionError]
```

## Workflow Sequence

### 1. Initialization
```
CLI → Orchestrator → Initialize Agents → Load Tools → Connect to LLM
```

### 2. Planning Phase
```
WorkItem → Planner Agent → Analyze Requirements → Generate Tasks → Create Plan
```

### 3. Execution Phase  
```
Plan → Executor Agent → Execute Tasks → Validate Results → Generate Artifacts
```

### 4. Finalization Phase
```
Results → Finalizer Agent → Run Tests → Create PR → Notify Stakeholders
```

## Error Handling Strategy

### Retry Logic
- Network errors: Exponential backoff with jitter
- Tool failures: Retry with different parameters
- LLM errors: Fallback to simpler prompts

### Rollback Mechanism
- Git-based rollback for file changes
- State snapshots at each phase
- Cleanup of temporary resources

### Validation Gates
- Syntax validation after code generation
- Test execution before finalization
- Security scanning for sensitive changes

## Extensibility Points

### Adding New Agents
The orchestrator can be extended with new agents:
```python
class ReviewerAgent(Agent):
    """Performs code review before finalization"""
    
class SecurityAgent(Agent):  
    """Scans for security vulnerabilities"""
    
class DocumentationAgent(Agent):
    """Updates documentation for changes"""
```

### Custom Tools
Tools can be registered for specific repositories:
```python
@tool
def deploy_to_staging() -> DeployResult:
    """Deploy current branch to staging environment"""
```

### Workflow Customization
Different workflows for different work item types:
- Feature: Plan → Execute → Test → Review → Finalize
- Hotfix: Plan → Execute → Test → Finalize (skip review)
- Refactor: Plan → Execute → Full Test Suite → Finalize

## Performance Considerations

### Parallel Execution
- Independent tasks can run concurrently
- Tool calls can be batched where possible
- Async/await throughout the system

### Caching
- LLM response caching for similar requests
- File content caching to reduce I/O
- Tool result caching for idempotent operations

### Resource Management
- Connection pooling for external APIs
- Graceful degradation under load
- Resource cleanup on errors

## Security

### Credential Management
- AWS credentials for Bedrock API
- GitHub tokens for repository access
- Jira API keys for ticket management

### Sandboxing
- Execute code changes in isolated environments
- Validate external command execution
- Prevent access to sensitive files

### Audit Trail
- Log all agent decisions and tool calls
- Track changes and their reasoning
- Maintain provenance for debugging

## Future Enhancements

### Multi-Repository Support
- Cross-repository dependency management
- Coordinated changes across services
- Microservice deployment orchestration

### Advanced Planning
- Cost-based optimization of execution plans
- Learning from previous execution patterns
- Predictive analysis of change impact

### Integration Ecosystem
- Plugin system for custom integrations
- Webhook support for external triggers
- API for programmatic control