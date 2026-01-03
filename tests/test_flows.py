"""Comprehensive tests for the event-driven flow control system."""

import asyncio
import pytest
from typing import Any

from core.flows import (
    Event,
    EventResult,
    EventPriority,
    EventBus,
    Flow,
    FlowManager,
    ListenerInfo,
    ListenerRegistry,
    start,
    listen,
    router,
    on_output,
    trigger,
    trigger_and_wait,
    get_event_bus,
    get_flow_manager,
    list_workflow_events,
    get_event_history,
    BuildResult,
    DeployResult,
    BuildDeployFlow,
)


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_creation(self):
        """Test creating an event with required fields."""
        event = Event(name="test_event", payload={"key": "value"})
        assert event.name == "test_event"
        assert event.payload == {"key": "value"}
        assert event.source is None
        assert event.priority == EventPriority.NORMAL
        assert event.id is not None  # Auto-generated

    def test_event_with_priority(self):
        """Test creating an event with custom priority."""
        event = Event(
            name="urgent_event",
            payload={},
            priority=EventPriority.HIGH
        )
        assert event.priority == EventPriority.HIGH

    def test_event_with_source(self):
        """Test creating an event with source."""
        event = Event(
            name="sourced_event",
            payload={},
            source="session:main"
        )
        assert event.source == "session:main"


class TestEventResult:
    """Tests for the EventResult dataclass."""

    def test_success_result(self):
        """Test successful event result."""
        event = Event(name="test", payload={})
        result = EventResult(event=event, success=True)
        assert result.success is True
        assert result.event.name == "test"
        assert result.error is None

    def test_failure_result(self):
        """Test failed event result."""
        event = Event(name="test", payload={})
        result = EventResult(
            event=event,
            success=False,
            error="Something went wrong"
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestListenerRegistry:
    """Tests for the ListenerRegistry class."""

    @pytest.mark.asyncio
    async def test_register_listener(self):
        """Test registering a listener."""
        registry = ListenerRegistry()

        async def handler(payload):
            pass

        listener_info = ListenerInfo(
            event_name="test_event",
            handler=handler,
            priority=EventPriority.NORMAL
        )
        await registry.register(listener_info)

        listeners = await registry.get_listeners("test_event")
        assert len(listeners) == 1
        assert listeners[0].handler == handler

    @pytest.mark.asyncio
    async def test_register_multiple_listeners(self):
        """Test registering multiple listeners for same event."""
        registry = ListenerRegistry()

        async def handler1(payload):
            pass

        async def handler2(payload):
            pass

        listener1 = ListenerInfo(
            event_name="test_event",
            handler=handler1,
            priority=EventPriority.NORMAL
        )
        listener2 = ListenerInfo(
            event_name="test_event",
            handler=handler2,
            priority=EventPriority.HIGH
        )

        await registry.register(listener1)
        await registry.register(listener2)

        listeners = await registry.get_listeners("test_event")
        assert len(listeners) == 2
        # Higher priority should come first
        assert listeners[0].priority == EventPriority.HIGH

    @pytest.mark.asyncio
    async def test_unregister_listener(self):
        """Test unregistering a listener."""
        registry = ListenerRegistry()

        async def handler(payload):
            pass

        listener = ListenerInfo(event_name="test_event", handler=handler)
        await registry.register(listener)
        assert len(await registry.get_listeners("test_event")) == 1

        await registry.unregister("test_event", handler)
        assert len(await registry.get_listeners("test_event")) == 0

    @pytest.mark.asyncio
    async def test_get_all_event_names(self):
        """Test getting all registered event names."""
        registry = ListenerRegistry()

        async def handler(payload):
            pass

        await registry.register(ListenerInfo(event_name="event_a", handler=handler))
        await registry.register(ListenerInfo(event_name="event_b", handler=handler))
        await registry.register(ListenerInfo(event_name="event_c", handler=handler))

        events = await registry.get_all_event_names()
        assert "event_a" in events
        assert "event_b" in events
        assert "event_c" in events


class TestEventBus:
    """Tests for the EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh EventBus for each test."""
        # Create a new registry to avoid global state interference
        registry = ListenerRegistry()
        bus = EventBus(registry=registry)
        return bus

    @pytest.mark.asyncio
    async def test_start_and_stop(self, event_bus):
        """Test starting and stopping the event bus."""
        await event_bus.start()
        assert event_bus._running is True

        await event_bus.stop()
        assert event_bus._running is False

    @pytest.mark.asyncio
    async def test_trigger_event(self, event_bus):
        """Test triggering an event."""
        await event_bus.start()

        received_payloads = []

        async def handler(payload):
            received_payloads.append(payload)

        listener = ListenerInfo(event_name="test_event", handler=handler)
        await event_bus._registry.register(listener)

        result = await event_bus.trigger(
            event_name="test_event",
            payload={"message": "hello"}
        )

        # Give time for event processing
        await asyncio.sleep(0.1)

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_trigger_immediate(self, event_bus):
        """Test trigger with immediate=True for synchronous processing."""
        await event_bus.start()

        received = []

        async def handler(payload):
            received.append(payload["value"])
            return payload["value"] * 2

        listener = ListenerInfo(event_name="compute", handler=handler)
        await event_bus._registry.register(listener)

        result = await event_bus.trigger(
            event_name="compute",
            payload={"value": 5},
            immediate=True
        )

        assert len(received) == 1
        assert received[0] == 5
        assert result.success is True

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_pattern_subscription(self, event_bus):
        """Test subscribing to terminal output patterns."""
        await event_bus.start()

        matched_texts = []

        async def pattern_handler(text: str, match: Any) -> None:
            matched_texts.append(match)

        # Subscribe to pattern
        await event_bus.subscribe_to_pattern(r"error:\s*(.+)", pattern_handler)

        # Process terminal output
        await event_bus.process_terminal_output("session1", "error: connection failed")
        await event_bus.process_terminal_output("session1", "success: all good")
        await event_bus.process_terminal_output("session1", "error: timeout occurred")

        assert len(matched_texts) == 2

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_history(self, event_bus):
        """Test event history tracking."""
        await event_bus.start()

        await event_bus.trigger("event_1", {"data": 1}, immediate=True)
        await event_bus.trigger("event_2", {"data": 2}, immediate=True)
        await event_bus.trigger("event_1", {"data": 3}, immediate=True)

        history = await event_bus.get_history(limit=10)
        assert len(history) == 3

        # Filter by event name
        event_1_history = await event_bus.get_history(event_name="event_1", limit=10)
        assert len(event_1_history) == 2

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering(self, event_bus):
        """Test that higher priority listeners are called first."""
        await event_bus.start()

        call_order = []

        async def low_handler(payload):
            call_order.append("low")

        async def high_handler(payload):
            call_order.append("high")

        async def critical_handler(payload):
            call_order.append("critical")

        await event_bus._registry.register(
            ListenerInfo(event_name="test", handler=low_handler, priority=EventPriority.LOW)
        )
        await event_bus._registry.register(
            ListenerInfo(event_name="test", handler=high_handler, priority=EventPriority.HIGH)
        )
        await event_bus._registry.register(
            ListenerInfo(event_name="test", handler=critical_handler, priority=EventPriority.CRITICAL)
        )

        await event_bus.trigger("test", {}, immediate=True)

        assert call_order == ["critical", "high", "low"]

        await event_bus.stop()


class TestDecorators:
    """Tests for the flow decorators."""

    def test_start_decorator(self):
        """Test the @start decorator."""
        class TestFlow(Flow):
            @start("init_event")
            async def on_init(self, payload):
                return "initialized"

        flow = TestFlow()
        # Check that the method has the decorator metadata
        assert hasattr(flow.on_init, '_is_start')
        assert flow.on_init._is_start is True
        assert flow.on_init._start_event == 'init_event'

    def test_listen_decorator(self):
        """Test the @listen decorator."""
        class TestFlow(Flow):
            @listen("data_ready")
            async def process_data(self, payload):
                return payload["data"] * 2

        flow = TestFlow()
        assert hasattr(flow.process_data, '_is_listener')
        assert flow.process_data._is_listener is True
        assert flow.process_data._listen_event == 'data_ready'

    def test_router_decorator(self):
        """Test the @router decorator."""
        class TestFlow(Flow):
            @router("route_request")
            async def decide_route(self, payload):
                if payload.get("urgent"):
                    return "fast_path"
                return "slow_path"

        flow = TestFlow()
        assert hasattr(flow.decide_route, '_is_router')
        assert flow.decide_route._is_router is True
        assert flow.decide_route._router_event == 'route_request'

    def test_on_output_decorator(self):
        """Test the @on_output decorator."""
        class TestFlow(Flow):
            @on_output(r"PASS|FAIL", event_name="test_result")
            async def handle_test_result(self, text, match):
                return match.group(0)

        flow = TestFlow()
        assert hasattr(flow.handle_test_result, '_is_output_handler')
        assert flow.handle_test_result._is_output_handler is True
        assert flow.handle_test_result._output_pattern == r"PASS|FAIL"


class TestFlow:
    """Tests for the Flow base class."""

    @pytest.mark.asyncio
    async def test_flow_registration(self):
        """Test registering a flow with the event bus."""
        registry = ListenerRegistry()
        event_bus = EventBus(registry=registry)
        await event_bus.start()

        class SimpleFlow(Flow):
            def __init__(self):
                super().__init__(event_bus=event_bus)
                self.started = False

            @start("begin")
            async def on_begin(self, payload):
                self.started = True

        flow = SimpleFlow()
        await flow.register()

        await event_bus.trigger("begin", {}, immediate=True)

        assert flow.started is True

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_flow_router_functionality(self):
        """Test that router properly routes events."""
        registry = ListenerRegistry()
        event_bus = EventBus(registry=registry)
        await event_bus.start()

        class RouterFlow(Flow):
            def __init__(self):
                super().__init__(event_bus=event_bus)
                self.route_taken = None

            @router("decide")
            async def route_decision(self, payload):
                if payload.get("value") > 10:
                    return "high_path"
                return "low_path"

            @listen("high_path")
            async def handle_high(self, payload):
                self.route_taken = "high"

            @listen("low_path")
            async def handle_low(self, payload):
                self.route_taken = "low"

        flow = RouterFlow()
        await flow.register()

        # Test high path
        await event_bus.trigger("decide", {"value": 15}, immediate=True)
        assert flow.route_taken == "high"

        # Test low path
        await event_bus.trigger("decide", {"value": 5}, immediate=True)
        assert flow.route_taken == "low"

        await event_bus.stop()


class TestFlowManager:
    """Tests for the FlowManager class."""

    @pytest.mark.asyncio
    async def test_register_flow(self):
        """Test registering flows with FlowManager."""
        registry = ListenerRegistry()
        event_bus = EventBus(registry=registry)
        manager = FlowManager(event_bus=event_bus)
        await manager.start()

        class TestFlow(Flow):
            @start("test")
            async def on_test(self, payload):
                pass

        flow = TestFlow()
        await manager.register_flow(flow)

        flows = manager.list_flows()
        assert "TestFlow" in flows

        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_flow(self):
        """Test retrieving a registered flow."""
        registry = ListenerRegistry()
        event_bus = EventBus(registry=registry)
        manager = FlowManager(event_bus=event_bus)
        await manager.start()

        class MyFlow(Flow):
            pass

        flow = MyFlow()
        await manager.register_flow(flow)

        retrieved = manager.get_flow("MyFlow")
        assert retrieved is flow

        await manager.stop()

    @pytest.mark.asyncio
    async def test_unregister_flow(self):
        """Test unregistering a flow."""
        registry = ListenerRegistry()
        event_bus = EventBus(registry=registry)
        manager = FlowManager(event_bus=event_bus)
        await manager.start()

        class TempFlow(Flow):
            pass

        flow = TempFlow()
        await manager.register_flow(flow)

        assert "TempFlow" in manager.list_flows()

        await manager.unregister_flow("TempFlow")

        assert "TempFlow" not in manager.list_flows()

        await manager.stop()


class TestBuildDeployFlow:
    """Tests for the example BuildDeployFlow."""

    def test_build_result_dataclass(self):
        """Test BuildResult dataclass."""
        result = BuildResult(
            success=True,
            project="my-app",
            version="1.0.0",
            artifacts=["app.jar", "config.yaml"]
        )
        assert result.success is True
        assert result.project == "my-app"
        assert len(result.artifacts) == 2
        assert result.environment == "staging"  # default

    def test_deploy_result_dataclass(self):
        """Test DeployResult dataclass."""
        result = DeployResult(
            success=True,
            environment="production",
            url="https://app.example.com"
        )
        assert result.success is True
        assert result.environment == "production"
        assert result.url == "https://app.example.com"

    def test_build_deploy_flow_decorators(self):
        """Test that BuildDeployFlow has proper decorators."""
        flow = BuildDeployFlow()

        # Check start decorator
        assert hasattr(flow.start_build, '_is_start')
        assert flow.start_build._is_start is True
        assert flow.start_build._start_event == 'build_requested'

        # Check listen decorator
        assert hasattr(flow.on_build_complete, '_is_listener')
        assert flow.on_build_complete._is_listener is True

        # Check router decorator
        assert hasattr(flow.route_deploy, '_is_router')
        assert flow.route_deploy._is_router is True

        # Check on_output decorators
        assert hasattr(flow.on_error_output, '_is_output_handler')
        assert flow.on_error_output._is_output_handler is True

    @pytest.mark.asyncio
    async def test_build_deploy_flow_routing(self):
        """Test the routing logic in BuildDeployFlow."""
        registry = ListenerRegistry()
        event_bus = EventBus(registry=registry)
        await event_bus.start()

        flow = BuildDeployFlow(event_bus=event_bus)
        await flow.register()

        # Track which events are triggered
        triggered = []

        async def track_staging(payload):
            triggered.append("staging")

        async def track_production(payload):
            triggered.append("production")

        await event_bus._registry.register(
            ListenerInfo(event_name="staging_deploy", handler=track_staging)
        )
        await event_bus._registry.register(
            ListenerInfo(event_name="production_deploy", handler=track_production)
        )

        # Request staging deploy
        await event_bus.trigger("deploy_requested", {"environment": "staging"}, immediate=True)
        assert "staging" in triggered

        # Request production deploy
        await event_bus.trigger("deploy_requested", {"environment": "production"}, immediate=True)
        assert "production" in triggered

        await event_bus.stop()


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_get_event_bus_singleton(self):
        """Test that get_event_bus returns the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_get_flow_manager_singleton(self):
        """Test that get_flow_manager returns the same instance."""
        manager1 = get_flow_manager()
        manager2 = get_flow_manager()
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_list_workflow_events(self):
        """Test listing workflow events."""
        # Use isolated event bus
        registry = ListenerRegistry()
        bus = EventBus(registry=registry)
        await bus.start()

        async def handler(payload):
            pass

        await bus._registry.register(
            ListenerInfo(event_name="test_event_alpha", handler=handler)
        )
        await bus._registry.register(
            ListenerInfo(event_name="test_event_beta", handler=handler)
        )

        events = await bus.get_registered_events()

        assert "test_event_alpha" in events
        assert "test_event_beta" in events

        await bus.stop()

    @pytest.mark.asyncio
    async def test_trigger_function(self):
        """Test the trigger() convenience function."""
        bus = get_event_bus()
        await bus.start()

        received = []

        async def handler(payload):
            received.append(payload)

        await bus._registry.register(
            ListenerInfo(event_name="convenience_test", handler=handler)
        )

        result = await trigger("convenience_test", {"data": "test"}, immediate=True)

        assert result.success is True

        await bus.stop()

    @pytest.mark.asyncio
    async def test_trigger_and_wait_function(self):
        """Test the trigger_and_wait() convenience function."""
        bus = get_event_bus()
        await bus.start()

        async def double_handler(payload):
            return payload["value"] * 2

        await bus._registry.register(
            ListenerInfo(event_name="double_it_test", handler=double_handler)
        )

        result = await trigger_and_wait("double_it_test", {"value": 7})

        assert result.success is True

        await bus.stop()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_trigger_without_listeners(self):
        """Test triggering an event with no listeners."""
        registry = ListenerRegistry()
        bus = EventBus(registry=registry)
        await bus.start()

        result = await bus.trigger("no_listeners_here", {}, immediate=True)

        # Should succeed with no handlers
        assert result.success is True

        await bus.stop()

    @pytest.mark.asyncio
    async def test_handler_exception(self):
        """Test that handler exceptions are caught."""
        registry = ListenerRegistry()
        bus = EventBus(registry=registry)
        await bus.start()

        async def bad_handler(payload):
            raise ValueError("Handler error")

        await bus._registry.register(
            ListenerInfo(event_name="error_test", handler=bad_handler)
        )

        # Should not raise, but result should indicate failure
        result = await bus.trigger("error_test", {}, immediate=True)

        assert result.success is False
        assert "Handler error" in result.error

        await bus.stop()

    @pytest.mark.asyncio
    async def test_empty_payload(self):
        """Test triggering with empty payload."""
        registry = ListenerRegistry()
        bus = EventBus(registry=registry)
        await bus.start()

        received = []

        async def handler(payload):
            received.append(payload)

        await bus._registry.register(
            ListenerInfo(event_name="empty_test", handler=handler)
        )

        await bus.trigger("empty_test", {}, immediate=True)

        assert len(received) == 1
        assert received[0] == {}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_rapid_events(self):
        """Test handling many events in rapid succession."""
        registry = ListenerRegistry()
        bus = EventBus(registry=registry)
        await bus.start()

        count = 0

        async def counter(payload):
            nonlocal count
            count += 1

        await bus._registry.register(
            ListenerInfo(event_name="rapid", handler=counter)
        )

        # Fire 100 events rapidly (using immediate for reliability)
        for i in range(100):
            await bus.trigger("rapid", {"i": i}, immediate=True)

        assert count == 100

        await bus.stop()


# Run with: pytest tests/test_flows.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
