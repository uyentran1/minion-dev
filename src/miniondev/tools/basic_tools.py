"""
Basic Tools for MinionDev Agents

Essential file operations, command execution, and utility tools.
"""
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from .registry import tool


@tool(
    name="read_file",
    description="Read the contents of a file",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read"
            },
            "encoding": {
                "type": "string", 
                "description": "File encoding (default: utf-8)",
                "default": "utf-8"
            }
        },
        "required": ["file_path"]
    }
)
def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """Read and return the contents of a file"""
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        return content
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading file {file_path}: {str(e)}")


@tool(
    name="write_file", 
    description="Write content to a file",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "default": "utf-8"
            }
        },
        "required": ["file_path", "content"]
    }
)
def write_file(file_path: str, content: str, encoding: str = "utf-8") -> str:
    """Write content to a file, creating directories if needed"""
    try:
        # Create parent directories if they don't exist
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        raise Exception(f"Error writing file {file_path}: {str(e)}")


@tool(
    name="list_directory",
    description="List contents of a directory", 
    parameters={
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "Path to the directory to list"
            },
            "include_hidden": {
                "type": "boolean", 
                "description": "Include hidden files (default: false)",
                "default": False
            }
        },
        "required": ["directory_path"]
    }
)
def list_directory(directory_path: str, include_hidden: bool = False) -> List[str]:
    """List contents of a directory"""
    try:
        items = []
        for item in os.listdir(directory_path):
            if not include_hidden and item.startswith('.'):
                continue
            item_path = os.path.join(directory_path, item)
            item_type = "directory" if os.path.isdir(item_path) else "file"
            items.append(f"{item} ({item_type})")
        return sorted(items)
    except FileNotFoundError:
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    except Exception as e:
        raise Exception(f"Error listing directory {directory_path}: {str(e)}")


@tool(
    name="create_directory",
    description="Create a new directory",
    parameters={
        "type": "object", 
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "Path of the directory to create"
            },
            "parents": {
                "type": "boolean",
                "description": "Create parent directories if needed (default: true)",
                "default": True
            }
        },
        "required": ["directory_path"]
    }
)
def create_directory(directory_path: str, parents: bool = True) -> str:
    """Create a directory"""
    try:
        Path(directory_path).mkdir(parents=parents, exist_ok=True)
        return f"Successfully created directory: {directory_path}"
    except Exception as e:
        raise Exception(f"Error creating directory {directory_path}: {str(e)}")


@tool(
    name="run_command",
    description="Execute a shell command",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string", 
                "description": "Command to execute"
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for command execution (optional)"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
                "default": 30
            }
        },
        "required": ["command"]
    }
)
def run_command(command: str, working_directory: str = None, timeout: int = 30) -> Dict[str, Any]:
    """Execute a shell command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_directory,
            timeout=timeout,
            capture_output=True,
            text=True
        )
        
        return {
            "command": command,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        raise Exception(f"Command timed out after {timeout} seconds: {command}")
    except Exception as e:
        raise Exception(f"Error executing command '{command}': {str(e)}")


@tool(
    name="file_exists",
    description="Check if a file or directory exists",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to check for existence"
            }
        },
        "required": ["path"]
    }
)
def file_exists(path: str) -> Dict[str, Any]:
    """Check if a file or directory exists"""
    path_obj = Path(path)
    return {
        "path": path,
        "exists": path_obj.exists(),
        "is_file": path_obj.is_file() if path_obj.exists() else False,
        "is_directory": path_obj.is_dir() if path_obj.exists() else False
    }


@tool(
    name="search_files",
    description="Search for files matching a pattern",
    parameters={
        "type": "object", 
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory to search in"
            },
            "pattern": {
                "type": "string", 
                "description": "File pattern to match (e.g., '*.py', '*test*')"
            },
            "recursive": {
                "type": "boolean",
                "description": "Search recursively in subdirectories (default: true)",
                "default": True
            }
        },
        "required": ["directory", "pattern"]
    }
)
def search_files(directory: str, pattern: str, recursive: bool = True) -> List[str]:
    """Search for files matching a pattern"""
    try:
        path_obj = Path(directory)
        if not path_obj.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
            
        if recursive:
            matches = list(path_obj.rglob(pattern))
        else:
            matches = list(path_obj.glob(pattern))
            
        # Return relative paths as strings
        return [str(match.relative_to(path_obj)) for match in matches if match.is_file()]
    except Exception as e:
        raise Exception(f"Error searching files in {directory}: {str(e)}")


@tool(
    name="get_file_info",
    description="Get detailed information about a file",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file"
            }
        },
        "required": ["file_path"]
    }
)
def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get detailed information about a file"""
    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        stat = path_obj.stat()
        return {
            "path": str(path_obj.absolute()),
            "name": path_obj.name,
            "size_bytes": stat.st_size,
            "modified_time": stat.st_mtime,
            "is_file": path_obj.is_file(),
            "is_directory": path_obj.is_dir(),
            "parent_directory": str(path_obj.parent),
            "extension": path_obj.suffix
        }
    except Exception as e:
        raise Exception(f"Error getting file info for {file_path}: {str(e)}")