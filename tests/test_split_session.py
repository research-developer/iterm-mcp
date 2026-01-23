"""Tests for split_session functionality."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import iterm2

from core.terminal import ItermTerminal
from core.session import ItermSession
from core.agents import AgentRegistry
from core.models import (
    SplitSessionRequest,
    SplitSessionResponse,
    SessionTarget,
)


class TestSplitSessionDirectional(unittest.TestCase):
    """Test the split_session_directional method in ItermTerminal."""

    async def async_setup(self):
        """Set up the test environment."""
        # Connect to iTerm2
        try:
            self.connection = await iterm2.Connection.async_create()
            
            # Initialize terminal
            self.terminal = ItermTerminal(self.connection)
            await self.terminal.initialize()
            
            # Create a test window/session
            self.test_session = await self.terminal.create_window()
            if self.test_session:
                await self.test_session.set_name("TestSourceSession")
                await asyncio.sleep(1)
            else:
                self.fail("Failed to create test window")
        except Exception as e:
            self.fail(f"Failed to set up test environment: {str(e)}")
    
    async def async_teardown(self):
        """Clean up the test environment."""
        # Close all test sessions
        if hasattr(self, "terminal"):
            # Get all sessions and close them
            for session_id in list(self.terminal.sessions.keys()):
                try:
                    await self.terminal.close_session(session_id)
                except Exception:
                    pass  # Ignore errors during cleanup
    
    def run_async_test(self, coro):
        """Run an async test function."""
        async def test_wrapper():
            try:
                await self.async_setup()
                await coro()
            finally:
                await self.async_teardown()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_wrapper())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    def test_split_below(self):
        """Test splitting a session below (horizontal split, after)."""
        async def test_impl():
            # Split below the test session
            new_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="below",
                name="BelowPane"
            )
            
            # Verify the new session was created
            self.assertIsNotNone(new_session)
            self.assertEqual(new_session.name, "BelowPane")
            self.assertNotEqual(new_session.id, self.test_session.id)
            
            # Verify we can send commands to both sessions
            await self.test_session.send_text("echo 'source'\n")
            await new_session.send_text("echo 'below'\n")
            await asyncio.sleep(1)
            
            # Verify output
            source_output = await self.test_session.get_screen_contents()
            new_output = await new_session.get_screen_contents()
            
            self.assertIn("source", source_output)
            self.assertIn("below", new_output)
        
        self.run_async_test(test_impl)
    
    def test_split_above(self):
        """Test splitting a session above (horizontal split, before)."""
        async def test_impl():
            # Split above the test session
            new_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="above",
                name="AbovePane"
            )
            
            # Verify the new session was created
            self.assertIsNotNone(new_session)
            self.assertEqual(new_session.name, "AbovePane")
            self.assertNotEqual(new_session.id, self.test_session.id)
        
        self.run_async_test(test_impl)
    
    def test_split_right(self):
        """Test splitting a session to the right (vertical split, after)."""
        async def test_impl():
            # Split right of the test session
            new_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="right",
                name="RightPane"
            )
            
            # Verify the new session was created
            self.assertIsNotNone(new_session)
            self.assertEqual(new_session.name, "RightPane")
            self.assertNotEqual(new_session.id, self.test_session.id)
        
        self.run_async_test(test_impl)
    
    def test_split_left(self):
        """Test splitting a session to the left (vertical split, before)."""
        async def test_impl():
            # Split left of the test session
            new_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="left",
                name="LeftPane"
            )
            
            # Verify the new session was created
            self.assertIsNotNone(new_session)
            self.assertEqual(new_session.name, "LeftPane")
            self.assertNotEqual(new_session.id, self.test_session.id)
        
        self.run_async_test(test_impl)
    
    def test_invalid_direction(self):
        """Test that invalid direction raises ValueError."""
        async def test_impl():
            with self.assertRaises(ValueError) as context:
                await self.terminal.split_session_directional(
                    session_id=self.test_session.id,
                    direction="invalid",
                    name="InvalidPane"
                )
            
            self.assertIn("Invalid direction", str(context.exception))
        
        self.run_async_test(test_impl)
    
    def test_invalid_session_id(self):
        """Test that invalid session ID raises ValueError."""
        async def test_impl():
            with self.assertRaises(ValueError) as context:
                await self.terminal.split_session_directional(
                    session_id="nonexistent-session-id",
                    direction="below",
                    name="InvalidPane"
                )
            
            self.assertIn("not found", str(context.exception))
        
        self.run_async_test(test_impl)
    
    def test_multiple_splits(self):
        """Test creating multiple splits from the same session."""
        async def test_impl():
            # Create multiple splits
            below_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="below",
                name="BelowPane"
            )
            
            right_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="right",
                name="RightPane"
            )
            
            # Verify all sessions exist and are unique
            self.assertIsNotNone(below_session)
            self.assertIsNotNone(right_session)
            
            all_ids = {
                self.test_session.id,
                below_session.id,
                right_session.id
            }
            self.assertEqual(len(all_ids), 3, "All sessions should have unique IDs")
        
        self.run_async_test(test_impl)


class TestSplitSessionModels(unittest.TestCase):
    """Test the SplitSessionRequest and SplitSessionResponse models."""
    
    def test_split_session_request_valid(self):
        """Test creating a valid SplitSessionRequest."""
        request = SplitSessionRequest(
            target=SessionTarget(session_id="test-id"),
            direction="below",
            name="NewPane",
            agent="test-agent",
            team="test-team",
        )
        
        self.assertEqual(request.direction, "below")
        self.assertEqual(request.name, "NewPane")
        self.assertEqual(request.agent, "test-agent")
        self.assertEqual(request.team, "test-team")
    
    def test_split_session_request_minimal(self):
        """Test creating a minimal SplitSessionRequest."""
        request = SplitSessionRequest(
            target=SessionTarget(name="source-session"),
            direction="right",
        )
        
        self.assertEqual(request.direction, "right")
        self.assertIsNone(request.name)
        self.assertIsNone(request.agent)
    
    def test_split_session_response(self):
        """Test creating a SplitSessionResponse."""
        response = SplitSessionResponse(
            session_id="new-id",
            name="NewPane",
            agent="test-agent",
            persistent_id="persistent-id",
            source_session_id="source-id"
        )
        
        self.assertEqual(response.session_id, "new-id")
        self.assertEqual(response.name, "NewPane")
        self.assertEqual(response.agent, "test-agent")
        self.assertEqual(response.source_session_id, "source-id")


class TestSplitSessionIntegration(unittest.TestCase):
    """Integration tests for split_session with agent registry."""
    
    async def async_setup(self):
        """Set up the test environment."""
        # Connect to iTerm2
        try:
            self.connection = await iterm2.Connection.async_create()
            
            # Initialize terminal and agent registry
            self.terminal = ItermTerminal(self.connection)
            await self.terminal.initialize()
            
            self.agent_registry = AgentRegistry()
            
            # Create a test window/session
            self.test_session = await self.terminal.create_window()
            if self.test_session:
                await self.test_session.set_name("IntegrationTestSession")
                await asyncio.sleep(1)
            else:
                self.fail("Failed to create test window")
        except Exception as e:
            self.fail(f"Failed to set up test environment: {str(e)}")
    
    async def async_teardown(self):
        """Clean up the test environment."""
        if hasattr(self, "terminal"):
            for session_id in list(self.terminal.sessions.keys()):
                try:
                    await self.terminal.close_session(session_id)
                except Exception:
                    pass
    
    def run_async_test(self, coro):
        """Run an async test function."""
        async def test_wrapper():
            try:
                await self.async_setup()
                await coro()
            finally:
                await self.async_teardown()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_wrapper())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    def test_split_with_agent_registration(self):
        """Test splitting a session and registering an agent."""
        async def test_impl():
            # Split and create agent
            new_session = await self.terminal.split_session_directional(
                session_id=self.test_session.id,
                direction="below",
                name="AgentPane"
            )
            
            # Register agent manually (simulating what the MCP tool does)
            self.agent_registry.register_agent(
                name="test-agent",
                session_id=new_session.id,
                teams=["test-team"]
            )
            
            # Verify agent was registered
            agent = self.agent_registry.get_agent("test-agent")
            self.assertIsNotNone(agent)
            self.assertEqual(agent.session_id, new_session.id)
            self.assertIn("test-team", agent.teams)
        
        self.run_async_test(test_impl)
    
    def test_split_by_agent_name(self):
        """Test targeting a session by agent name for splitting."""
        async def test_impl():
            # Register an agent for the test session
            self.agent_registry.register_agent(
                name="source-agent",
                session_id=self.test_session.id
            )
            
            # Get the session by agent name
            agent = self.agent_registry.get_agent("source-agent")
            self.assertIsNotNone(agent)
            
            session = await self.terminal.get_session_by_id(agent.session_id)
            self.assertIsNotNone(session)
            
            # Split using the resolved session
            new_session = await self.terminal.split_session_directional(
                session_id=session.id,
                direction="right",
                name="SplitFromAgent"
            )
            
            self.assertIsNotNone(new_session)
            self.assertEqual(new_session.name, "SplitFromAgent")
        
        self.run_async_test(test_impl)


if __name__ == "__main__":
    unittest.main()
