"""Terminal management for iTerm2 integration."""

import asyncio
from typing import Dict, List, Optional, Tuple, Union

import iterm2

from .session import ItermSession

class ItermTerminal:
    """Manages an iTerm2 terminal with multiple sessions (panes)."""
    
    def __init__(self, connection: iterm2.Connection):
        """Initialize the terminal manager.
        
        Args:
            connection: The iTerm2 connection object
        """
        self.connection = connection
        self.app = None
        self.sessions: Dict[str, ItermSession] = {}
        
    async def initialize(self) -> None:
        """Initialize the connection to iTerm2."""
        self.app = await iterm2.async_get_app(self.connection)
        await self._refresh_sessions()
    
    async def _refresh_sessions(self) -> None:
        """Refresh the list of available sessions."""
        if not self.app:
            raise RuntimeError("Terminal not initialized")
        
        # Clear existing sessions
        self.sessions = {}
        
        # Get all windows
        windows = await self.app.async_get_windows()
        
        # Loop through all windows and tabs to find all sessions
        for window in windows:
            tabs = await window.async_get_tabs()
            for tab in tabs:
                tab_sessions = await tab.async_get_sessions()
                for session in tab_sessions:
                    # Create a new ItermSession and add to the dictionary
                    iterm_session = ItermSession(session)
                    self.sessions[iterm_session.id] = iterm_session
    
    async def get_sessions(self) -> List[ItermSession]:
        """Get all available sessions.
        
        Returns:
            List of session objects
        """
        await self._refresh_sessions()
        return list(self.sessions.values())
    
    async def get_session_by_id(self, session_id: str) -> Optional[ItermSession]:
        """Get a session by its ID.
        
        Args:
            session_id: The unique ID of the session
            
        Returns:
            The session if found, None otherwise
        """
        await self._refresh_sessions()
        return self.sessions.get(session_id)
    
    async def get_session_by_name(self, name: str) -> Optional[ItermSession]:
        """Get a session by its name.
        
        Args:
            name: The name of the session
            
        Returns:
            The first session with the given name if found, None otherwise
        """
        await self._refresh_sessions()
        for session in self.sessions.values():
            if session.name == name:
                return session
        return None
    
    async def create_window(self) -> ItermSession:
        """Create a new iTerm2 window.
        
        Returns:
            The session for the new window
        """
        if not self.app:
            raise RuntimeError("Terminal not initialized")
        
        # Create a new window with default profile
        window = await iterm2.Window.async_create(self.connection)
        
        # Get the first session from the window
        tabs = await window.async_get_tabs()
        if not tabs:
            raise RuntimeError("Failed to create window with tabs")
            
        sessions = await tabs[0].async_get_sessions()
        if not sessions:
            raise RuntimeError("Failed to create window with sessions")
        
        # Create a new ItermSession and add to the dictionary
        session = ItermSession(sessions[0])
        self.sessions[session.id] = session
        
        return session
    
    async def create_tab(self, window_id: Optional[str] = None) -> ItermSession:
        """Create a new tab in the specified window or current window.
        
        Args:
            window_id: Optional ID of the window to create the tab in
            
        Returns:
            The session for the new tab
        """
        if not self.app:
            raise RuntimeError("Terminal not initialized")
            
        # Get the window to create the tab in
        window = None
        if window_id:
            windows = await self.app.async_get_windows()
            for w in windows:
                if w.window_id == window_id:
                    window = w
                    break
            if not window:
                raise ValueError(f"Window with ID {window_id} not found")
        else:
            window = await self.app.async_get_current_window()
            if not window:
                # Create a new window if none exists
                return await self.create_window()
        
        # Create a new tab with default profile
        tab = await window.async_create_tab()
        
        # Get the session from the tab
        sessions = await tab.async_get_sessions()
        if not sessions:
            raise RuntimeError("Failed to create tab with sessions")
        
        # Create a new ItermSession and add to the dictionary
        session = ItermSession(sessions[0])
        self.sessions[session.id] = session
        
        return session
    
    async def create_split_pane(
        self, 
        session_id: str, 
        vertical: bool = False,
        name: Optional[str] = None
    ) -> ItermSession:
        """Create a new split pane from an existing session.
        
        Args:
            session_id: The ID of the session to split
            vertical: Whether to split vertically (True) or horizontally (False)
            name: Optional name for the new session
            
        Returns:
            The session for the new pane
        """
        # Get the source session
        source_session = await self.get_session_by_id(session_id)
        if not source_session:
            raise ValueError(f"Session with ID {session_id} not found")
        
        # Create a new split pane
        profile = await iterm2.LocalWriteOnlyProfile.async_get(self.connection)
        new_session = await source_session.session.async_split_pane(
            vertical=vertical,
            profile=profile
        )
        
        # Create a new ItermSession and add to the dictionary
        iterm_session = ItermSession(new_session, name=name)
        if name:
            await iterm_session.set_name(name)
            
        self.sessions[iterm_session.id] = iterm_session
        
        return iterm_session
    
    async def focus_session(self, session_id: str) -> None:
        """Focus on a specific session.
        
        Args:
            session_id: The ID of the session to focus
        """
        # Get the session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session with ID {session_id} not found")
        
        # Focus the session
        await session.session.async_activate()
        
    async def close_session(self, session_id: str) -> None:
        """Close a specific session.
        
        Args:
            session_id: The ID of the session to close
        """
        # Get the session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session with ID {session_id} not found")
        
        # Close the session
        await session.session.async_close()
        
        # Remove from our sessions dictionary
        if session_id in self.sessions:
            del self.sessions[session_id]