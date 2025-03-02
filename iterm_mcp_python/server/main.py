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
        """Demonstrate basic functionality of the iTerm controller."""
        try:
            self.logger.info("Creating a horizontal split layout...")

            # Create a horizontal split layout with named panes
            session_map = await self.layout_manager.create_layout(
                layout_type=LayoutType.HORIZONTAL_SPLIT,
                pane_names=["Left Pane", "Right Pane"]
            )

            left_session_id = session_map["Left Pane"]
            right_session_id = session_map["Right Pane"]

            left_session = await self.terminal.get_session_by_id(left_session_id)
            right_session = await self.terminal.get_session_by_id(right_session_id)

            self.logger.info(f"Created sessions: {left_session.name} and {right_session.name}")

            # Send some commands to the sessions
            await left_session.send_text("echo 'Hello from the left pane!'\n")
            await right_session.send_text("echo 'Hello from the right pane!'\n")

            # Wait for commands to complete
            await asyncio.sleep(1)

            # Read output from each session
            left_output = await left_session.get_screen_contents()
            right_output = await right_session.get_screen_contents()

            self.logger.info(f"Left pane output: {left_output}")
            self.logger.info(f"Right pane output: {right_output}")

            # Demonstrate focus functionality
            self.logger.info("Focusing on left pane...")
            await self.terminal.focus_session(left_session_id)
            await asyncio.sleep(1)

            self.logger.info("Focusing on right pane...")
            await self.terminal.focus_session(right_session_id)
            await asyncio.sleep(1)

            self.logger.info("Demo completed successfully!")
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