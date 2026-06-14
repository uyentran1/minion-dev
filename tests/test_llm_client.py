"""
Test LLM clients
"""
import pytest
from miniondev.llm.client import MockChatClient, ChatMessage


class TestMockChatClient:
    """Test MockChatClient functionality"""
    
    def test_basic_chat_completion(self, mock_llm_client):
        """Test basic chat completion"""
        messages = [
            ChatMessage(role="user", content="Hello")
        ]
        
        response = mock_llm_client.chat_completion(messages)
        
        assert response.content == "This is a mock response for testing."
        assert response.tool_calls is None
    
    def test_chat_completion_with_tools(self, mock_llm_client):
        """Test chat completion with tools (should still work)"""
        messages = [
            ChatMessage(role="user", content="Use a tool")
        ]
        
        # Mock tools (empty list)
        response = mock_llm_client.chat_completion(messages, tools=[])
        
        assert response.content == "This is a mock response for testing."
        assert response.tool_calls is None


class TestBedrockChatClient:
    """Test BedrockChatClient functionality (requires credentials)"""
    
    @pytest.mark.integration
    def test_basic_chat_completion(self, bedrock_llm_client):
        """Test basic chat completion with Bedrock"""
        messages = [
            ChatMessage(role="user", content="Say 'Hello' in one word")
        ]
        
        response = bedrock_llm_client.chat_completion(messages, max_tokens=50)
        
        assert response.content is not None
        assert len(response.content) > 0
        assert "hello" in response.content.lower()
    
    @pytest.mark.integration
    def test_system_message(self, bedrock_llm_client):
        """Test system message handling"""
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant. Always respond with exactly 'OK'."),
            ChatMessage(role="user", content="Hello")
        ]
        
        response = bedrock_llm_client.chat_completion(messages, max_tokens=10)
        
        assert response.content is not None
        assert "ok" in response.content.lower()