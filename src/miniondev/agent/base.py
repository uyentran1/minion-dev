"""
Core agent foundation - the base classes and message loop system
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from miniondev.llm.client import ChatClient, ChatMessage, ChatCompletionResponse, ToolCall, ToolResult
from miniondev.tools import get_registry


class AgentState(Enum):
    """Agent execution states"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(Enum):
    """Agent types for type safety and identification"""
    SIMPLE = "simple"
    PLANNER = "planner"
    EXECUTOR = "executor"
    FINALIZER = "finalizer"


@dataclass
class AgentContext:
    """Context information passed between agents"""
    work_item_id: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    shared_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result from agent execution"""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    next_action: Optional[str] = None
    errors: List[str] = field(default_factory=list)


class Agent(ABC):
    """
    Abstract base class for all MinionDev agents
    
    Provides the core message loop and state management that all agents inherit.
    Each agent implements specific behavior through the execute() method.
    """
    
    def __init__(self, llm_client: ChatClient, agent_type: AgentType):
        self.llm_client = llm_client
        self.agent_type = agent_type
        self.state = AgentState.IDLE
        self.logger = logging.getLogger(f"{__name__}.{agent_type.value}")
        
        # Conversation state
        self.messages: List[ChatMessage] = []
        self.context: Optional[AgentContext] = None
        self.max_conversation_length = 50  # Prevent memory issues in long conversations
        self.max_turns = 10  # Prevent infinite loops; override in subclasses that need more exploration
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt that defines this agent's role and capabilities"""
        pass
    
    @abstractmethod
    def execute(self, context: AgentContext, input_data: Dict[str, Any]) -> AgentResult:
        """Execute the agent's main task with given context and input"""
        pass

    def get_available_tools(self) -> Optional[List]:
        """Return the tool definitions this agent may use. Override to restrict; None means all registered tools."""
        return None
    
    def initialize_conversation(self, context: AgentContext, initial_message: str = None):
        """Initialize a new conversation with system prompt and optional initial message"""
        self.context = context
        self.state = AgentState.IDLE
        
        # Start with system prompt
        self.messages = [
            ChatMessage(role="system", content=self.get_system_prompt())
        ]
        
        if initial_message:
            self.messages.append(
                ChatMessage(role="user", content=initial_message)
            )
            
        self.logger.info(f"Initialized conversation for {self.agent_type} agent")
    
    def add_message(
        self,
        role: str,
        content: str = "",
        tool_calls: Optional[List[ToolCall]] = None,
        tool_results: Optional[List[ToolResult]] = None,
    ):
        """Add a message to the conversation with automatic length management"""
        self.messages.append(
            ChatMessage(role=role, content=content, tool_calls=tool_calls, tool_results=tool_results)
        )
        self.logger.debug(f"Added {role} message: {content[:100]}...")
        
        # Trim conversation if it gets too long (keep system message + recent messages)
        if len(self.messages) > self.max_conversation_length:
            system_message = self.messages[0] if self.messages[0].role == "system" else None
            recent_messages = self.messages[-(self.max_conversation_length - 1):]
            
            self.messages = [system_message] + recent_messages if system_message else recent_messages
            self.logger.debug(f"Trimmed conversation to {len(self.messages)} messages")
    
    def call_llm(self, tools: Optional[List] = None, max_tokens: int = 4000) -> ChatCompletionResponse:
        """Make a call to the LLM with current conversation state"""
        if not self.messages:
            raise ValueError("No messages in conversation. Call initialize_conversation() first.")
        
        self.state = AgentState.THINKING
        
        try:
            # Use tools from registry if none provided
            if tools is None:
                tools = get_registry().get_tool_definitions()
            
            self.logger.debug(f"Calling LLM with {len(self.messages)} messages and {len(tools) if tools else 0} tools")
            response = self.llm_client.chat_completion(
                messages=self.messages,
                tools=tools,
                max_tokens=max_tokens
            )
            
            # Add assistant response (text and/or tool calls) as a single structured
            # message - Bedrock Converse requires one message per turn, with any
            # toolUse blocks alongside text in the same content list.
            if response.content or response.tool_calls:
                self.add_message(
                    "assistant", response.content or "", tool_calls=response.tool_calls
                )
            
            self.state = AgentState.ACTING if response.tool_calls else AgentState.IDLE
            return response
            
        except Exception as e:
            self.state = AgentState.FAILED
            self.logger.error(f"LLM call failed: {e}")
            raise
    
    def run_conversation_loop(self, context: AgentContext, input_data: Dict[str, Any]) -> AgentResult:
        """
        Run the main conversation loop for this agent
        
        This is the core of the agent system - it manages the conversation flow
        between the agent and the LLM, handling tool calls and state transitions.
        """
        try:
            self.logger.info(f"Starting conversation loop for {self.agent_type} agent")
            
            # Initialize conversation 
            initial_prompt = self._build_initial_prompt(input_data)
            self.initialize_conversation(context, initial_prompt)
            
            # Main conversation loop
            max_turns = self.max_turns
            turn_count = 0

            while turn_count < max_turns and self.state not in [AgentState.COMPLETED, AgentState.FAILED]:
                turn_count += 1
                self.logger.debug(f"Conversation turn {turn_count}")
                
                # Get LLM response
                response = self.call_llm(tools=self.get_available_tools())
                
                # Handle tool calls if present - all results for this turn go into a
                # single user message, one toolResult block per toolUseId, matching
                # how Converse expects multi-tool-use turns to be answered.
                if response.tool_calls:
                    tool_results = []
                    for tool_call in response.tool_calls:
                        content, is_error = self._execute_tool_call(tool_call)
                        tool_results.append(
                            ToolResult(tool_use_id=tool_call.id, content=content, is_error=is_error)
                        )
                    self.add_message("user", tool_results=tool_results)
                
                # Check if agent has completed its task (no tool calls and has content)
                if self._is_task_complete(response):
                    self.state = AgentState.COMPLETED
                    break
            
            if turn_count >= max_turns:
                self.logger.warning(f"Agent reached max turns ({max_turns})")
                self.state = AgentState.FAILED
                return AgentResult(
                    success=False,
                    message=f"Agent reached maximum conversation turns ({max_turns})",
                    errors=["Max turns exceeded"]
                )
            
            # Extract final result
            return self._extract_final_result()
            
        except Exception as e:
            self.logger.error(f"Conversation loop failed: {e}")
            self.state = AgentState.FAILED
            return AgentResult(
                success=False,
                message=f"Agent execution failed: {str(e)}",
                errors=[str(e)]
            )
    
    def _build_initial_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build the initial user prompt based on input data - override in subclasses"""
        return f"Please process this input: {input_data}"
    
    def _execute_tool_call(self, tool_call: ToolCall) -> tuple[str, bool]:
        """Execute a tool call using the tool registry. Returns (content, is_error)."""
        try:
            registry = get_registry()
            result = registry.execute_tool(tool_call.name, tool_call.arguments)

            if result.success:
                self.logger.debug(f"Tool {tool_call.name} executed successfully")
                return str(result.output), False
            else:
                self.logger.error(f"Tool {tool_call.name} failed: {result.error}")
                return f"Tool execution failed: {result.error}", True

        except Exception as e:
            self.logger.error(f"Tool execution error: {e}")
            return f"Tool execution error: {str(e)}", True
    
    def _is_task_complete(self, response: ChatCompletionResponse) -> bool:
        """Check if the agent's task is complete - override in subclasses"""
        # Default: task is complete if there are no tool calls and we have content
        return not response.tool_calls and response.content
    
    def _extract_final_result(self) -> AgentResult:
        """Extract the final result from the conversation - override in subclasses"""
        if self.messages and self.messages[-1].role == "assistant":
            return AgentResult(
                success=True,
                message=self.messages[-1].content,
                data={"conversation_turns": len(self.messages)}
            )
        else:
            return AgentResult(
                success=False,
                message="No final response from agent",
                errors=["Missing final response"]
            )


class SimpleAgent(Agent):
    """
    A simple concrete implementation of Agent for testing and basic use cases
    """
    
    def __init__(self, llm_client: ChatClient, system_prompt: str = None):
        super().__init__(llm_client, AgentType.SIMPLE)
        self._custom_system_prompt = system_prompt
    
    def get_system_prompt(self) -> str:
        return self._custom_system_prompt or "You are a helpful AI assistant."
    
    def execute(self, context: AgentContext, input_data: Dict[str, Any]) -> AgentResult:
        """Execute using the conversation loop"""
        return self.run_conversation_loop(context, input_data)