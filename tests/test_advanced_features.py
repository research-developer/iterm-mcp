"""Tests for advanced features of iTerm2 MCP integration."""

import asyncio
import os
import unittest
import time
import tempfile
import shutil
import re

import iterm2

from iterm_mcp_python.core.terminal import ItermTerminal
from iterm_mcp_python.core.layouts import LayoutManager, LayoutType
from iterm_mcp_python.core.session import ItermSession
from iterm_mcp_python.utils.logging import ItermLogManager, ItermSessionLogger


class TestAdvancedFeatures(unittest.TestCase):
    """Test advanced features of the iTerm2 MCP integration."""

    def setUp(self):
        """Set up a temporary directory for logs."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)

    async def async_setup(self):
        """Set up the test environment."""
        try:
            # Connect to iTerm2
            self.connection = await iterm2.Connection.async_create()

            # Initialize terminal with logging enabled
            self.terminal = ItermTerminal(
                connection=self.connection,
                log_dir=self.temp_dir,
                enable_logging=True
            )
            await self.terminal.initialize()

            # Create a test window
            self.test_session = await self.terminal.create_window()
            if self.test_session:
                await self.test_session.set_name("AdvTestSession")

                # Wait for window to be ready
                await asyncio.sleep(1)
            else:
                self.fail("Failed to create test window")
        except Exception as e:
            self.fail(f"Failed to set up test environment: {str(e)}")

    async def async_teardown(self):
        """Clean up the test environment."""
        # Close the test session if it exists
        if hasattr(self, "test_session"):
            if self.test_session.is_monitoring:
                self.test_session.stop_monitoring()
            await self.terminal.close_session(self.test_session.id)

    def run_async_test(self, coro):
        """Run an async test function."""
        async def test_wrapper():
            try:
                await self.async_setup()
                await coro()
            finally:
                await self.async_teardown()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_wrapper())

    def test_screen_monitoring(self):
        """Test screen monitoring functionality."""
        async def test_impl():
            # Start monitoring the session
            output_received = asyncio.Event()
            captured_output = []
            
            async def output_callback(content):
                captured_output.append(content)
                output_received.set()
            
            # Add the callback and start monitoring
            self.test_session.add_monitor_callback(output_callback)
            await self.test_session.start_monitoring()
            
            # Wait to ensure monitoring is started
            await asyncio.sleep(1)
            
            # Verify monitoring is active
            self.assertTrue(self.test_session.is_monitoring)
            
            # Send a command
            test_string = f"echo 'Test monitoring {time.time()}'"
            await self.test_session.send_text(f"{test_string}\n")
            
            # Wait for output to be received
            try:
                await asyncio.wait_for(output_received.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.fail("Timed out waiting for screen update")
                
            # Stop monitoring
            self.test_session.stop_monitoring()
            await asyncio.sleep(1)
            
            # Verify monitoring stopped
            self.assertFalse(self.test_session.is_monitoring)
            
            # Verify we captured the output
            self.assertTrue(any(test_string in output for output in captured_output))
            
            # Verify snapshot file exists
            self.assertTrue(os.path.exists(self.test_session.logger.snapshot_file))
            
            # Read snapshot file
            with open(self.test_session.logger.snapshot_file, 'r') as f:
                snapshot = f.read()
                
            # Verify snapshot contains our test string
            self.assertIn(test_string, snapshot)

        self.run_async_test(test_impl)

    def test_output_filtering(self):
        """Test output filtering functionality."""
        async def test_impl():
            # Add a filter to only capture lines with 'ERROR'
            self.test_session.logger.add_output_filter(r"ERROR")
            
            # Send various messages
            await self.test_session.send_text("echo 'This is a normal message'\n")
            await self.test_session.send_text("echo 'This message contains an ERROR'\n")
            await self.test_session.send_text("echo 'Another normal message'\n")
            
            # Wait for commands to complete
            await asyncio.sleep(2)
            
            # Read the log file
            with open(self.test_session.logger.log_file, 'r') as f:
                log_content = f.read()
            
            # The normal messages should not be in the log
            self.assertNotIn("OUTPUT: This is a normal message", log_content)
            self.assertNotIn("OUTPUT: Another normal message", log_content)
            
            # The error message should be in the log
            self.assertIn("OUTPUT: This message contains an ERROR", log_content)
            
            # Clear filters and send another message
            self.test_session.logger.clear_output_filters()
            await self.test_session.send_text("echo 'After clearing filters'\n")
            await asyncio.sleep(1)
            
            # Read the log file again
            with open(self.test_session.logger.log_file, 'r') as f:
                updated_log = f.read()
                
            # Now the normal message should be in the log
            self.assertIn("OUTPUT: After clearing filters", updated_log)

        self.run_async_test(test_impl)

    def test_multiple_sessions(self):
        """Test creating and managing multiple sessions."""
        async def test_impl():
            # Create multiple sessions with different commands
            session_configs = [
                {"name": "Session1", "command": "echo 'Hello from Session 1'", "monitor": True},
                {"name": "Session2", "command": "echo 'Hello from Session 2'", "layout": True, "vertical": True}
            ]
            
            session_map = await self.terminal.create_multiple_sessions(session_configs)
            
            # Verify we got sessions back
            self.assertEqual(len(session_map), 2)
            self.assertIn("Session1", session_map)
            self.assertIn("Session2", session_map)
            
            # Wait for commands to execute
            await asyncio.sleep(2)
            
            # Get session objects
            session1 = await self.terminal.get_session_by_id(session_map["Session1"])
            session2 = await self.terminal.get_session_by_id(session_map["Session2"])
            
            # Check that Session1 is being monitored
            self.assertTrue(session1.is_monitoring)
            
            # Verify output from each session
            output1 = await session1.get_screen_contents()
            output2 = await session2.get_screen_contents()
            
            self.assertIn("Hello from Session 1", output1)
            self.assertIn("Hello from Session 2", output2)
            
            # Clean up
            for session_id in session_map.values():
                # Get the session and stop monitoring if active
                session = await self.terminal.get_session_by_id(session_id)
                if session and session.is_monitoring:
                    session.stop_monitoring()
                # Close the session
                await self.terminal.close_session(session_id)

        self.run_async_test(test_impl)


if __name__ == "__main__":
    unittest.main()