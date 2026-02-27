"""Phoenix tracing integration for nanobot."""

import os
from functools import wraps
from typing import Any, Callable

from loguru import logger


_tracer = None
_tracer_initialized = False


def init_phoenix_tracing(
    collector_endpoint: str | None = None,
    project_name: str = "nanobot",
    auto_instrument: bool = False,
) -> bool:
    """
    Initialize Phoenix OTEL tracing.
    
    Args:
        collector_endpoint: Phoenix collector endpoint URL (e.g., "http://localhost:4318/v1/traces" for HTTP or "http://localhost:4317" for gRPC).
        project_name: Project name for grouping traces.
        auto_instrument: Enable auto-instrumentation for AI libraries.
    
    Returns:
        True if initialization succeeded, False otherwise.
    """
    global _tracer, _tracer_initialized
    
    if _tracer_initialized:
        logger.info("Phoenix tracing already initialized")
        return True
    
    try:
        from phoenix.otel import register as register_phoenix
        from opentelemetry import trace
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        
        endpoint = collector_endpoint or os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        if not endpoint:
            logger.warning("Phoenix collector endpoint not configured, tracing disabled")
            return False
        
        logger.info("Initializing Phoenix tracing with endpoint: {}", endpoint)
        logger.info("Project name: {}", project_name)
        
        # Register Phoenix with default settings (uses BatchSpanProcessor internally)
        tracer_provider = register_phoenix(
            project_name=project_name,
            endpoint=endpoint,
        )
        
        _tracer = trace.get_tracer(__name__)
        _tracer_initialized = True
        logger.info("Phoenix tracing initialized successfully")
        
        # Test tracer by creating a test span
        with _tracer.start_as_current_span("phoenix.init_test") as span:
            span.set_attribute("test", "initialization")
            span.set_status({"status_code": 1, "description": "OK"})
            logger.info("Test span created successfully")
        
        # Force flush to ensure test span is sent
        try:
            tracer_provider.force_flush()
            logger.info("Tracer provider flushed successfully")
        except Exception as flush_error:
            logger.warning("Failed to flush tracer provider: {}", flush_error)
        
        return True
        
    except ImportError as e:
        logger.warning("Phoenix OTEL package not installed: {}", e)
        logger.warning("Install with: pip install arize-phoenix-otel")
        return False
    except Exception as e:
        logger.error("Failed to initialize Phoenix tracing: {}", e)
        logger.exception("Full traceback:")
        return False


def get_tracer():
    """Get the global tracer instance."""
    return _tracer


def trace_llm_call(func: Callable) -> Callable:
    """
    Decorator to trace LLM calls.
    
    Usage:
        @trace_llm_call
        async def chat(self, messages, ...):
            ...
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not _tracer_initialized or _tracer is None:
            return await func(*args, **kwargs)
        
        with _tracer.start_as_current_span("llm.chat") as span:
            try:
                model = kwargs.get("model", "unknown")
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.type", "chat")
                
                messages = kwargs.get("messages", [])
                if messages:
                    span.set_attribute("llm.messages.count", len(messages))
                    
                    # Add message context (first and last messages)
                    if len(messages) > 0:
                        first_msg = messages[0]
                        if isinstance(first_msg, dict):
                            role = first_msg.get("role", "unknown")
                            content = first_msg.get("content", "")
                            span.set_attribute("llm.messages.first.role", role)
                            if isinstance(content, str):
                                span.set_attribute("llm.messages.first.content", content[:500])
                            elif isinstance(content, list):
                                span.set_attribute("llm.messages.first.content_type", "list")
                    
                    if len(messages) > 1:
                        last_msg = messages[-1]
                        if isinstance(last_msg, dict):
                            role = last_msg.get("role", "unknown")
                            content = last_msg.get("content", "")
                            span.set_attribute("llm.messages.last.role", role)
                            if isinstance(content, str):
                                span.set_attribute("llm.messages.last.content", content[:500])
                            elif isinstance(content, list):
                                span.set_attribute("llm.messages.last.content_type", "list")
                
                result = await func(*args, **kwargs)
                
                if hasattr(result, "usage") and result.usage:
                    span.set_attribute("llm.tokens.prompt", result.usage.get("prompt_tokens", 0))
                    span.set_attribute("llm.tokens.completion", result.usage.get("completion_tokens", 0))
                    span.set_attribute("llm.tokens.total", result.usage.get("total_tokens", 0))
                
                if hasattr(result, "finish_reason"):
                    span.set_attribute("llm.finish_reason", result.finish_reason)
                
                if hasattr(result, "tool_calls") and result.tool_calls:
                    span.set_attribute("llm.tool_calls.count", len(result.tool_calls))
                    tool_names = [tc.name for tc in result.tool_calls]
                    span.set_attribute("llm.tool_calls.names", ", ".join(tool_names))
                
                span.set_status({"status_code": 1, "description": "OK"})
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status({"status_code": 2, "description": str(e)})
                raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not _tracer_initialized or _tracer is None:
            return func(*args, **kwargs)
        
        with _tracer.start_as_current_span("llm.chat") as span:
            try:
                model = kwargs.get("model", "unknown")
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.type", "chat")
                
                messages = kwargs.get("messages", [])
                if messages:
                    span.set_attribute("llm.messages.count", len(messages))
                    
                    # Add message context (first and last messages)
                    if len(messages) > 0:
                        first_msg = messages[0]
                        if isinstance(first_msg, dict):
                            role = first_msg.get("role", "unknown")
                            content = first_msg.get("content", "")
                            span.set_attribute("llm.messages.first.role", role)
                            if isinstance(content, str):
                                span.set_attribute("llm.messages.first.content", content[:500])
                            elif isinstance(content, list):
                                span.set_attribute("llm.messages.first.content_type", "list")
                    
                    if len(messages) > 1:
                        last_msg = messages[-1]
                        if isinstance(last_msg, dict):
                            role = last_msg.get("role", "unknown")
                            content = last_msg.get("content", "")
                            span.set_attribute("llm.messages.last.role", role)
                            if isinstance(content, str):
                                span.set_attribute("llm.messages.last.content", content[:500])
                            elif isinstance(content, list):
                                span.set_attribute("llm.messages.last.content_type", "list")
                
                result = func(*args, **kwargs)
                
                if hasattr(result, "usage") and result.usage:
                    span.set_attribute("llm.tokens.prompt", result.usage.get("prompt_tokens", 0))
                    span.set_attribute("llm.tokens.completion", result.usage.get("completion_tokens", 0))
                    span.set_attribute("llm.tokens.total", result.usage.get("total_tokens", 0))
                
                if hasattr(result, "finish_reason"):
                    span.set_attribute("llm.finish_reason", result.finish_reason)
                
                span.set_status({"status_code": 1, "description": "OK"})
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status({"status_code": 2, "description": str(e)})
                raise
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def trace_tool_call(func: Callable) -> Callable:
    """
    Decorator to trace tool calls.
    
    Usage:
        @trace_tool_call
        async def execute(self, tool_name, arguments):
            ...
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not _tracer_initialized or _tracer is None:
            return await func(*args, **kwargs)
        
        tool_name = kwargs.get("tool_name", args[1] if len(args) > 1 else "unknown")
        
        with _tracer.start_as_current_span(f"tool.{tool_name}") as span:
            try:
                span.set_attribute("tool.name", tool_name)
                
                arguments = kwargs.get("arguments", args[2] if len(args) > 2 else {})
                if arguments:
                    span.set_attribute("tool.arguments", str(arguments)[:1000])
                
                result = await func(*args, **kwargs)
                
                span.set_status({"status_code": 1, "description": "OK"})
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status({"status_code": 2, "description": str(e)})
                raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not _tracer_initialized or _tracer is None:
            return func(*args, **kwargs)
        
        tool_name = kwargs.get("tool_name", args[1] if len(args) > 1 else "unknown")
        
        with _tracer.start_as_current_span(f"tool.{tool_name}") as span:
            try:
                span.set_attribute("tool.name", tool_name)
                
                arguments = kwargs.get("arguments", args[2] if len(args) > 2 else {})
                if arguments:
                    span.set_attribute("tool.arguments", str(arguments)[:1000])
                
                result = func(*args, **kwargs)
                
                span.set_status({"status_code": 1, "description": "OK"})
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status({"status_code": 2, "description": str(e)})
                raise
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def trace_agent_message(func: Callable) -> Callable:
    """
    Decorator to trace agent message processing.
    
    Usage:
        @trace_agent_message
        async def _process_message(self, msg):
            ...
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not _tracer_initialized or _tracer is None:
            return await func(*args, **kwargs)
        
        msg = kwargs.get("msg", args[1] if len(args) > 1 else None)
        
        with _tracer.start_as_current_span("agent.process_message") as span:
            try:
                if msg:
                    span.set_attribute("agent.channel", msg.channel)
                    span.set_attribute("agent.sender_id", msg.sender_id)
                    span.set_attribute("agent.message_length", len(msg.content))
                
                result = await func(*args, **kwargs)
                
                span.set_status({"status_code": 1, "description": "OK"})
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status({"status_code": 2, "description": str(e)})
                raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not _tracer_initialized or _tracer is None:
            return func(*args, **kwargs)
        
        msg = kwargs.get("msg", args[1] if len(args) > 1 else None)
        
        with _tracer.start_as_current_span("agent.process_message") as span:
            try:
                if msg:
                    span.set_attribute("agent.channel", msg.channel)
                    span.set_attribute("agent.sender_id", msg.sender_id)
                    span.set_attribute("agent.message_length", len(msg.content))
                
                result = func(*args, **kwargs)
                
                span.set_status({"status_code": 1, "description": "OK"})
                return result
                
            except Exception as e:
                span.record_exception(e)
                span.set_status({"status_code": 2, "description": str(e)})
                raise
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


__all__ = [
    "init_phoenix_tracing",
    "get_tracer",
    "trace_llm_call",
    "trace_tool_call",
    "trace_agent_message",
]
