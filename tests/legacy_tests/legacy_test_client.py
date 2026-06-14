#!/usr/bin/env python3
"""
Test MinionDev LLM clients - both Bedrock and Mock
"""
import sys
import os
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)

from miniondev.llm.client import BedrockChatClient, MockChatClient, ChatMessage


def test_bedrock_client():
    """Test BedrockChatClient with Claude Sonnet 4.5"""
    try:
        print("Testing Bedrock Client...")
        client = BedrockChatClient()
        
        messages = [
            ChatMessage(role="user", content="Write a one-sentence bedtime story about a unicorn.")
        ]
        
        response = client.chat_completion(messages, max_tokens=100)
        print(f"✅ Bedrock Success!")
        print(f"Model: {client.model_id}")
        print(f"Response: {response.content}")
        return True
        
    except Exception as e:
        print(f"❌ Bedrock failed: {e}")
        return False


def test_mock_client():
    """Test MockChatClient for development"""
    try:
        print("\nTesting Mock Client...")
        client = MockChatClient()
        
        messages = [
            ChatMessage(role="user", content="Test message")
        ]
        
        response = client.chat_completion(messages)
        print(f"✅ Mock Success!")
        print(f"Response: {response.content}")
        return True
        
    except Exception as e:
        print(f"❌ Mock failed: {e}")
        return False


def test_tool_calling():
    """Test tool calling capability (when tools are implemented)"""
    try:
        print("\nTesting Tool Calling...")
        client = MockChatClient()
        
        # This will be useful when we implement tools
        messages = [
            ChatMessage(role="system", content="You are a helpful coding assistant."),
            ChatMessage(role="user", content="List the files in the current directory.")
        ]
        
        # For now, just test without tools
        response = client.chat_completion(messages)
        print(f"✅ Tool calling structure ready!")
        print(f"Response: {response.content}")
        return True
        
    except Exception as e:
        print(f"❌ Tool calling test failed: {e}")
        return False


if __name__ == "__main__":
    print("MinionDev LLM Client Test")
    print("=" * 40)
    
    # Test both clients
    bedrock_works = test_bedrock_client()
    mock_works = test_mock_client()
    
    print(f"\n{'='*40}")
    print("Test Summary:")
    print(f"Bedrock Client: {'✅ Working' if bedrock_works else '❌ Not available'}")
    print(f"Mock Client: {'✅ Working' if mock_works else '❌ Failed'}")
    
    if bedrock_works:
        print(f"\n🎉 Ready for agent development with real Bedrock!")
    elif mock_works:
        print(f"\n💡 Ready for agent development with mock client!")
    else:
        print(f"\n❌ Setup issues - check dependencies")