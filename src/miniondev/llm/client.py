import boto3
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class ChatCompletionResponse(BaseModel):
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None


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
    
    def __init__(self, region_name: str = "eu-north-1", model_id: str = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"):
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.model_id = model_id
    
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
            else:
                conversation.append({
                    "role": msg.role,
                    "content": [{"text": msg.content}]
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
                    tool_calls.append({
                        "id": tool_use["toolUseId"],
                        "name": tool_use["name"],
                        "arguments": tool_use["input"]
                    })
            
            return ChatCompletionResponse(
                content=content,
                tool_calls=tool_calls if tool_calls else None
            )
            
        except Exception as e:
            raise Exception(f"Bedrock Converse API error: {str(e)}")


class MockChatClient(ChatClient):
    """Mock client for testing without API calls"""
    
    def chat_completion(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4000
    ) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            content="This is a mock response for testing."
        )