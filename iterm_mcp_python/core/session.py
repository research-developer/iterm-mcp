"""Session management for iTerm2 interaction."""

import asyncio
from typing import Dict, List, Optional, Tuple, Union

import iterm2

from ..utils.logging import ItermSessionLogger

class ItermSession:
    """Manages an iTerm2 session (terminal pane)."""
    
    def __init__(
        self,
        session: iterm2.Session,
        name: Optional[str] = None,
        logger: Optional[ItermSessionLogger] = None
    ):
        """Initialize a session wrapper.
        
        Args:
            session: The iTerm2 session object
            name: Optional name for the session
            logger: Optional logger for the session
        """
        self.session = session
        self._name = name or session.name
        self.logger = logger
    
    @property
    def id(self) -> str:
        """Get the unique identifier for this session."""
        return self.session.session_id
    
    @property
    def name(self) -> str:
        """Get the name of the session."""
        return self._name
    
    @property
    def is_processing(self) -> bool:
        """Check if the session is currently processing a command."""
        return self.session.is_processing
    
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
    
    async def get_screen_contents(self, max_lines: int = 50) -> str:
        """Get the contents of the session's screen.
        
        Args:
            max_lines: Maximum number of lines to retrieve
            
        Returns:
            The text contents of the screen
        """
        contents = await self.session.async_get_screen_contents()
        lines = []
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