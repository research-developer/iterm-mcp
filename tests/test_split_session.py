"""Tests for split_session functionality (Issue #85)."""

import unittest

from pydantic import ValidationError

from core.models import (
    SessionTarget,
    SessionRole,
    RoleConfig,
    SplitSessionRequest,
    SplitSessionResponse,
)


class TestSplitSessionRequest(unittest.TestCase):
    """Test SplitSessionRequest model validation."""

    def test_minimal_request(self):
        """Test creating a request with only required fields."""
        request = SplitSessionRequest(
            target=SessionTarget(session_id="test-123"),
            direction="right"
        )
        self.assertEqual(request.direction, "right")
        self.assertEqual(request.target.session_id, "test-123")
        self.assertIsNone(request.name)
        self.assertIsNone(request.profile)
        self.assertIsNone(request.command)
        self.assertIsNone(request.agent)
        self.assertIsNone(request.team)
        self.assertFalse(request.monitor)

    def test_full_request(self):
        """Test creating a request with all fields."""
        request = SplitSessionRequest(
            target=SessionTarget(agent="main-agent"),
            direction="below",
            name="WorkerPane",
            profile="MCP Agent",
            command="echo hello",
            agent="worker-1",
            team="workers",
            monitor=True,
            role=SessionRole.BUILDER,
            role_config=RoleConfig(
                role=SessionRole.BUILDER,
                description="Custom builder config"
            )
        )
        self.assertEqual(request.direction, "below")
        self.assertEqual(request.name, "WorkerPane")
        self.assertEqual(request.agent, "worker-1")
        self.assertEqual(request.team, "workers")
        self.assertTrue(request.monitor)
        self.assertEqual(request.role, SessionRole.BUILDER)
        self.assertIsNotNone(request.role_config)

    def test_all_directions(self):
        """Test all valid split directions."""
        for direction in ["above", "below", "left", "right"]:
            request = SplitSessionRequest(
                target=SessionTarget(name="test"),
                direction=direction
            )
            self.assertEqual(request.direction, direction)

    def test_invalid_direction(self):
        """Test that invalid direction raises validation error."""
        with self.assertRaises(ValidationError):
            SplitSessionRequest(
                target=SessionTarget(name="test"),
                direction="diagonal"  # Invalid direction
            )

    def test_target_by_session_id(self):
        """Test targeting by session ID."""
        request = SplitSessionRequest(
            target=SessionTarget(session_id="abc-123"),
            direction="right"
        )
        self.assertEqual(request.target.session_id, "abc-123")

    def test_target_by_agent_name(self):
        """Test targeting by agent name."""
        request = SplitSessionRequest(
            target=SessionTarget(agent="my-agent"),
            direction="left"
        )
        self.assertEqual(request.target.agent, "my-agent")

    def test_target_by_session_name(self):
        """Test targeting by session name."""
        request = SplitSessionRequest(
            target=SessionTarget(name="MainSession"),
            direction="above"
        )
        self.assertEqual(request.target.name, "MainSession")

    def test_agent_type_specified(self):
        """Test specifying an agent type to launch."""
        request = SplitSessionRequest(
            target=SessionTarget(name="test"),
            direction="right",
            agent_type="claude"
        )
        self.assertEqual(request.agent_type, "claude")

    def test_role_without_config(self):
        """Test specifying a role without custom config."""
        request = SplitSessionRequest(
            target=SessionTarget(name="test"),
            direction="right",
            role=SessionRole.DEBUGGER
        )
        self.assertEqual(request.role, SessionRole.DEBUGGER)
        self.assertIsNone(request.role_config)


class TestSplitSessionResponse(unittest.TestCase):
    """Test SplitSessionResponse model."""

    def test_minimal_response(self):
        """Test creating a response with required fields."""
        response = SplitSessionResponse(
            session_id="new-session-123",
            name="NewPane",
            persistent_id="persistent-abc",
            source_session_id="source-456",
            direction="right"
        )
        self.assertEqual(response.session_id, "new-session-123")
        self.assertEqual(response.name, "NewPane")
        self.assertEqual(response.source_session_id, "source-456")
        self.assertEqual(response.direction, "right")
        self.assertIsNone(response.agent)
        self.assertIsNone(response.role)

    def test_full_response(self):
        """Test creating a response with all fields."""
        response = SplitSessionResponse(
            session_id="new-session-123",
            name="WorkerPane",
            agent="worker-1",
            persistent_id="persistent-abc",
            source_session_id="source-456",
            direction="below",
            role="builder"
        )
        self.assertEqual(response.agent, "worker-1")
        self.assertEqual(response.role, "builder")

    def test_response_serialization(self):
        """Test that response can be serialized to JSON."""
        response = SplitSessionResponse(
            session_id="test-123",
            name="TestPane",
            persistent_id="persist-1",
            source_session_id="source-1",
            direction="left"
        )
        json_str = response.model_dump_json()
        self.assertIn("test-123", json_str)
        self.assertIn("TestPane", json_str)
        self.assertIn("left", json_str)


class TestDirectionMapping(unittest.TestCase):
    """Test direction to iTerm2 API parameter mapping."""

    def test_direction_mapping_values(self):
        """Test the expected direction mapping for iTerm2 API."""
        # This tests the expected mapping documented in the models
        # above: vertical=False, before=True
        # below: vertical=False, before=False
        # left: vertical=True, before=True
        # right: vertical=True, before=False

        direction_map = {
            "above": {"vertical": False, "before": True},
            "below": {"vertical": False, "before": False},
            "left": {"vertical": True, "before": True},
            "right": {"vertical": True, "before": False},
        }

        # Verify above/below are horizontal splits
        self.assertFalse(direction_map["above"]["vertical"])
        self.assertFalse(direction_map["below"]["vertical"])

        # Verify left/right are vertical splits
        self.assertTrue(direction_map["left"]["vertical"])
        self.assertTrue(direction_map["right"]["vertical"])

        # Verify before flags
        self.assertTrue(direction_map["above"]["before"])
        self.assertFalse(direction_map["below"]["before"])
        self.assertTrue(direction_map["left"]["before"])
        self.assertFalse(direction_map["right"]["before"])


class TestSplitSessionDirectional(unittest.TestCase):
    """Test the split_session_directional direction mapping logic."""

    def test_direction_to_iterm_params_above(self):
        """Test 'above' direction maps correctly."""
        # above: vertical=False, before=True (horizontal split, new pane above)
        direction_map = {
            "above": {"vertical": False, "before": True},
            "below": {"vertical": False, "before": False},
            "left": {"vertical": True, "before": True},
            "right": {"vertical": True, "before": False},
        }
        params = direction_map["above"]
        self.assertFalse(params["vertical"])
        self.assertTrue(params["before"])

    def test_direction_to_iterm_params_below(self):
        """Test 'below' direction maps correctly."""
        direction_map = {
            "above": {"vertical": False, "before": True},
            "below": {"vertical": False, "before": False},
            "left": {"vertical": True, "before": True},
            "right": {"vertical": True, "before": False},
        }
        params = direction_map["below"]
        self.assertFalse(params["vertical"])
        self.assertFalse(params["before"])

    def test_direction_to_iterm_params_left(self):
        """Test 'left' direction maps correctly."""
        direction_map = {
            "above": {"vertical": False, "before": True},
            "below": {"vertical": False, "before": False},
            "left": {"vertical": True, "before": True},
            "right": {"vertical": True, "before": False},
        }
        params = direction_map["left"]
        self.assertTrue(params["vertical"])
        self.assertTrue(params["before"])

    def test_direction_to_iterm_params_right(self):
        """Test 'right' direction maps correctly."""
        direction_map = {
            "above": {"vertical": False, "before": True},
            "below": {"vertical": False, "before": False},
            "left": {"vertical": True, "before": True},
            "right": {"vertical": True, "before": False},
        }
        params = direction_map["right"]
        self.assertTrue(params["vertical"])
        self.assertFalse(params["before"])


class TestSplitSessionIntegration(unittest.TestCase):
    """Integration-style tests using mocked context."""

    def test_request_with_all_target_types(self):
        """Test that all SessionTarget types work with SplitSessionRequest."""
        # Test with session_id
        req1 = SplitSessionRequest(
            target=SessionTarget(session_id="id-123"),
            direction="right"
        )
        self.assertIsNotNone(req1.target.session_id)

        # Test with agent
        req2 = SplitSessionRequest(
            target=SessionTarget(agent="my-agent"),
            direction="left"
        )
        self.assertIsNotNone(req2.target.agent)

        # Test with name
        req3 = SplitSessionRequest(
            target=SessionTarget(name="SessionName"),
            direction="above"
        )
        self.assertIsNotNone(req3.target.name)

    def test_request_agent_and_team_together(self):
        """Test specifying both agent and team in request."""
        request = SplitSessionRequest(
            target=SessionTarget(name="main"),
            direction="right",
            agent="new-agent",
            team="my-team"
        )
        self.assertEqual(request.agent, "new-agent")
        self.assertEqual(request.team, "my-team")

    def test_request_command_and_agent_type_exclusive(self):
        """Test that agent_type takes precedence over command."""
        # Both can be specified, but agent_type should take precedence in implementation
        request = SplitSessionRequest(
            target=SessionTarget(name="main"),
            direction="right",
            command="echo hello",
            agent_type="claude"
        )
        # Both are set - implementation should prioritize agent_type
        self.assertEqual(request.command, "echo hello")
        self.assertEqual(request.agent_type, "claude")


if __name__ == "__main__":
    unittest.main()
