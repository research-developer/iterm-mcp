"""Session management for iTerm2 interaction."""

import asyncio
from typing import Dict, List, Optional, Tuple, Union

import iterm2

class ItermSession:
    """Manages an iTerm2 session (terminal pane)."""
    
    def __init__(self, session: iterm2.Session, name: Optional[str] = None):
        """Initialize a session wrapper.
        
        Args:
            session: The iTerm2 session object
            name: Optional name for the session
        """
        self.session = session
        self._name = name or session.name
    
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
    
    async def set_name(self, name: str) -> None:
        """Set the name of the session.
        
        Args:
            name: The new name for the session
        """
        self._name = name
        await self.session.async_set_name(name)
    
    async def send_text(self, text: str) -> None:
        """Send text to the session.
        
        Args:
            text: The text to send
        """
        await self.session.async_send_text(text)
    
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
        
        return "\n".join(lines)
    
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
    
    async def clear_screen(self) -> None:
        """Clear the screen."""
        await self.session.async_send_text("\u001b[2J\u001b[H")  # ANSI clear screen