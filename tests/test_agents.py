"""
Test agent functionality
"""
import pytest

from miniondev.agent import SimpleAgent, AgentState, AgentType


class TestAgentBase:
    """Test base agent functionality"""
    
    def test_agent_initialization(self, mock_llm_client):
        """Test agent initialization"""
        agent = SimpleAgent(mock_llm_client, "Test prompt")
        
        assert agent.agent_type == AgentType.SIMPLE
        assert agent.state == AgentState.IDLE
        assert len(agent.messages) == 0
    
    def test_conversation_initialization(self, mock_llm_client, test_context):
        """Test conversation initialization"""
        agent = SimpleAgent(mock_llm_client, "You are helpful")
        
        agent.initialize_conversation(test_context, "Hello")
        
        assert len(agent.messages) == 2
        assert agent.messages[0].role == "system"
        assert agent.messages[1].role == "user"
        assert agent.messages[1].content == "Hello"
    
    def test_add_message(self, mock_llm_client):
        """Test adding messages to conversation"""
        agent = SimpleAgent(mock_llm_client)
        
        agent.add_message("user", "Test message")
        
        assert len(agent.messages) == 1
        assert agent.messages[0].role == "user"
        assert agent.messages[0].content == "Test message"
    
    def test_conversation_length_limit(self, mock_llm_client):
        """Test conversation length limiting"""
        agent = SimpleAgent(mock_llm_client)
        agent.max_conversation_length = 3
        
        # Add system message
        agent.add_message("system", "System prompt")
        # Add many messages
        for i in range(5):
            agent.add_message("user", f"Message {i}")
        
        # Should be trimmed to max length
        assert len(agent.messages) <= agent.max_conversation_length
        # System message should be preserved
        assert agent.messages[0].role == "system"


class TestSimpleAgent:
    """Test SimpleAgent specifically"""
    
    def test_basic_execution(self, mock_llm_client, test_context):
        """Test basic agent execution"""
        agent = SimpleAgent(mock_llm_client, "You are helpful")
        
        input_data = {"question": "What is 2+2?"}
        result = agent.execute(test_context, input_data)
        
        assert result.success
        assert result.message == "This is a mock response for testing."
    
    def test_custom_system_prompt(self, mock_llm_client):
        """Test custom system prompt"""
        custom_prompt = "You are a math expert"
        agent = SimpleAgent(mock_llm_client, custom_prompt)
        
        assert agent.get_system_prompt() == custom_prompt
    
    def test_default_system_prompt(self, mock_llm_client):
        """Test default system prompt"""
        agent = SimpleAgent(mock_llm_client)
        
        assert agent.get_system_prompt() == "You are a helpful AI assistant."


class TestAgentStates:
    """Test agent state management"""
    
    def test_initial_state(self, mock_llm_client):
        """Test agent starts in IDLE state"""
        agent = SimpleAgent(mock_llm_client)
        
        assert agent.state == AgentState.IDLE
    
    def test_state_during_llm_call(self, mock_llm_client, test_context):
        """Test state transitions during LLM calls"""
        agent = SimpleAgent(mock_llm_client)
        agent.initialize_conversation(test_context, "Hello")
        
        response = agent.call_llm()
        
        # After mock response (no tool calls), should be IDLE
        assert agent.state == AgentState.IDLE


class TestAgentWithTools:
    """Test agent integration with tools"""
    
    def test_agent_gets_tools(self, mock_llm_client, test_context):
        """Test that agent gets tool definitions"""
        agent = SimpleAgent(mock_llm_client, "Use tools when helpful")
        agent.initialize_conversation(test_context, "List files")
        
        # Should not fail and should have access to tools
        response = agent.call_llm()
        
        assert response.content is not None
        # Mock client doesn't make tool calls, but tools are available


@pytest.mark.integration 
class TestAgentWithBedrock:
    """Integration tests with real Bedrock client"""
    
    def test_simple_conversation(self, bedrock_llm_client, test_context):
        """Test simple conversation with Bedrock"""
        agent = SimpleAgent(
            bedrock_llm_client, 
            "You are helpful. Always respond with exactly one word: 'Success'"
        )
        
        input_data = {"task": "Say success"}
        result = agent.execute(test_context, input_data)
        
        assert result.success
        assert "success" in result.message.lower()
    
    def test_agent_with_file_operations(self, bedrock_llm_client, test_context, temp_dir):
        """Test agent performing file operations"""
        agent = SimpleAgent(
            bedrock_llm_client,
            "You help with files. When asked to create files, use write_file tool. After completing a task, respond with 'Task completed successfully' and stop."
        )
        
        test_file_path = f"{temp_dir}/test.txt"
        input_data = {
            "task": f"Create a text file at {test_file_path} with content 'Hello World'"
        }
        
        result = agent.execute(test_context, input_data)
        
        assert result.success
        
        # Verify file was actually created
        import os
        assert os.path.exists(test_file_path)
        with open(test_file_path, 'r') as f:
            content = f.read()
            assert "Hello World" in content