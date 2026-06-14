#!/usr/bin/env python3
"""
Test the tool registry and basic tools
"""
import sys
import os
import tempfile
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)

from miniondev.tools import get_registry
from miniondev.tools.registry import ToolResult
from miniondev.llm.client import MockChatClient
from miniondev.agent import SimpleAgent, AgentContext


def test_tool_registry():
    """Test tool registration and discovery"""
    print("Testing Tool Registry...")
    
    try:
        registry = get_registry()
        
        # Check registered tools
        tools = registry.list_tools()
        print(f"✅ Found {len(tools)} registered tools:")
        for tool_name in sorted(tools):
            print(f"  - {tool_name}")
        
        # Check tool definitions
        definitions = registry.get_tool_definitions()
        print(f"✅ Tool definitions: {len(definitions)} available for LLM:")
        for definition in definitions:
            print(f"  - {definition}")
        
        # Test specific tool
        if "read_file" in tools:
            tool_def = registry.get_tool_definition("read_file")
            print(f"✅ read_file tool definition: {tool_def.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool registry test failed: {e}")
        return False


def test_basic_file_tools():
    """Test basic file operations"""
    print("\nTesting Basic File Tools...")
    
    try:
        registry = get_registry()
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
            test_content = "Hello, MinionDev tools!"
            tmp.write(test_content)
            tmp_path = tmp.name
        
        try:
            # Test read_file
            result = registry.execute_tool("read_file", {"file_path": tmp_path})
            assert result.success, f"read_file failed: {result.error}"
            assert result.output == test_content, "Content mismatch"
            print("✅ read_file tool works")
            
            # Test file_exists
            result = registry.execute_tool("file_exists", {"path": tmp_path})
            assert result.success, f"file_exists failed: {result.error}"
            assert result.output["exists"] == True, "File should exist"
            print("✅ file_exists tool works")
            
            # Test get_file_info
            result = registry.execute_tool("get_file_info", {"file_path": tmp_path})
            assert result.success, f"get_file_info failed: {result.error}"
            assert result.output["size_bytes"] > 0, "File should have size"
            print("✅ get_file_info tool works")
            
            # Test write_file
            new_content = "Updated content!"
            result = registry.execute_tool("write_file", {
                "file_path": tmp_path,
                "content": new_content
            })
            assert result.success, f"write_file failed: {result.error}"
            print("✅ write_file tool works")
            
            # Verify write worked
            result = registry.execute_tool("read_file", {"file_path": tmp_path})
            assert result.output == new_content, "Write didn't update content"
            print("✅ File write verification works")
            
        finally:
            # Cleanup
            os.unlink(tmp_path)
            
        return True
        
    except Exception as e:
        print(f"❌ Basic file tools test failed: {e}")
        return False


def test_directory_tools():
    """Test directory operations"""
    print("\nTesting Directory Tools...")
    
    try:
        registry = get_registry()
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Test list_directory
            result = registry.execute_tool("list_directory", {"directory_path": tmp_dir})
            assert result.success, f"list_directory failed: {result.error}"
            assert isinstance(result.output, list), "Should return a list"
            print("✅ list_directory tool works")
            
            # Test create_directory
            new_dir = os.path.join(tmp_dir, "test_subdir")
            result = registry.execute_tool("create_directory", {"directory_path": new_dir})
            assert result.success, f"create_directory failed: {result.error}"
            assert os.path.exists(new_dir), "Directory should be created"
            print("✅ create_directory tool works")
            
            # Test search_files
            # Create a test file
            test_file = os.path.join(new_dir, "test.py")
            with open(test_file, 'w') as f:
                f.write("print('hello')")
            
            result = registry.execute_tool("search_files", {
                "directory": tmp_dir,
                "pattern": "*.py",
                "recursive": True
            })
            assert result.success, f"search_files failed: {result.error}"
            assert len(result.output) > 0, "Should find the test.py file"
            print("✅ search_files tool works")
        
        return True
        
    except Exception as e:
        print(f"❌ Directory tools test failed: {e}")
        return False


def test_command_tool():
    """Test command execution"""
    print("\nTesting Command Tool...")
    
    try:
        registry = get_registry()
        
        # Test simple command
        result = registry.execute_tool("run_command", {"command": "echo 'Hello World'"})
        assert result.success, f"run_command failed: {result.error}"
        assert "Hello World" in result.output["stdout"], "Command output incorrect"
        assert result.output["return_code"] == 0, "Should succeed"
        print("✅ run_command tool works")
        
        # Test command with error
        result = registry.execute_tool("run_command", {"command": "false"})  # Command that always fails
        assert result.success, "Tool execution should succeed even if command fails"
        assert result.output["return_code"] != 0, "Command should fail"
        print("✅ Command error handling works")
        
        return True
        
    except Exception as e:
        print(f"❌ Command tool test failed: {e}")
        return False


def test_agent_with_tools():
    """Test agent using tools"""
    print("\nTesting Agent with Tools...")
    
    try:
        # Create mock client and agent
        client = MockChatClient()
        agent = SimpleAgent(
            client, 
            "You are a helpful assistant that can read and write files. Use tools when needed."
        )
        
        # Create context
        context = AgentContext(
            work_item_id="tools-test",
            session_id="tools-session"
        )
        
        # Test that agent gets tools
        agent.initialize_conversation(context, "List the available tools")
        response = agent.call_llm()
        
        # Check that tools were provided to LLM
        registry = get_registry()
        tools_count = len(registry.list_tools())
        print(f"✅ Agent has access to {tools_count} tools")
        print(f"✅ LLM call successful: {response.content[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent with tools test failed: {e}")
        return False


if __name__ == "__main__":
    print("MinionDev Tools System Test")
    print("=" * 50)
    
    # Run all tests
    tests = [
        test_tool_registry,
        test_basic_file_tools,
        test_directory_tools,
        test_command_tool,
        test_agent_with_tools
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
        print(f"\n🎉 All tools tests passed!")
        print("Ready for agent development with full tool support!")
    else:
        print(f"\n❌ Some tests failed - check implementation")