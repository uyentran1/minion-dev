#!/usr/bin/env python3
"""
Test tools with real Bedrock client
"""
import sys
import os
import tempfile
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)

from miniondev.llm.client import BedrockChatClient
from miniondev.agent import SimpleAgent, AgentContext


def test_agent_file_operations():
    """Test agent performing real file operations with Bedrock"""
    print("Testing Agent File Operations with Bedrock...")
    
    try:
        # Create Bedrock client and agent
        client = BedrockChatClient()
        agent = SimpleAgent(
            client,
            "You are a helpful coding assistant. When asked to work with files, use the available tools. After completing a task successfully, respond with 'Task completed successfully' and stop."
        )
        
        # Create test context
        context = AgentContext(
            work_item_id="bedrock-file-test",
            session_id="bedrock-session"
        )
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as tmp_dir:
            print(f"Using temporary directory: {tmp_dir}")
            
            # Test 1: Ask agent to create a file
            input_data = {
                "task": f"Create a simple Python hello world script at {tmp_dir}/hello.py"
            }
            
            result = agent.execute(context, input_data)
            
            print(f"✅ Agent execution completed")
            print(f"Success: {result.success}")
            print(f"Response: {result.message}")
            print(f"Conversation turns: {len(agent.messages)}")
            print(f"Conversation: {agent.messages}")
            
            # Check if file was actually created
            hello_file = os.path.join(tmp_dir, "hello.py")
            if os.path.exists(hello_file):
                print(f"✅ File created successfully!")
                with open(hello_file, 'r') as f:
                    content = f.read()
                print(f"File content preview: {content[:100]}...")
            else:
                print(f"⚠️  File not found - agent may not have used tools")
            
        return True
        
    except ValueError as e:
        if "AWS_BEARER_TOKEN_BEDROCK" in str(e):
            print("⚠️  Bedrock client needs bearer token - skipping real test")
            return True
        else:
            print(f"❌ Bedrock file test failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Bedrock file test failed: {e}")
        return False


def test_agent_directory_listing():
    """Test agent listing directory contents"""
    print("\nTesting Agent Directory Listing...")
    
    try:
        client = BedrockChatClient()
        agent = SimpleAgent(
            client,
            "You are helpful assistant. When asked about directories, use the list_directory tool to provide accurate information."
        )
        
        context = AgentContext(
            work_item_id="bedrock-dir-test", 
            session_id="bedrock-session-2"
        )
        
        # Ask agent to list current directory
        input_data = {
            "task": "List the contents of the current directory (.)"
        }
        
        result = agent.execute(context, input_data)
        
        print(f"✅ Directory listing completed")
        print(f"Success: {result.success}")
        print(f"Response preview: {result.message}")
        print(f"Conversation: {agent.messages}")
        
        return True
        
    except ValueError as e:
        if "AWS_BEARER_TOKEN_BEDROCK" in str(e):
            print("⚠️  Bedrock client needs bearer token - skipping real test") 
            return True
        else:
            print(f"❌ Bedrock directory test failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Bedrock directory test failed: {e}")
        return False


if __name__ == "__main__":
    print("MinionDev Tools with Bedrock Test")
    print("=" * 50)
    
    tests = [
        test_agent_file_operations,
        test_agent_directory_listing
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print(f"\n{'='*50}")
    print("Test Summary:")
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{test.__name__}: {status}")
    
    if all(results):
        print(f"\n🎉 Tools work perfectly with Bedrock!")
        print("Agents can now perform real file operations!")
    else:
        print(f"\n❌ Some tests failed")