"""Terminal management for iTerm2 integration."""

import asyncio
import os
from typing import Dict, List, Optional, Tuple, Union

import iterm2

from .session import ItermSession
from ..utils.logging import ItermLogManager, ItermSessionLogger

class ItermTerminal:
    """Manages an iTerm2 terminal with multiple sessions (panes)."""
    
    def __init__(
        self,
        connection: iterm2.Connection,
        log_dir: Optional[str] = None,
        enable_logging: bool = True
    ):
        """Initialize the terminal manager.
        
        Args:
            connection: The iTerm2 connection object
            log_dir: Optional directory for log files
            enable_logging: Whether to enable session logging
        """
        self.connection = connection
        self.app = None
        self.sessions: Dict[str, ItermSession] = {}
        
        # Initialize logging if enabled
        self.enable_logging = enable_logging
        if enable_logging:
            self.log_manager = ItermLogManager(log_dir=log_dir)
        
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
        windows = self.app.windows
        
        # Loop through all windows and tabs to find all sessions
        for window in windows:
            tabs = window.tabs
            for tab in tabs:
                tab_sessions = tab.sessions
                for session in tab_sessions:
                    # Create a new ItermSession with logger and add to the dictionary
                    iterm_session = ItermSession(session)
                    
                    # Add logger if logging is enabled
                    if self.enable_logging and hasattr(self, "log_manager"):
                        session_logger = self.log_manager.get_session_logger(
                            session_id=iterm_session.id,
                            session_name=iterm_session.name
                        )
                        iterm_session.set_logger(session_logger)
                    
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
        window = await iterm2.Window.async_create(connection=self.connection)
        
        # Get the first session from the window
        tabs = window.tabs
        if not tabs:
            raise RuntimeError("Failed to create window with tabs")
            
        sessions = tabs[0].sessions
        if not sessions:
            raise RuntimeError("Failed to create window with sessions")
        
        # Create a new ItermSession with logger and add to the dictionary
        session = ItermSession(sessions[0])
        
        # Add logger if logging is enabled
        if self.enable_logging and hasattr(self, "log_manager"):
            session_logger = self.log_manager.get_session_logger(
                session_id=session.id,
                session_name=session.name
            )
            session.set_logger(session_logger)
            
            # Log window creation event
            self.log_manager.log_app_event(
                "WINDOW_CREATED", 
                f"Created new window with session: {session.name} ({session.id})"
            )
        
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
            windows = self.app.windows
            for w in windows:
                if w.window_id == window_id:
                    window = w
                    break
            if not window:
                raise ValueError(f"Window with ID {window_id} not found")
        else:
            window = self.app.current_window
            if not window:
                # Create a new window if none exists
                return await self.create_window()
        
        # Create a new tab with default profile
        tab = await window.async_create_tab()
        
        # Get the session from the tab
        sessions = tab.sessions
        if not sessions:
            raise RuntimeError("Failed to create tab with sessions")
        
        # Create a new ItermSession with logger and add to the dictionary
        session = ItermSession(sessions[0])
        
        # Add logger if logging is enabled
        if self.enable_logging and hasattr(self, "log_manager"):
            session_logger = self.log_manager.get_session_logger(
                session_id=session.id,
                session_name=session.name
            )
            session.set_logger(session_logger)
            
            # Log tab creation event
            self.log_manager.log_app_event(
                "TAB_CREATED", 
                f"Created new tab with session: {session.name} ({session.id})"
            )
        
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
        profile_customizations = iterm2.LocalWriteOnlyProfile()
        new_session = await source_session.session.async_split_pane(
            vertical=vertical,
            profile_customizations=profile_customizations
        )
        
        # Create a new ItermSession with logger and add to the dictionary
        iterm_session = ItermSession(new_session, name=name)
        
        # Try to set the name multiple times in case there's a race condition
        if name:
            # Set name and verify
            for attempt in range(3):
                await iterm_session.set_name(name)
                await asyncio.sleep(0.2)  # Give iTerm2 time to set the name
                
                # Refresh the session object
                new_session_name = new_session.name
                if name in new_session_name:
                    break
                    
                print(f"Attempt {attempt+1}: Failed to set session name to '{name}', current name: '{new_session_name}'")
                # If we've tried multiple times and failed, log a warning
                if attempt == 2:
                    print(f"WARNING: Failed to set session name to '{name}' after 3 attempts")
        
        # Add logger if logging is enabled
        if self.enable_logging and hasattr(self, "log_manager"):
            session_logger = self.log_manager.get_session_logger(
                session_id=iterm_session.id,
                session_name=iterm_session.name
            )
            iterm_session.set_logger(session_logger)
            
            # Log split pane creation event
            split_type = "Vertical" if vertical else "Horizontal"
            self.log_manager.log_app_event(
                "PANE_SPLIT", 
                f"Created new {split_type.lower()} split pane: {iterm_session.name} ({iterm_session.id})"
            )
            
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
        
        # Log session closure if logging is enabled
        if self.enable_logging and hasattr(self, "log_manager"):
            # Log in the session logger
            if session.logger:
                session.logger.log_session_closed()
            
            # Log in the app logger
            self.log_manager.log_app_event(
                "SESSION_CLOSED", 
                f"Closed session: {session.name} ({session.id})"
            )
            
            # Remove the session logger
            self.log_manager.remove_session_logger(session_id)
        
        # Close the session
        await session.session.async_close()
        
        # Remove from our sessions dictionary
        if session_id in self.sessions:
            del self.sessions[session_id]