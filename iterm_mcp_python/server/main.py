"""Main entry point for the iTerm controller."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

import iterm2

from ..core.layouts import LayoutManager, LayoutType
from ..core.session import ItermSession
from ..core.terminal import ItermTerminal


class ItermController:
    """iTerm2 terminal controller implementation."""

    def __init__(self):
        """Initialize the controller."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(os.path.expanduser("~/.iterm-controller.log")),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("iterm-controller")

        # Set terminal and layout manager to None initially
        # They will be initialized when the controller starts
        self.terminal: Optional[ItermTerminal] = None
        self.layout_manager: Optional[LayoutManager] = None
        self.session_map: Dict[str, str] = {}  # Maps names to session IDs

        # Configure log directory
        self.log_dir = os.path.expanduser("~/.iterm_logs")

    async def start(self):
        """Start the controller."""
        # Initialize connection to iTerm2
        connection = await iterm2.Connection.async_create()

        # Initialize terminal and layout manager
        self.terminal = ItermTerminal(
            connection=connection,
            log_dir=self.log_dir,
            enable_logging=True
        )
        await self.terminal.initialize()

        self.layout_manager = LayoutManager(self.terminal)

        self.logger.info(f"iTerm2 controller initialized. Logs saved to: {self.log_dir}")

        # Example: Create a layout and demonstrate functionality
        await self.demo_functionality()

    async def demo_functionality(self):
        """Demonstrate advanced functionality of the iTerm controller."""
        try:
            self.logger.info("Starting advanced demo...")

            # Create multiple sessions with different configurations
            session_configs = [
                {
                    "name": "Command", 
                    "command": "echo 'Welcome to the iTerm2 MCP Demo'; sleep 1; echo 'This session is monitored in real-time'", 
                    "monitor": True
                },
                {
                    "name": "Output", 
                    "command": "for i in {1..5}; do echo \"Output line $i\"; sleep 1; done", 
                    "layout": True, 
                    "vertical": True
                },
                {
                    "name": "Errors", 
                    "command": "echo 'Normal message'; sleep 1; echo 'ERROR: This is an error message'; sleep 1; echo 'Another normal message'", 
                    "layout": True, 
                    "vertical": False
                }
            ]
            
            self.logger.info("Creating multiple sessions...")
            session_map = await self.terminal.create_multiple_sessions(session_configs)
            
            # Get session objects
            command_session = await self.terminal.get_session_by_id(session_map["Command"])
            output_session = await self.terminal.get_session_by_id(session_map["Output"])
            error_session = await self.terminal.get_session_by_id(session_map["Errors"])
            
            # Show that Command session is being monitored
            self.logger.info(f"Command session monitoring active: {command_session.is_monitoring}")
            
            # Set up a filter on the Errors session to only capture error messages
            if error_session.logger:
                error_session.logger.add_output_filter(r"ERROR")
                self.logger.info("Added error filter to Errors session")
            
            # Register a callback for Command session monitoring
            async def output_handler(content):
                self.logger.info(f"Realtime update from Command session: {content[:50]}...")
                
            command_session.add_monitor_callback(output_handler)
            
            # Wait for initial commands to complete
            await asyncio.sleep(3)
            
            # Add more interactions
            self.logger.info("Sending additional commands...")
            
            # Send commands to sessions
            await command_session.send_text("echo 'This is a dynamic command executed later'\n")
            await output_session.send_text("echo 'Running a second command in the output pane'\n")
            await error_session.send_text("echo 'DEBUG: This message will be filtered out'\n")
            await error_session.send_text("echo 'ERROR: This error message will be captured'\n")
            
            # Wait for commands to complete
            await asyncio.sleep(2)
            
            # Demonstrate focus switching
            for name, session_id in session_map.items():
                self.logger.info(f"Focusing on {name} session...")
                await self.terminal.focus_session(session_id)
                await asyncio.sleep(1)
            
            # Display snapshot information for Command session
            if hasattr(self.terminal, "log_manager"):
                snapshot = self.terminal.log_manager.get_snapshot(command_session.id)
                if snapshot:
                    self.logger.info(f"Command session snapshot sample: {snapshot[:100]}...")
                    
                # List all session logs
                logs = self.terminal.log_manager.list_session_logs()
                self.logger.info(f"Log files available: {list(logs.values())}")
                
                # List all snapshots
                snapshots = self.terminal.log_manager.list_session_snapshots()
                self.logger.info(f"Snapshot files available: {list(snapshots.values())}")
            
            # Stop monitoring on Command session
            if command_session.is_monitoring:
                command_session.stop_monitoring()
                self.logger.info("Stopped monitoring Command session")
            
            self.logger.info("Advanced demo completed successfully!")
        except Exception as e:
            self.logger.error(f"Error in demo: {str(e)}", exc_info=True)


async def async_main():
    """Async entry point for the controller."""
    controller = ItermController()
    await controller.start()


def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("Controller stopped by user")
    except Exception as e:
        print(f"Error running controller: {e}")


if __name__ == "__main__":
    main()