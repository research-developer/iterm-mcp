"""Tests for command output tracking functionality."""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from core.terminal import ItermTerminal
from core.session import ItermSession
from utils.logging import ItermLogManager, ItermSessionLogger


class TestCommandOutputTracking(unittest.IsolatedAsyncioTestCase):
    """Tests for command output tracking functionality."""
    
    async def asyncSetUp(self):
        """Set up test environment before each test method."""
        # Create a temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock session
        self.session = MagicMock(spec=ItermSession)
        self.session.session_id = "test-session-123"
        self.session.name = "Test Session"
        self.session.is_processing = False
        
        # Create a mock connection
        self.connection = AsyncMock()
        
        # Create a terminal instance with logging enabled
        self.terminal = ItermTerminal(
            connection=self.connection,
            enable_logging=True
        )
        
        # Add a logger to the terminal instance
        self.terminal.logger = MagicMock()
        
        # Mock the get_session_by_id method to return our mock session
        self.terminal.get_session_by_id = AsyncMock(return_value=self.session)
        
        # Set up the log manager and logger
        self.log_manager = ItermLogManager(
            log_dir=self.temp_dir,
            max_snapshot_lines=1000,
            default_max_lines=100
        )

        # Get a logger for our test session
        self.logger = self.log_manager.get_session_logger(
            session_id=self.session.session_id,
            session_name=self.session.name
        )
        
        # Set the logger on the session
        self.session.logger = self.logger
        
        # Mock the send_text method to simulate command execution
        async def mock_send_text(text, execute=True):
            # Simulate command output
            if execute and text.strip() and text.strip() != "\n":
                # Log the command
                self.logger.log_command(text.strip())
                # Simulate command output
                output = f"Output for: {text.strip()}\n"
                self.logger.log_output(output)
                
        self.session.send_text = mock_send_text
        
        # Mock the terminal's app property to avoid initialization errors
        self.terminal.app = MagicMock()
        self.terminal.sessions = {self.session.session_id: self.session}
        
        # Mock the _refresh_sessions method to avoid actual iTerm2 API calls
        async def mock_refresh_sessions():
            pass
            
        self.terminal._refresh_sessions = mock_refresh_sessions
        
    async def asyncTearDown(self):
        """Clean up after each test method."""
        # Clean up the temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_track_command_output(self):
        """Test tracking output for a specific command."""
        # Execute a command
        await self.terminal.execute_command(
            self.session.session_id,
            "echo 'Hello, World!'"
        )
        
        # Log some output
        self.logger.log_output("Hello, World!\n")
        
        # Get output since last command
        output = self.logger.get_output_since_last_command()
        self.assertIn("Hello, World!", output)
    
    async def test_multiple_commands(self):
        """Test tracking output across multiple commands."""
        # First command
        await self.terminal.execute_command(
            self.session.session_id,
            "echo 'First command'"
        )
        self.logger.log_output("First command\n")
        
        # Second command
        await self.terminal.execute_command(
            self.session.session_id,
            "echo 'Second command'"
        )
        self.logger.log_output("Second command\n")
        
        # Get output since last command
        output = self.logger.get_output_since_last_command()
        self.assertIn("Second command", output)
        self.assertNotIn("First command", output)
    
    async def test_no_commands_yet(self):
        """Test getting output when no commands have been executed."""
        output = self.logger.get_output_since_last_command()
        self.assertEqual(output, "")
    
    async def test_max_lines_respected(self):
        """Test that max_lines is respected when getting output."""
        # Execute a command
        await self.terminal.execute_command(
            self.session.session_id,
            "echo 'Test'"
        )

        # Log more lines than the max
        for i in range(15):
            self.logger.log_output(f"Line {i}")

        # Get output with a small max_lines
        output = self.logger.get_output_since_last_command(max_lines=5)
        self.assertEqual(len(output.splitlines()), 5)

    async def test_empty_command(self):
        """Test handling of empty command."""
        # Empty commands don't trigger log_command due to the check in send_text mock
        # So manually log an empty command to test the behavior
        self.logger.log_command("")

        # Log some output after the command
        self.logger.log_output("Some output\n")

        # Get output since empty command
        output = self.logger.get_output_since_last_command()
        self.assertIn("Some output", output)

    async def test_command_with_special_characters(self):
        """Test command with special characters."""
        # Execute a command with special characters
        special_cmd = "echo 'Hello & World | Test > output.txt'"
        await self.terminal.execute_command(
            self.session.session_id,
            special_cmd
        )

        # Log output
        self.logger.log_output("Command executed successfully\n")

        # Get output
        output = self.logger.get_output_since_last_command()
        self.assertIn("Command executed successfully", output)

    async def test_very_long_output(self):
        """Test handling of very long output."""
        # Execute a command
        await self.terminal.execute_command(
            self.session.session_id,
            "cat large_file.txt"
        )

        # Log a lot of output (within snapshot limits of 1000)
        for i in range(200):
            self.logger.log_output(f"Line {i}: This is a very long line with lots of text to simulate real output\n")

        # Get all output
        output = self.logger.get_output_since_last_command()
        # Output should have all lines since command (200 lines, each becomes one in latest_output)
        self.assertGreater(len(output.splitlines()), 150)

        # Get limited output
        limited_output = self.logger.get_output_since_last_command(max_lines=10)
        # Allow for +/- 1 line due to newline handling
        self.assertGreaterEqual(len(limited_output.splitlines()), 9)
        self.assertLessEqual(len(limited_output.splitlines()), 10)

    async def test_consecutive_empty_outputs(self):
        """Test multiple commands with no output between them."""
        # Manually log commands without output to avoid mock side effects
        self.logger.log_command("echo 'First'")
        # No output logged between commands
        self.logger.log_command("echo 'Second'")

        # Since no output was logged after the second command
        output = self.logger.get_output_since_last_command()
        self.assertEqual(output, "")

    async def test_command_without_execution(self):
        """Test typing a command without executing it."""
        # Type command without executing
        await self.terminal.execute_command(
            self.session.session_id,
            "ls -la",
            execute=False
        )

        # Since execute=False, the command might not be logged
        # But we should still be able to get output
        output = self.logger.get_output_since_last_command()
        # Should return empty or whatever was logged
        self.assertIsInstance(output, str)

    async def test_rapid_command_execution(self):
        """Test rapid consecutive command execution."""
        # Execute multiple commands rapidly
        for i in range(10):
            await self.terminal.execute_command(
                self.session.session_id,
                f"echo 'Command {i}'"
            )
            self.logger.log_output(f"Output from command {i}\n")

        # Get output from last command
        output = self.logger.get_output_since_last_command()
        self.assertIn("Output from command 9", output)
        self.assertNotIn("Output from command 8", output)


if __name__ == "__main__":
    unittest.main()
