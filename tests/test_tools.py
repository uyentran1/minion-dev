"""
Test tool registry and basic tools
"""
import pytest
import os
from pathlib import Path

from miniondev.tools import get_registry
from miniondev.tools.registry import ToolResult


class TestToolRegistry:
    """Test tool registry functionality"""
    
    def test_tool_registration(self):
        """Test that tools are properly registered"""
        registry = get_registry()
        
        tools = registry.list_tools()
        assert len(tools) > 0
        assert "read_file" in tools
        assert "write_file" in tools
        assert "list_directory" in tools
    
    def test_tool_definitions(self):
        """Test tool definitions for LLM"""
        registry = get_registry()
        
        definitions = registry.get_tool_definitions()
        assert len(definitions) > 0
        
        # Check read_file definition
        read_file_def = registry.get_tool_definition("read_file")
        assert read_file_def is not None
        assert read_file_def.name == "read_file"
        assert "file_path" in read_file_def.input_schema["properties"]


class TestFileTools:
    """Test file operation tools"""
    
    def test_read_file(self, temp_file):
        """Test read_file tool"""
        registry = get_registry()
        
        result = registry.execute_tool("read_file", {"file_path": temp_file})
        
        assert result.success
        assert "Test content" in result.output
    
    def test_write_file(self, temp_dir):
        """Test write_file tool"""
        registry = get_registry()
        
        test_file = os.path.join(temp_dir, "test.txt")
        test_content = "Hello, World!"
        
        result = registry.execute_tool("write_file", {
            "file_path": test_file,
            "content": test_content
        })
        
        assert result.success
        assert "Successfully wrote" in result.output
        
        # Verify file was created
        assert os.path.exists(test_file)
        with open(test_file, 'r') as f:
            assert f.read() == test_content
    
    def test_file_exists(self, temp_file, temp_dir):
        """Test file_exists tool"""
        registry = get_registry()
        
        # Test existing file
        result = registry.execute_tool("file_exists", {"path": temp_file})
        assert result.success
        assert result.output["exists"] is True
        assert result.output["is_file"] is True
        
        # Test existing directory
        result = registry.execute_tool("file_exists", {"path": temp_dir})
        assert result.success
        assert result.output["exists"] is True
        assert result.output["is_directory"] is True
        
        # Test non-existing file
        result = registry.execute_tool("file_exists", {"path": "/nonexistent/path"})
        assert result.success
        assert result.output["exists"] is False
    
    def test_get_file_info(self, temp_file):
        """Test get_file_info tool"""
        registry = get_registry()
        
        result = registry.execute_tool("get_file_info", {"file_path": temp_file})
        
        assert result.success
        assert result.output["name"] is not None
        assert result.output["size_bytes"] > 0
        assert result.output["is_file"] is True


class TestDirectoryTools:
    """Test directory operation tools"""
    
    def test_list_directory(self, temp_dir):
        """Test list_directory tool"""
        registry = get_registry()
        
        # Create test files
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        result = registry.execute_tool("list_directory", {"directory_path": temp_dir})
        
        assert result.success
        assert isinstance(result.output, list)
        assert any("test.txt" in item for item in result.output)
    
    def test_create_directory(self, temp_dir):
        """Test create_directory tool"""
        registry = get_registry()
        
        new_dir = os.path.join(temp_dir, "subdir")
        
        result = registry.execute_tool("create_directory", {"directory_path": new_dir})
        
        assert result.success
        assert "Successfully created" in result.output
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)
    
    def test_search_files(self, temp_dir):
        """Test search_files tool"""
        registry = get_registry()
        
        # Create test files
        test_files = ["test.py", "test.txt", "other.py"]
        for filename in test_files:
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write("test content")
        
        result = registry.execute_tool("search_files", {
            "directory": temp_dir,
            "pattern": "*.py",
            "recursive": False
        })
        
        assert result.success
        assert isinstance(result.output, list)
        assert len(result.output) == 2  # test.py and other.py
        assert "test.py" in result.output
        assert "other.py" in result.output


class TestCommandTool:
    """Test command execution tool"""
    
    def test_simple_command(self):
        """Test simple command execution"""
        registry = get_registry()
        
        result = registry.execute_tool("run_command", {"command": "echo 'hello'"})
        
        assert result.success
        assert result.output["success"] is True
        assert result.output["return_code"] == 0
        assert "hello" in result.output["stdout"]
    
    def test_failing_command(self):
        """Test command that fails"""
        registry = get_registry()
        
        result = registry.execute_tool("run_command", {"command": "false"})
        
        assert result.success  # Tool execution succeeds
        assert result.output["success"] is False  # But command fails
        assert result.output["return_code"] != 0


class TestToolErrors:
    """Test tool error handling"""
    
    def test_nonexistent_tool(self):
        """Test calling non-existent tool"""
        registry = get_registry()
        
        result = registry.execute_tool("nonexistent_tool", {})
        
        assert not result.success
        assert "not found" in result.error
    
    def test_tool_with_invalid_args(self):
        """Test calling tool with invalid arguments"""
        registry = get_registry()
        
        result = registry.execute_tool("read_file", {})  # Missing file_path
        
        assert not result.success
        assert result.error is not None