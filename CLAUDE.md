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
- Mock client available for development without AWS credentials
- Real Bedrock client configured and tested

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