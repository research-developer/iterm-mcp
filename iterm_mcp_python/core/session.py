"""Session management for iTerm2 interaction."""

import asyncio
import os
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union, Callable

import iterm2

from ..utils.logging import ItermSessionLogger

class ItermSession:
    """Manages an iTerm2 session (terminal pane)."""
    
    def __init__(
        self,
        session: iterm2.Session,
        name: Optional[str] = None,
        logger: Optional[ItermSessionLogger] = None,
        persistent_id: Optional[str] = None,
        max_lines: int = 50
    ):
        """Initialize a session wrapper.
        
        Args:
            session: The iTerm2 session object
            name: Optional name for the session
            logger: Optional logger for the session
            persistent_id: Optional persistent ID for reconnection
            max_lines: Maximum number of lines to retrieve by default
        """
        self.session = session
        self._name = name or session.name
        self.logger = logger
        
        # Generate or use persistent ID
        self._persistent_id = persistent_id or str(uuid.uuid4())
        
        # Default number of lines to retrieve
        self._max_lines = max_lines
        
        # For screen monitoring
        self._monitoring = False
        self._monitor_task = None
        self._monitor_callbacks = []
        self._last_screen_update = time.time()
    
    @property
    def id(self) -> str:
        """Get the unique identifier for this session."""
        return self.session.session_id
        
    @property
    def persistent_id(self) -> str:
        """Get the persistent identifier for this session."""
        return self._persistent_id
    
    @property
    def name(self) -> str:
        """Get the name of the session."""
        return self._name
        
    @property
    def max_lines(self) -> int:
        """Get the maximum number of lines to retrieve."""
        return self._max_lines

    def set_max_lines(self, max_lines: int) -> None:
        """Set the maximum number of lines to retrieve.
        
        Args:
            max_lines: Maximum number of lines
        """
        self._max_lines = max_lines
    
    @property
    def is_processing(self) -> bool:
        """Check if the session is currently processing a command."""
        try:
            # Try to access the is_processing attribute of the iTerm2 session
            if hasattr(self.session, 'is_processing'):
                return self.session.is_processing
            else:
                # If it doesn't exist, log a warning and return a default value
                import logging
                logging.getLogger("iterm-mcp-session").warning(
                    f"Session {self.id} ({self._name}) does not have is_processing attribute"
                )
                return False
        except Exception as e:
            # Handle any exceptions that might occur
            import logging
            logging.getLogger("iterm-mcp-session").error(
                f"Error checking is_processing for session {self.id} ({self._name}): {str(e)}"
            )
            return False
    
    def set_logger(self, logger: ItermSessionLogger) -> None:
        """Set the logger for this session.
        
        Args:
            logger: The logger to use
        """
        self.logger = logger
    
    async def set_name(self, name: str) -> None:
        """Set the name of the session.
        
        Args:
            name: The new name for the session
        """
        old_name = self._name
        self._name = name
        await self.session.async_set_name(name)
        
        # Log the name change
        if self.logger:
            self.logger.log_session_renamed(name)
    
    async def send_text(self, text: str) -> None:
        """Send text to the session.
        
        Args:
            text: The text to send
        """
        await self.session.async_send_text(text)
        
        # Log the command
        if self.logger:
            # If text ends with newline, it's likely a command
            if text.endswith("\n") or text.endswith("\r"):
                self.logger.log_command(text.rstrip("\r\n"))
    
    async def get_screen_contents(self, max_lines: Optional[int] = None) -> str:
        """Get the contents of the session's screen.
        
        Args:
            max_lines: Maximum number of lines to retrieve (defaults to session's max_lines)
            
        Returns:
            The text contents of the screen
        """
        contents = await self.session.async_get_screen_contents()
        lines = []
        
        # Use instance default if not specified
        if max_lines is None:
            max_lines = self._max_lines
            
        max_lines = min(max_lines, contents.number_of_lines)
        
        for i in range(max_lines):
            line = contents.line(i)
            line_text = line.string
            if line_text:
                lines.append(line_text)
        
        output = "\n".join(lines)
        
        # Log the output
        if self.logger:
            self.logger.log_output(output)
        
        return output
    
    async def send_control_character(self, character: str) -> None:
        """Send a control character to the session.
        
        Args:
            character: The character (e.g., "c" for Ctrl+C)
        """
        if len(character) != 1 or not character.isalpha():
            raise ValueError("Control character must be a single letter")
            
        # Convert to uppercase and then to control code
        character = character.upper()
        code = ord(character) - 64
        control_sequence = chr(code)
        
        await self.session.async_send_text(control_sequence)
        
        # Log the control character
        if self.logger:
            self.logger.log_control_character(character)
    
    async def clear_screen(self) -> None:
        """Clear the screen."""
        await self.session.async_send_text("\u001b[2J\u001b[H")  # ANSI clear screen
        
        # Log the clear action
        if self.logger:
            self.logger.log_custom_event("CLEAR_SCREEN", "Screen cleared")
            
    async def start_monitoring(self, update_interval: float = 0.5) -> None:
        """Start monitoring the screen for changes.
        
        This allows real-time capture of terminal output without requiring explicit
        calls to get_screen_contents(). Uses polling-based approach as a fallback
        since subscription-based approach may have WebSocket issues.
        
        Args:
            update_interval: How often to check for updates (in seconds)
        """
        if self._monitoring:
            return
            
        self._monitoring = True
        
        async def monitor_screen_polling():
            """Polling-based screen monitoring as a fallback approach."""
            try:
                import logging
                logger = logging.getLogger("iterm-mcp-session")
                logger.info(f"Starting polling-based screen monitoring for session {self.id}")
                
                if self.logger:
                    self.logger.log_custom_event("MONITORING_STARTED", "Polling-based screen monitoring started")
                
                last_content = await self.get_screen_contents()
                
                while self._monitoring:
                    try:
                        # Get current content
                        current_content = await self.get_screen_contents()
                        
                        # Check if content has changed
                        if current_content != last_content:
                            # Process the content through any registered callbacks
                            for callback in self._monitor_callbacks:
                                # Run each callback in a separate task to prevent blocking
                                try:
                                    # Using ensure_future instead of create_task for better compatibility
                                    asyncio.ensure_future(callback(current_content))
                                except Exception as callback_error:
                                    logger.error(f"Error in callback: {str(callback_error)}")
                            
                            # Update last content and timestamp
                            last_content = current_content
                            self._last_screen_update = time.time()
                        
                        # Sleep to prevent excessive CPU usage
                        await asyncio.sleep(update_interval)
                    except Exception as poll_error:
                        logger.error(f"Error in polling loop: {str(poll_error)}")
                        await asyncio.sleep(update_interval)
            except asyncio.CancelledError:
                logger.info(f"Polling monitor task cancelled for session {self.id}")
            except Exception as e:
                logger.error(f"Fatal error in polling monitor: {str(e)}")
                if self.logger:
                    self.logger.log_custom_event("MONITORING_ERROR", f"Error in screen monitoring: {str(e)}")
            finally:
                self._monitoring = False
                if self.logger:
                    self.logger.log_custom_event("MONITORING_STOPPED", "Screen monitoring stopped")
        
        # Use polling-based approach instead of subscription-based approach
        # to avoid WebSocket frame errors
        self._monitor_task = asyncio.create_task(monitor_screen_polling())
        
    def stop_monitoring(self) -> None:
        """Stop monitoring the screen for changes."""
        if not self._monitoring or not self._monitor_task:
            return
            
        self._monitoring = False
        if not self._monitor_task.done():
            self._monitor_task.cancel()
        self._monitor_task = None
        
    def add_monitor_callback(self, callback: Callable[[str], None]) -> None:
        """Add a callback to be called when the screen changes.
        
        Args:
            callback: A function that takes the screen content as a string
        """
        if callback not in self._monitor_callbacks:
            self._monitor_callbacks.append(callback)
            
    def remove_monitor_callback(self, callback: Callable[[str], None]) -> None:
        """Remove a previously registered callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._monitor_callbacks:
            self._monitor_callbacks.remove(callback)
            
    @property
    def is_monitoring(self) -> bool:
        """Check if the session is being monitored."""
        return self._monitoring
        
    @property
    def last_update_time(self) -> float:
        """Get the timestamp of the last screen update."""
        return self._last_screen_update