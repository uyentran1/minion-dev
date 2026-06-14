"""
Pytest configuration and shared fixtures
"""
import pytest
import tempfile
import os
from pathlib import Path

from miniondev.llm.client import MockChatClient, BedrockChatClient
from miniondev.agent import AgentContext


@pytest.fixture
def mock_llm_client():
    """Provide a mock LLM client for testing"""
    return MockChatClient()


@pytest.fixture
def bedrock_llm_client():
    """Provide a Bedrock client if credentials available"""
    try:
        return BedrockChatClient()
    except ValueError as e:
        if "AWS_BEARER_TOKEN_BEDROCK" in str(e):
            pytest.skip("AWS_BEARER_TOKEN_BEDROCK not available")
        raise


@pytest.fixture
def test_context():
    """Provide a test agent context"""
    return AgentContext(
        work_item_id="test-001",
        session_id="test-session"
    )


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that gets cleaned up"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_file():
    """Provide a temporary file that gets cleaned up"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
        tmp.write("Test content")
        tmp_path = tmp.name
    
    yield tmp_path
    
    # Cleanup
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)