"""Logging utilities for iTerm MCP."""

import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Union


class ItermSessionLogger:
    """Logger for iTerm2 session activities and content.
    
    This logger creates log files for each session to track:
    1. Commands sent to the session
    2. Output from the session
    3. Control characters and other actions
    
    Logs are stored in the user's home directory under .iterm_mcp_logs/
    
    The logger can be configured with regex filters to only capture specific output patterns.
    """
    
    def __init__(
        self,
        session_id: str,
        session_name: str,
        log_dir: Optional[str] = None
    ):
        """Initialize the session logger.
        
        Args:
            session_id: The unique ID of the session
            session_name: The name of the session
            log_dir: Optional override for the log directory
        """
        self.session_id = session_id
        self.session_name = session_name
        
        # Set up logging directory
        self.log_dir = log_dir or os.path.expanduser("~/.iterm_mcp_logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create a timestamp for this session
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create log filename: timestamp_sessionname_sessionid.log
        safe_name = "".join(c if c.isalnum() else "_" for c in session_name)
        self.log_file = os.path.join(
            self.log_dir,
            f"{timestamp}_{safe_name}_{session_id[:8]}.log"
        )
        
        # Create a separate file for the latest snapshot
        self.snapshot_file = os.path.join(
            self.log_dir,
            f"latest_{safe_name}_{session_id[:8]}.txt"
        )
        
        # Initialize with no filters
        self.output_filters = []
        self.latest_output = []  # Store recent output for snapshots
        
        # Set up file logger
        self.logger = logging.getLogger(f"session_{session_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Add a header to the log file
        self.logger.info(
            f"Session started - ID: {session_id} - Name: {session_name}"
        )
    
    def log_command(self, command: str) -> None:
        """Log a command sent to the session.
        
        Args:
            command: The command text
        """
        # Truncate long commands to avoid overwhelming the log
        if len(command) > 500:
            command = command[:497] + "..."
        
        self.logger.info(f"COMMAND: {command}")
    
    def add_output_filter(self, pattern: str) -> None:
        """Add a regex filter for output.
        
        Args:
            pattern: The regex pattern to filter by
        """
        try:
            compiled_pattern = re.compile(pattern)
            self.output_filters.append(compiled_pattern)
            self.logger.info(f"FILTER_ADDED: {pattern}")
        except re.error as e:
            self.logger.error(f"FILTER_ERROR: Invalid regex pattern '{pattern}': {str(e)}")
    
    def clear_output_filters(self) -> None:
        """Clear all output filters."""
        self.output_filters = []
        self.logger.info("FILTERS_CLEARED: All output filters removed")
    
    def matches_filters(self, text: str) -> bool:
        """Check if text matches any of the filters.
        
        Args:
            text: The text to check
            
        Returns:
            True if no filters are set or if the text matches at least one filter
        """
        # If no filters, everything matches
        if not self.output_filters:
            return True
        
        # Check if text matches any filter
        return any(pattern.search(text) for pattern in self.output_filters)

    def log_output(self, output: str) -> None:
        """Log output received from the session.
        
        Args:
            output: The output text
        """
        # Only log the output if it's not too large
        if len(output) > 2000:
            output = output[:1997] + "..."
        
        # Store in latest output cache (up to 1000 lines)
        lines = output.split('\n')
        self.latest_output.extend(lines)
        if len(self.latest_output) > 1000:
            self.latest_output = self.latest_output[-1000:]
        
        # Write to snapshot file
        try:
            with open(self.snapshot_file, 'w') as f:
                f.write('\n'.join(self.latest_output))
        except Exception as e:
            self.logger.error(f"SNAPSHOT_ERROR: Failed to write snapshot: {str(e)}")
        
        # Only log if it matches filters
        if self.matches_filters(output):
            self.logger.info(f"OUTPUT: {output}")
    
    def log_control_character(self, character: str) -> None:
        """Log a control character sent to the session.
        
        Args:
            character: The control character
        """
        self.logger.info(f"CONTROL: Ctrl-{character.upper()}")
    
    def log_session_renamed(self, new_name: str) -> None:
        """Log a session rename event.
        
        Args:
            new_name: The new name of the session
        """
        self.logger.info(f"RENAME: {self.session_name} -> {new_name}")
        self.session_name = new_name
    
    def log_session_closed(self) -> None:
        """Log session closure."""
        self.logger.info(f"Session closed - ID: {self.session_id}")
    
    def log_custom_event(self, event_type: str, data: Union[str, Dict]) -> None:
        """Log a custom event.
        
        Args:
            event_type: The type of event
            data: The event data
        """
        if isinstance(data, dict):
            data_str = json.dumps(data)
        else:
            data_str = str(data)
        
        self.logger.info(f"EVENT[{event_type}]: {data_str}")


class ItermLogManager:
    """Manager for iTerm2 session loggers."""
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        enable_app_log: bool = True,
        max_snapshot_lines: int = 1000
    ):
        """Initialize the log manager.
        
        Args:
            log_dir: Optional override for the log directory
            enable_app_log: Whether to enable application-level logging
            max_snapshot_lines: Maximum number of lines to keep in memory for snapshots
        """
        self.log_dir = log_dir or os.path.expanduser("~/.iterm_mcp_logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Dictionary of session loggers
        self.session_loggers: Dict[str, ItermSessionLogger] = {}
        
        # Settings
        self.max_snapshot_lines = max_snapshot_lines
        
        # Set up application logger if enabled
        if enable_app_log:
            self.setup_app_logger()
    
    def setup_app_logger(self) -> None:
        """Set up the application-level logger."""
        # Get app logger
        app_logger = logging.getLogger("iterm_mcp")
        app_logger.setLevel(logging.INFO)
        
        # Close and clear existing handlers
        for handler in app_logger.handlers:
            handler.close()
        app_logger.handlers = []
        
        # Add file handler
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        app_log_file = os.path.join(self.log_dir, f"app_{timestamp}.log")
        
        file_handler = logging.FileHandler(app_log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        app_logger.addHandler(file_handler)
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)
        
        # Store app logger
        self.app_logger = app_logger
    
    def get_session_logger(
        self,
        session_id: str,
        session_name: str
    ) -> ItermSessionLogger:
        """Get a logger for a session, creating it if it doesn't exist.
        
        Args:
            session_id: The unique ID of the session
            session_name: The name of the session
            
        Returns:
            The session logger
        """
        if session_id not in self.session_loggers:
            self.session_loggers[session_id] = ItermSessionLogger(
                session_id=session_id,
                session_name=session_name,
                log_dir=self.log_dir
            )
        
        return self.session_loggers[session_id]
    
    def remove_session_logger(self, session_id: str) -> None:
        """Remove a session logger.
        
        Args:
            session_id: The unique ID of the session
        """
        if session_id in self.session_loggers:
            self.session_loggers[session_id].log_session_closed()
            del self.session_loggers[session_id]
    
    def log_app_event(self, event_type: str, message: str) -> None:
        """Log an application-level event.
        
        Args:
            event_type: The type of event
            message: The event message
        """
        if hasattr(self, "app_logger"):
            self.app_logger.info(f"{event_type}: {message}")
    
    def get_snapshot(self, session_id: str) -> Optional[str]:
        """Get the latest output snapshot for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            The snapshot contents or None if session not found
        """
        if session_id not in self.session_loggers:
            return None
            
        logger = self.session_loggers[session_id]
        try:
            if os.path.exists(logger.snapshot_file):
                with open(logger.snapshot_file, 'r') as f:
                    return f.read()
            return None
        except Exception as e:
            self.log_app_event("ERROR", f"Failed to read snapshot for session {session_id}: {str(e)}")
            return None
            
    def set_output_filter(self, session_id: str, pattern: str) -> bool:
        """Set an output filter for a session.
        
        Args:
            session_id: The session ID
            pattern: The regex pattern to filter by
            
        Returns:
            True if successful, False otherwise
        """
        if session_id not in self.session_loggers:
            return False
            
        logger = self.session_loggers[session_id]
        try:
            logger.add_output_filter(pattern)
            return True
        except Exception as e:
            self.log_app_event("ERROR", f"Failed to set filter for session {session_id}: {str(e)}")
            return False
            
    def clear_output_filters(self, session_id: str) -> bool:
        """Clear output filters for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            True if successful, False otherwise
        """
        if session_id not in self.session_loggers:
            return False
            
        logger = self.session_loggers[session_id]
        try:
            logger.clear_output_filters()
            return True
        except Exception as e:
            self.log_app_event("ERROR", f"Failed to clear filters for session {session_id}: {str(e)}")
            return False

    def list_session_logs(self) -> Dict[str, str]:
        """List all session log files.
        
        Returns:
            Dictionary mapping session IDs to log file paths
        """
        result = {}
        for session_id, logger in self.session_loggers.items():
            result[session_id] = logger.log_file
        
        return result
        
    def list_session_snapshots(self) -> Dict[str, str]:
        """List all session snapshot files.
        
        Returns:
            Dictionary mapping session IDs to snapshot file paths
        """
        result = {}
        for session_id, logger in self.session_loggers.items():
            result[session_id] = logger.snapshot_file
        
        return result