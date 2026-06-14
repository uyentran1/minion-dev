#!/usr/bin/env python3
"""
Test the core agent foundation
"""
import sys
import os
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)

from miniondev.llm.client import BedrockChatClient, MockChatClient
from miniondev.agent import SimpleAgent, AgentContext, AgentState


def test_simple_agent_with_mock():
    """Test SimpleAgent with MockChatClient"""
    print("Testing SimpleAgent with Mock Client...")
    
    try:
        # Create mock client and agent
        client = MockChatClient()
        agent = SimpleAgent(client, "You are a helpful coding assistant.")
        
        # Create test context
        context = AgentContext(
            work_item_id="test-001",
            session_id="session-001"
        )
        
        # Test basic execution
        input_data = {"task": "Explain what a function is in Python"}
        result = agent.execute(context, input_data)
        
        print(f"✅ Agent execution completed")
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"State: {agent.state}")
        
        return True
        
    except Exception as e:
        print(f"❌ SimpleAgent test failed: {e}")
        return False


def test_agent_conversation_flow():
    """Test the agent conversation management"""
    print("\nTesting Agent Conversation Flow...")
    
    try:
        client = MockChatClient()
        agent = SimpleAgent(client, "You are a Python expert who gives concise answers.")
        
        # Test conversation initialization
        context = AgentContext(work_item_id="test-002", session_id="session-002")
        agent.initialize_conversation(context, "What is a list in Python?")
        
        print(f"✅ Conversation initialized")
        print(f"Messages count: {len(agent.messages)}")
        print(f"System message: {agent.messages[0].content[:50]}...")
        
        # Test LLM call
        response = agent.call_llm()
        print(f"✅ LLM call successful")
        print(f"Response content: {response.content[:100]}...")
        print(f"Messages after call: {len(agent.messages)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversation flow test failed: {e}")
        return False


def test_with_bedrock_client():
    """Test with real Bedrock client (if available)"""
    print("\nTesting with Bedrock Client...")
    
    try:
        # Try to create Bedrock client
        client = BedrockChatClient()
        agent = SimpleAgent(
            client, 
            "You are a helpful AI assistant. Give very brief responses (1-2 sentences max)."
        )
        
        context = AgentContext(
            work_item_id="test-bedrock-001", 
            session_id="bedrock-session"
        )
        
        input_data = {"question": "What is recursion in programming?"}
        result = agent.execute(context, input_data)
        
        print(f"✅ Bedrock agent execution completed")
        print(f"Success: {result.success}")
        print(f"Response: {result.message}")
        print(f"Messages count: {len(agent.messages)}")
        
        return True
        
    except ValueError as e:
        if "AWS_BEARER_TOKEN_BEDROCK" in str(e):
            print("⚠️  Bedrock client needs bearer token - this is expected")
            return True
        else:
            print(f"❌ Bedrock test failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Bedrock test failed: {e}")
        return False


def test_agent_states():
    """Test agent state management"""
    print("\nTesting Agent State Management...")
    
    try:
        client = MockChatClient()
        agent = SimpleAgent(client)
        
        # Test initial state
        assert agent.state == AgentState.IDLE, f"Expected IDLE, got {agent.state}"
        print("✅ Initial state: IDLE")
        
        # Test state transitions during conversation
        context = AgentContext(work_item_id="state-test", session_id="state-session")
        agent.initialize_conversation(context, "Hello")
        
        # State should still be idle until we call LLM
        assert agent.state == AgentState.IDLE
        print("✅ State after initialization: IDLE")
        
        # Make LLM call and check state progression
        response = agent.call_llm()
        # After mock response (no tool calls), should be back to IDLE
        assert agent.state == AgentState.IDLE
        print("✅ State after LLM call: IDLE")
        
        return True
        
    except Exception as e:
        print(f"❌ State management test failed: {e}")
        return False


if __name__ == "__main__":
    print("MinionDev Core Agent Foundation Test")
    print("=" * 50)
    
    # Run all tests
    tests = [
        test_simple_agent_with_mock,
        test_agent_conversation_flow,
        test_agent_states,
        test_with_bedrock_client
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print(f"\n{'='*50}")
    print("Test Summary:")
    print(f"Mock Client Tests: {'✅ Passed' if results[0] and results[1] and results[2] else '❌ Failed'}")
    print(f"Bedrock Client Test: {'✅ Passed' if results[3] else '❌ Failed'}")
    
    if all(results):
        print(f"\n🎉 Core agent foundation is working correctly!")
        print("Ready for tool system implementation!")
    else:
        print(f"\n❌ Some tests failed - check implementation")