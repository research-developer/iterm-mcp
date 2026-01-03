"""OpenTelemetry instrumentation for iTerm MCP server.

This module provides production-grade observability through OpenTelemetry,
enabling tracing of agent operations, message delivery, and command execution.

Configuration:
    Environment variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4317)
    - OTEL_SERVICE_NAME: Service name (default: iterm-mcp)
    - OTEL_TRACES_EXPORTER: Exporter type (otlp, console, none)
    - OTEL_ENABLED: Enable/disable tracing (default: true)
    - OTEL_CONSOLE_EXPORTER: Use console exporter for debugging (default: false)

Usage:
    from utils.otel import get_tracer, trace_operation, init_tracing

    # Initialize at startup
    init_tracing()

    # Use decorator for automatic tracing
    @trace_operation("my_operation")
    async def my_function():
        ...

    # Or use tracer directly
    tracer = get_tracer()
    with tracer.start_as_current_span("my_span") as span:
        span.set_attribute("key", "value")
"""

import asyncio
import functools
import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar, Union

# OpenTelemetry imports with graceful fallback
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode, Span, Tracer
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes

    # OTLP exporter - optional dependency
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        OTLP_AVAILABLE = True
    except ImportError:
        OTLP_AVAILABLE = False

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    OTLP_AVAILABLE = False

logger = logging.getLogger("iterm-mcp.otel")

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])

# Global tracer instance
_tracer: Optional[Any] = None
_initialized: bool = False

# Configuration from environment
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "iterm-mcp")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_EXPORTER = os.getenv("OTEL_TRACES_EXPORTER", "otlp")
OTEL_CONSOLE = os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() in ("true", "1", "yes")


class NoOpSpan:
    """No-op span implementation when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def __enter__(self) -> "NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class NoOpTracer:
    """No-op tracer implementation when OpenTelemetry is not available."""

    def start_as_current_span(
        self,
        name: str,
        **kwargs: Any
    ) -> NoOpSpan:
        return NoOpSpan()

    @contextmanager
    def start_span(self, name: str, **kwargs: Any):
        yield NoOpSpan()


def init_tracing(
    service_name: Optional[str] = None,
    endpoint: Optional[str] = None,
    console_exporter: Optional[bool] = None,
) -> bool:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Override OTEL_SERVICE_NAME
        endpoint: Override OTEL_EXPORTER_OTLP_ENDPOINT
        console_exporter: Override OTEL_CONSOLE_EXPORTER

    Returns:
        True if tracing was initialized, False otherwise
    """
    global _tracer, _initialized

    if _initialized:
        return True

    if not OTEL_AVAILABLE:
        logger.info(
            "OpenTelemetry not available - install with: "
            "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
        )
        _tracer = NoOpTracer()
        _initialized = True
        return False

    if not OTEL_ENABLED:
        logger.info("OpenTelemetry tracing disabled via OTEL_ENABLED=false")
        _tracer = NoOpTracer()
        _initialized = True
        return False

    # Use provided values or fall back to environment/defaults
    svc_name = service_name or OTEL_SERVICE_NAME
    otlp_endpoint = endpoint or OTEL_ENDPOINT
    use_console = console_exporter if console_exporter is not None else OTEL_CONSOLE

    try:
        # Create resource with service information
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: svc_name,
            ResourceAttributes.SERVICE_VERSION: "0.1.0",
            "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "development"),
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add exporters based on configuration
        exporter_added = False

        if use_console:
            # Console exporter for debugging
            console_processor = SimpleSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(console_processor)
            logger.info("OpenTelemetry console exporter enabled")
            exporter_added = True

        if OTEL_EXPORTER == "otlp" and OTLP_AVAILABLE:
            # OTLP exporter for production
            try:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint,
                    insecure=True,  # Use HTTP for local development
                )
                otlp_processor = BatchSpanProcessor(otlp_exporter)
                provider.add_span_processor(otlp_processor)
                logger.info(f"OpenTelemetry OTLP exporter enabled: {otlp_endpoint}")
                exporter_added = True
            except Exception as e:
                logger.warning(f"Failed to initialize OTLP exporter: {e}")
        elif OTEL_EXPORTER == "otlp" and not OTLP_AVAILABLE:
            logger.warning(
                "OTLP exporter requested but not available - "
                "install with: pip install opentelemetry-exporter-otlp"
            )

        if not exporter_added:
            # Fall back to console exporter if nothing else configured
            console_processor = SimpleSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(console_processor)
            logger.info("OpenTelemetry using console exporter (default)")

        # Set the tracer provider
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(svc_name)
        _initialized = True

        logger.info(f"OpenTelemetry tracing initialized for service: {svc_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        _tracer = NoOpTracer()
        _initialized = True
        return False


def get_tracer() -> Union[Any, NoOpTracer]:
    """Get the global tracer instance.

    Returns:
        Tracer instance (or NoOpTracer if not initialized)
    """
    global _tracer

    if _tracer is None:
        init_tracing()

    return _tracer


def shutdown_tracing() -> None:
    """Shutdown tracing and flush pending spans."""
    global _tracer, _initialized

    if OTEL_AVAILABLE and _initialized:
        try:
            provider = trace.get_tracer_provider()
            if hasattr(provider, "shutdown"):
                provider.shutdown()
            logger.info("OpenTelemetry tracing shutdown complete")
        except Exception as e:
            logger.warning(f"Error during tracing shutdown: {e}")

    _tracer = None
    _initialized = False


def trace_operation(
    operation_name: str,
    *,
    extract_agent: bool = True,
    extract_session: bool = True,
    record_args: bool = False,
) -> Callable[[F], F]:
    """Decorator to trace an operation with OpenTelemetry.

    This decorator automatically:
    - Creates a span for the operation
    - Extracts agent and session info from kwargs
    - Records success/failure status
    - Records exceptions

    Args:
        operation_name: Name of the operation (used as span name)
        extract_agent: Extract agent name from kwargs (default: True)
        extract_session: Extract session_id from kwargs (default: True)
        record_args: Record function arguments as attributes (default: False)

    Returns:
        Decorated function with automatic tracing

    Example:
        @trace_operation("write_to_session")
        async def write_to_sessions(request: WriteToSessionsRequest):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()

            with tracer.start_as_current_span(operation_name) as span:
                # Set common attributes
                span.set_attribute("operation.name", operation_name)

                # Extract agent name from various sources
                if extract_agent:
                    agent_name = _extract_agent_name(args, kwargs)
                    if agent_name:
                        span.set_attribute("agent.name", agent_name)

                # Extract session ID from various sources
                if extract_session:
                    session_id = _extract_session_id(args, kwargs)
                    if session_id:
                        span.set_attribute("session.id", session_id)

                # Record arguments if requested
                if record_args:
                    _record_arguments(span, args, kwargs)

                try:
                    result = await func(*args, **kwargs)

                    if OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.OK))

                    # Record result info if applicable
                    _record_result(span, result)

                    return result

                except Exception as e:
                    if OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()

            with tracer.start_as_current_span(operation_name) as span:
                span.set_attribute("operation.name", operation_name)

                if extract_agent:
                    agent_name = _extract_agent_name(args, kwargs)
                    if agent_name:
                        span.set_attribute("agent.name", agent_name)

                if extract_session:
                    session_id = _extract_session_id(args, kwargs)
                    if session_id:
                        span.set_attribute("session.id", session_id)

                if record_args:
                    _record_arguments(span, args, kwargs)

                try:
                    result = func(*args, **kwargs)

                    if OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.OK))

                    _record_result(span, result)
                    return result

                except Exception as e:
                    if OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def _extract_agent_name(args: tuple, kwargs: dict) -> Optional[str]:
    """Extract agent name from function arguments."""
    # Check kwargs directly
    if "agent" in kwargs:
        return kwargs["agent"]
    if "agent_name" in kwargs:
        return kwargs["agent_name"]

    # Check request objects
    request = kwargs.get("request") or (args[0] if args else None)
    if request:
        # Check for agent attribute
        if hasattr(request, "agent"):
            return getattr(request, "agent")
        if hasattr(request, "agent_name"):
            return getattr(request, "agent_name")
        # Check for requesting_agent
        if hasattr(request, "requesting_agent"):
            return getattr(request, "requesting_agent")

    return None


def _extract_session_id(args: tuple, kwargs: dict) -> Optional[str]:
    """Extract session ID from function arguments."""
    # Check kwargs directly
    if "session_id" in kwargs:
        return kwargs["session_id"]

    # Check request objects
    request = kwargs.get("request") or (args[0] if args else None)
    if request:
        if hasattr(request, "session_id"):
            return getattr(request, "session_id")
        # Check targets for session_id
        if hasattr(request, "targets"):
            targets = getattr(request, "targets")
            if targets and len(targets) > 0:
                first_target = targets[0]
                if hasattr(first_target, "session_id"):
                    return getattr(first_target, "session_id")

    return None


def _record_arguments(span: Any, args: tuple, kwargs: dict) -> None:
    """Record function arguments as span attributes."""
    try:
        for i, arg in enumerate(args):
            if isinstance(arg, (str, int, float, bool)):
                span.set_attribute(f"arg.{i}", str(arg))
            elif hasattr(arg, "__class__"):
                span.set_attribute(f"arg.{i}.type", arg.__class__.__name__)

        for key, value in kwargs.items():
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(f"kwarg.{key}", str(value))
            elif hasattr(value, "__class__"):
                span.set_attribute(f"kwarg.{key}.type", value.__class__.__name__)
    except Exception:
        pass  # Don't fail tracing due to argument recording


def _record_result(span: Any, result: Any) -> None:
    """Record result information as span attributes."""
    try:
        if result is None:
            return

        # Record result type
        span.set_attribute("result.type", type(result).__name__)

        # Record specific result attributes for known types
        if hasattr(result, "sent_count"):
            span.set_attribute("result.sent_count", result.sent_count)
        if hasattr(result, "skipped_count"):
            span.set_attribute("result.skipped_count", result.skipped_count)
        if hasattr(result, "error_count"):
            span.set_attribute("result.error_count", result.error_count)
        if hasattr(result, "total_sessions"):
            span.set_attribute("result.total_sessions", result.total_sessions)
        if hasattr(result, "success"):
            span.set_attribute("result.success", result.success)
    except Exception:
        pass  # Don't fail tracing due to result recording


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current span.

    Args:
        **attributes: Key-value pairs to add as span attributes

    Example:
        add_span_attributes(
            team="backend",
            message_count=5,
            operation_type="cascade"
        )
    """
    if not OTEL_AVAILABLE:
        return

    try:
        span = trace.get_current_span()
        for key, value in attributes.items():
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(key, value)
            else:
                span.set_attribute(key, str(value))
    except Exception:
        pass  # Don't fail if span not available


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Add an event to the current span.

    Args:
        name: Event name
        attributes: Optional event attributes

    Example:
        add_span_event("message_delivered", {"recipient": "agent-1"})
    """
    if not OTEL_AVAILABLE:
        return

    try:
        span = trace.get_current_span()
        span.add_event(name, attributes=attributes or {})
    except Exception:
        pass  # Don't fail if span not available


@contextmanager
def create_span(
    name: str,
    *,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
):
    """Context manager to create a child span.

    Args:
        name: Span name
        attributes: Optional span attributes
        record_exception: Whether to record exceptions (default: True)

    Yields:
        Span object (or NoOpSpan if tracing unavailable)

    Example:
        with create_span("process_message", attributes={"message_id": "123"}):
            process_message(msg)
    """
    tracer = get_tracer()

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            if record_exception and OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise
        else:
            if OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.OK))
