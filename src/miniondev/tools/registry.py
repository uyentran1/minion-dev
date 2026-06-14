"""
Tool Registry System

Manages tool registration, discovery, and execution for MinionDev agents.
"""
import logging
import inspect
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field

from miniondev.llm.client import ToolDefinition


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Central registry for all available tools
    
    Manages tool registration, discovery, and conversion to LLM tool definitions.
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: Dict[str, ToolDefinition] = {}
        self.logger = logging.getLogger(__name__)
        
    def register(
        self, 
        name: str, 
        func: Callable, 
        description: str, 
        parameters: Dict[str, Any]
    ):
        """Register a tool with its schema"""
        self._tools[name] = func
        self._tool_schemas[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=parameters
        )
        self.logger.debug(f"Registered tool: {name}")
        
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool function by name"""
        return self._tools.get(name)
        
    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name"""
        return self._tool_schemas.get(name)
        
    def list_tools(self) -> List[str]:
        """List all registered tool names"""
        return list(self._tools.keys())
        
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions for LLM"""
        return list(self._tool_schemas.values())
        
    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool with given arguments"""
        try:
            if name not in self._tools:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Tool '{name}' not found"
                )
                
            tool_func = self._tools[name]
            self.logger.debug(f"Executing tool: {name} with args: {arguments}")
            
            # Execute the tool
            result = tool_func(**arguments)
            
            return ToolResult(
                success=True,
                output=result,
                metadata={"tool_name": name, "arguments": arguments}
            )
            
        except Exception as e:
            self.logger.error(f"Tool execution failed for {name}: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                metadata={"tool_name": name, "arguments": arguments}
            )


# Global tool registry
_global_registry = ToolRegistry()


def tool(
    name: str = None,
    description: str = None,
    parameters: Dict[str, Any] = None
):
    """
    Decorator to register a function as a tool
    
    Usage:
    @tool(
        name="read_file",
        description="Read contents of a file",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file"}
            },
            "required": ["file_path"]
        }
    )
    def read_file(file_path: str) -> str:
        with open(file_path, 'r') as f:
            return f.read()
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Tool: {tool_name}"
        
        # Auto-generate parameters from function signature if not provided
        tool_parameters = parameters or _generate_parameters_from_signature(func)
        
        # Register the tool
        _global_registry.register(tool_name, func, tool_description, tool_parameters)
        
        # Mark the function as a tool
        func._is_tool = True
        func._tool_name = tool_name
        
        return func
    
    return decorator


def get_registry() -> ToolRegistry:
    """Get the global tool registry"""
    return _global_registry


def _generate_parameters_from_signature(func: Callable) -> Dict[str, Any]:
    """Auto-generate JSON schema parameters from function signature"""
    sig = inspect.signature(func)
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue
            
        # Basic type mapping
        param_type = "string"  # Default
        if param.annotation != inspect.Parameter.empty:
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list:
                param_type = "array"
            elif param.annotation == dict:
                param_type = "object"
                
        properties[param_name] = {
            "type": param_type,
            "description": f"Parameter: {param_name}"
        }
        
        # Add to required if no default value
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        "type": "object",
        "properties": properties,
        "required": required
    }