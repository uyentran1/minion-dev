import boto3
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from botocore.exceptions import ClientError, NoCredentialsError


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    tool_use_id: str
    content: str
    is_error: bool = False


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str = ""
    # Structured Converse content blocks. An assistant message may carry tool_calls
    # (the toolUse blocks it issued); a user message may carry tool_results (the
    # toolResult blocks answering them, correlated by tool_use_id/toolUseId).
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None


class ChatCompletionResponse(BaseModel):
    content: str
    tool_calls: Optional[List[ToolCall]] = None


class ChatClient(ABC):
    """Abstract base class for LLM chat clients"""
    
    @abstractmethod
    def chat_completion(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4000
    ) -> ChatCompletionResponse:
        pass


class BedrockChatClient(ChatClient):
    """AWS Bedrock chat client using Converse API"""
    
    def __init__(self, region_name: str = None, model_id: str = None):
        self.logger = logging.getLogger(__name__)
        
        # Use environment variables or defaults
        self.region_name = region_name or os.getenv("BEDROCK_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-north-1"))
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
        
        try:
            # Load .env file if available
            self._load_env_file()
            
            # Check for bearer token (required)
            bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
            if not bearer_token:
                raise ValueError("AWS_BEARER_TOKEN_BEDROCK environment variable is required")
            
            # Set up AWS session with bearer token
            os.environ["AWS_SESSION_TOKEN"] = bearer_token
            os.environ["AWS_ACCESS_KEY_ID"] = "dummy"  # Required by boto3
            os.environ["AWS_SECRET_ACCESS_KEY"] = "dummy"  # Required by boto3
            
            self.client = boto3.client("bedrock-runtime", region_name=self.region_name)
            self.logger.info(f"Initialized Bedrock client with bearer token in region {self.region_name}")
            
        except ValueError as e:
            self.logger.error(str(e))
            raise
        except Exception as e:
            self.logger.error(f"Failed to initialize Bedrock client: {e}")
            raise
    
    def _load_env_file(self):
        """Load environment variables from .env file if it exists"""
        try:
            import os
            from pathlib import Path
            
            # Look for .env in project root (current working directory)
            env_file = Path.cwd() / ".env"
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key, value = key.strip(), value.strip()
                            os.environ.setdefault(key, value)
                self.logger.debug(f"Loaded .env file from {env_file}")
            else:
                self.logger.debug(f".env file not found at {env_file}")
        except Exception as e:
            self.logger.debug(f"Error loading .env file: {e}")
    
    def chat_completion(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4000
    ) -> ChatCompletionResponse:
        """Send chat completion request using Bedrock Converse API"""
        
        # Convert messages to Converse format
        system_message = None
        conversation = []
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
                continue

            content_blocks = []
            if msg.content:
                content_blocks.append({"text": msg.content})

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    content_blocks.append({
                        "toolUse": {
                            "toolUseId": tool_call.id,
                            "name": tool_call.name,
                            "input": tool_call.arguments,
                        }
                    })

            if msg.tool_results:
                for tool_result in msg.tool_results:
                    content_blocks.append({
                        "toolResult": {
                            "toolUseId": tool_result.tool_use_id,
                            "content": [{"text": tool_result.content}],
                            "status": "error" if tool_result.is_error else "success",
                        }
                    })

            conversation.append({
                "role": msg.role,
                "content": content_blocks
            })
        
        # Build request parameters
        request_params = {
            "modelId": self.model_id,
            "messages": conversation,
            "inferenceConfig": {
                "maxTokens": max_tokens
            }
        }
        
        if system_message:
            request_params["system"] = [{"text": system_message}]
            
        if tools:
            request_params["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": {
                                "json": tool.input_schema
                            }
                        }
                    }
                    for tool in tools
                ]
            }
        
        try:
            self.logger.debug(f"Making Bedrock request with {len(messages)} messages")
            response = self.client.converse(**request_params)
            
            # Extract content and tool calls from Converse response
            content = ""
            tool_calls = []
            
            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            
            for block in content_blocks:
                if "text" in block:
                    content += block["text"]
                elif "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_calls.append(ToolCall(
                        id=tool_use["toolUseId"],
                        name=tool_use["name"],
                        arguments=tool_use["input"]
                    ))
            
            self.logger.debug(f"Received response with content length: {len(content)}, tool calls: {len(tool_calls)}")
            
            return ChatCompletionResponse(
                content=content,
                tool_calls=tool_calls if tool_calls else None
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            self.logger.error(f"Bedrock API error ({error_code}): {error_msg}")
            raise Exception(f"Bedrock API error ({error_code}): {error_msg}")
        except Exception as e:
            self.logger.error(f"Unexpected error in Bedrock client: {str(e)}")
            raise Exception(f"Bedrock client error: {str(e)}")


class MockChatClient(ChatClient):
    """Mock client for testing without API calls"""

    def __init__(
        self,
        content: str = "This is a mock response for testing.",
        tool_calls: Optional[List[ToolCall]] = None
    ):
        self.content = content
        self.tool_calls = tool_calls

    def chat_completion(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4000
    ) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            content=self.content,
            tool_calls=self.tool_calls
        )