"""Tests for OpenTelemetry instrumentation module."""

import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch


class TestOtelModule(unittest.TestCase):
    """Test the OpenTelemetry instrumentation module."""

    def setUp(self):
        """Reset module state before each test."""
        # Clear any cached module state
        import utils.otel as otel_module
        otel_module._tracer = None
        otel_module._initialized = False

    def tearDown(self):
        """Clean up after each test."""
        from utils.otel import shutdown_tracing
        shutdown_tracing()

    def test_init_tracing_without_otel_installed(self):
        """Test graceful fallback when OpenTelemetry is not installed."""
        import utils.otel as otel_module

        # Simulate OTEL not being available
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False

        try:
            from utils.otel import init_tracing, get_tracer, NoOpTracer

            result = init_tracing()
            self.assertFalse(result)

            tracer = get_tracer()
            self.assertIsInstance(tracer, NoOpTracer)
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_init_tracing_disabled_via_env(self):
        """Test that tracing can be disabled via environment variable."""
        import utils.otel as otel_module

        original_enabled = otel_module.OTEL_ENABLED
        otel_module.OTEL_ENABLED = False

        try:
            from utils.otel import init_tracing, get_tracer, NoOpTracer

            result = init_tracing()
            self.assertFalse(result)

            tracer = get_tracer()
            self.assertIsInstance(tracer, NoOpTracer)
        finally:
            otel_module.OTEL_ENABLED = original_enabled

    def test_noop_span_methods(self):
        """Test that NoOpSpan methods don't raise exceptions."""
        from utils.otel import NoOpSpan

        span = NoOpSpan()

        # These should all work without error
        span.set_attribute("key", "value")
        span.set_status(None)
        span.record_exception(Exception("test"))
        span.add_event("test_event", {"key": "value"})

        # Test context manager
        with span as s:
            self.assertIsInstance(s, NoOpSpan)

    def test_noop_tracer_methods(self):
        """Test that NoOpTracer methods return NoOpSpan."""
        from utils.otel import NoOpTracer, NoOpSpan

        tracer = NoOpTracer()

        # Test start_as_current_span
        span = tracer.start_as_current_span("test_span")
        self.assertIsInstance(span, NoOpSpan)

        # Test start_span context manager
        with tracer.start_span("test_span") as span:
            self.assertIsInstance(span, NoOpSpan)

    def test_get_tracer_initializes_if_needed(self):
        """Test that get_tracer auto-initializes if not done."""
        import utils.otel as otel_module

        # Ensure not initialized
        otel_module._tracer = None
        otel_module._initialized = False

        from utils.otel import get_tracer

        tracer = get_tracer()
        # Should have initialized and returned a tracer
        self.assertIsNotNone(tracer)

    def test_trace_operation_decorator_sync(self):
        """Test trace_operation decorator on sync function."""
        from utils.otel import trace_operation, init_tracing

        # Initialize with NoOp for testing
        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            @trace_operation("test.sync_operation")
            def sync_function(x, y):
                return x + y

            result = sync_function(1, 2)
            self.assertEqual(result, 3)
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_trace_operation_decorator_async(self):
        """Test trace_operation decorator on async function."""
        from utils.otel import trace_operation, init_tracing

        # Initialize with NoOp for testing
        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            @trace_operation("test.async_operation")
            async def async_function(x, y):
                return x + y

            result = asyncio.get_event_loop().run_until_complete(async_function(3, 4))
            self.assertEqual(result, 7)
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_trace_operation_exception_handling(self):
        """Test that trace_operation properly handles exceptions."""
        from utils.otel import trace_operation, init_tracing

        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            @trace_operation("test.exception_operation")
            def failing_function():
                raise ValueError("Test error")

            with self.assertRaises(ValueError):
                failing_function()
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_add_span_attributes_without_otel(self):
        """Test add_span_attributes is safe without OTEL."""
        from utils.otel import add_span_attributes, init_tracing

        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            # Should not raise
            add_span_attributes(key="value", number=42)
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_add_span_event_without_otel(self):
        """Test add_span_event is safe without OTEL."""
        from utils.otel import add_span_event, init_tracing

        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            # Should not raise
            add_span_event("test_event", {"key": "value"})
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_create_span_context_manager(self):
        """Test create_span context manager."""
        from utils.otel import create_span, init_tracing

        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            with create_span("test_span", attributes={"key": "value"}) as span:
                # Should work without error
                self.assertIsNotNone(span)
        finally:
            otel_module.OTEL_AVAILABLE = original_available

    def test_extract_agent_name_from_kwargs(self):
        """Test _extract_agent_name helper function."""
        from utils.otel import _extract_agent_name

        # Test direct kwargs
        result = _extract_agent_name((), {"agent": "test-agent"})
        self.assertEqual(result, "test-agent")

        result = _extract_agent_name((), {"agent_name": "test-agent-2"})
        self.assertEqual(result, "test-agent-2")

        # Test when not present
        result = _extract_agent_name((), {})
        self.assertIsNone(result)

    def test_extract_session_id_from_kwargs(self):
        """Test _extract_session_id helper function."""
        from utils.otel import _extract_session_id

        # Test direct kwargs
        result = _extract_session_id((), {"session_id": "session-123"})
        self.assertEqual(result, "session-123")

        # Test when not present
        result = _extract_session_id((), {})
        self.assertIsNone(result)

    def test_shutdown_tracing(self):
        """Test shutdown_tracing clears state."""
        from utils.otel import init_tracing, shutdown_tracing, get_tracer

        import utils.otel as otel_module
        original_available = otel_module.OTEL_AVAILABLE
        otel_module.OTEL_AVAILABLE = False
        init_tracing()

        try:
            # Should be initialized
            self.assertTrue(otel_module._initialized)

            shutdown_tracing()

            # Should be reset
            self.assertFalse(otel_module._initialized)
            self.assertIsNone(otel_module._tracer)
        finally:
            otel_module.OTEL_AVAILABLE = original_available


class TestOtelWithMockedSDK(unittest.TestCase):
    """Test OpenTelemetry with mocked SDK for full coverage."""

    def setUp(self):
        """Reset module state before each test."""
        import utils.otel as otel_module
        otel_module._tracer = None
        otel_module._initialized = False

    def tearDown(self):
        """Clean up after each test."""
        from utils.otel import shutdown_tracing
        shutdown_tracing()

    @patch.dict(os.environ, {"OTEL_CONSOLE_EXPORTER": "true"})
    def test_init_with_console_exporter(self):
        """Test initialization with console exporter."""
        # This test will only work if OTEL is installed
        import utils.otel as otel_module

        if not otel_module.OTEL_AVAILABLE:
            self.skipTest("OpenTelemetry not installed")

        # Reset state
        otel_module._tracer = None
        otel_module._initialized = False
        otel_module.OTEL_CONSOLE = True

        try:
            result = otel_module.init_tracing()
            self.assertTrue(result)
        finally:
            otel_module.OTEL_CONSOLE = False
            otel_module.shutdown_tracing()


class TestTraceOperationAgentExtraction(unittest.TestCase):
    """Test agent and session extraction in trace_operation."""

    def setUp(self):
        """Reset module state."""
        import utils.otel as otel_module
        otel_module._tracer = None
        otel_module._initialized = False
        otel_module.OTEL_AVAILABLE = False
        otel_module.init_tracing()

    def tearDown(self):
        """Clean up."""
        from utils.otel import shutdown_tracing
        shutdown_tracing()

    def test_extract_from_request_object(self):
        """Test extraction from a request object with agent attribute."""
        from utils.otel import _extract_agent_name, _extract_session_id

        class MockRequest:
            agent = "request-agent"
            session_id = "request-session"

        request = MockRequest()

        result = _extract_agent_name((request,), {})
        self.assertEqual(result, "request-agent")

        result = _extract_session_id((request,), {})
        self.assertEqual(result, "request-session")

    def test_extract_requesting_agent(self):
        """Test extraction of requesting_agent attribute."""
        from utils.otel import _extract_agent_name

        class MockRequest:
            requesting_agent = "requesting-agent"

        result = _extract_agent_name((MockRequest(),), {})
        self.assertEqual(result, "requesting-agent")


if __name__ == "__main__":
    unittest.main()
