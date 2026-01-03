"""Session management for iTerm2 interaction."""

import asyncio
import base64
import os
import re
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union, Callable, Literal

import iterm2

from utils.logging import ItermSessionLogger
from utils.otel import trace_operation, add_span_attributes, add_span_event, create_span

# Characters that can cause shell parsing issues when typed directly
# These require base64 encoding to safely execute
SHELL_UNSAFE_CHARS = set("\"'`$!\\|&;<>(){}[]")

# Simpler pattern for common safe commands (alphanumeric, spaces, basic punctuation)
SIMPLE_COMMAND_PATTERN = re.compile(r'^[a-zA-Z0-9_\-./: =,@#%^*+~]+$')

# Constants for text input delay calculation
BASE_DELAY_SECONDS = 0.05  # 50ms base delay
DELAY_PER_CHAR_SECONDS = 0.00002  # 0.02ms per character (1000 chars = 20ms extra)
MAX_DELAY_SECONDS = 0.5  # Maximum 500ms delay


def calculate_text_delay(text: str) -> float:
    """Calculate appropriate delay before sending Enter based on text length.

    For large text pastes, iTerm needs time to process the input buffer before
    the Enter key is sent. This function returns a delay that scales with text
    length to prevent race conditions where Enter is processed before the text.

    Args:
        text: The text being sent to the terminal

    Returns:
        Delay in seconds (between BASE_DELAY_SECONDS and MAX_DELAY_SECONDS)
    """
    text_length = len(text)
    calculated_delay = BASE_DELAY_SECONDS + (text_length * DELAY_PER_CHAR_SECONDS)
    return min(calculated_delay, MAX_DELAY_SECONDS)


def needs_base64_encoding(command: str) -> bool:
    """Check if a command contains characters that need base64 encoding.

    Args:
        command: The command string to check

    Returns:
        True if the command should be base64 encoded for safe execution
    """
    # Fast path: simple commands with only safe characters
    if SIMPLE_COMMAND_PATTERN.match(command):
        return False

    # Check for shell-unsafe characters
    if any(c in SHELL_UNSAFE_CHARS for c in command):
        return True

    # Check for control characters or non-ASCII
    for c in command:
        code = ord(c)
        if code < 0x20 and c not in '\t\n\r':  # Control chars except whitespace
            return True
        if code > 0x7e:  # Non-ASCII
            return True

    return False

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
    
    @trace_operation("session.send_text")
    async def send_text(self, text: str, execute: bool = True) -> None:
        """Send text to the session.

        Args:
            text: The text to send
            execute: Whether to execute the text as a command by sending Enter
        """
        add_span_attributes(
            session_id=self.id,
            session_name=self._name,
            text_length=len(text),
            execute=execute,
        )

        # Strip any trailing newlines/carriage returns to avoid double execution
        clean_text = text.rstrip("\r\n")

        # Send the text first
        await self.session.async_send_text(clean_text)

        # Send Enter/Return key to execute if requested
        if execute:
            # Wait for iTerm to process the text before sending Enter
            # Delay scales with text length to handle large pastes
            delay = calculate_text_delay(clean_text)
            await asyncio.sleep(delay)
            await self.session.async_send_text("\r")

        # Log the command
        if self.logger:
            self.logger.log_command(clean_text)

        add_span_event("text_sent", {"text_length": len(clean_text), "executed": execute})

    @trace_operation("session.execute_command")
    async def execute_command(
        self,
        command: str,
        use_encoding: Union[bool, Literal["auto"]] = False
    ) -> None:
        """Execute a command in the session.

        By default, sends the command directly without any encoding. The base64
        encoding option exists for edge cases where direct typing fails, but
        should rarely be needed since most shells handle quoted/escaped input.

        Args:
            command: The command to execute (raw, unencoded)
            use_encoding: Encoding mode:
                - False (default): Send command directly (recommended)
                - "auto": Only encode if command contains unusual characters
                - True: Always use base64 encoding (rarely needed)

        Note:
            The base64 encoding wraps commands in 'eval "$(echo ... | base64 -d)"'
            which can trigger security policy violations in some environments.
            Only use encoding when absolutely necessary (e.g., binary data or
            control characters in the command).
        """
        add_span_attributes(
            session_id=self.id,
            session_name=self._name,
            command_length=len(command),
            use_encoding=str(use_encoding),
        )

        # Strip any trailing newlines/carriage returns from input
        clean_command = command.rstrip("\r\n")

        # Determine if we should encode
        should_encode = (
            use_encoding is True or
            (use_encoding == "auto" and needs_base64_encoding(clean_command))
        )

        if should_encode:
            # Encode the command to avoid quote/special character issues
            # The command goes in as plain text, gets encoded, sent, decoded, and executed
            encoded = base64.b64encode(clean_command.encode('utf-8')).decode('ascii')

            # Wrap in a one-liner that decodes and executes
            # Using 'eval "$(echo ... | base64 -d)"' ensures proper shell parsing
            # Note: base64 output is safe (only contains A-Z, a-z, 0-9, +, /, =)
            # so no shell escaping of the encoded string is needed
            wrapper = f'eval "$(echo {encoded} | base64 -d)"'

            # Send the wrapper command
            await self.session.async_send_text(wrapper)
            text_sent = wrapper
        else:
            # Direct sending - command is sent as-is (default behavior)
            await self.session.async_send_text(clean_command)
            text_sent = clean_command

        # Wait for iTerm to process the text before sending Enter
        # Delay scales with text length to handle large pastes
        delay = calculate_text_delay(text_sent)
        await asyncio.sleep(delay)
        await self.session.async_send_text("\r")

        # Log the original command (not the encoded wrapper)
        if self.logger:
            self.logger.log_command(clean_command)

        add_span_event("command_executed", {
            "command_length": len(clean_command),
            "encoded": should_encode,
        })

    @trace_operation("session.get_screen_contents")
    async def get_screen_contents(self, max_lines: Optional[int] = None) -> str:
        """Get the contents of the session's screen.

        Args:
            max_lines: Maximum number of lines to retrieve (defaults to session's max_lines)

        Returns:
            The text contents of the screen
        """
        add_span_attributes(
            session_id=self.id,
            session_name=self._name,
            requested_max_lines=max_lines if max_lines is not None else self._max_lines,
        )

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

        add_span_event("screen_contents_retrieved", {
            "lines_retrieved": len(lines),
            "total_lines_available": contents.number_of_lines,
            "output_length": len(output),
        })

        return output
    
    @trace_operation("session.send_control_character")
    async def send_control_character(self, character: str) -> None:
        """Send a control character to the session.

        Args:
            character: The character (e.g., "c" for Ctrl+C)
        """
        add_span_attributes(
            session_id=self.id,
            session_name=self._name,
            control_character=character.upper() if character.isalpha() else character,
        )

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

        add_span_event("control_character_sent", {"character": character})
    
    @trace_operation("session.send_special_key")
    async def send_special_key(self, key: str) -> None:
        """Send a special key to the session.

        Args:
            key: The special key name ('enter', 'return', 'tab', 'escape', etc.)
        """
        add_span_attributes(
            session_id=self.id,
            session_name=self._name,
            special_key=key.lower(),
        )

        key = key.lower()

        # Map special key names to their character sequences
        key_map = {
            'enter': '\r',
            'return': '\r',
            'tab': '\t',
            'escape': '\x1b',
            'esc': '\x1b',
            'space': ' ',
            'backspace': '\x7f',
            'delete': '\x1b[3~',
            'up': '\x1b[A',
            'down': '\x1b[B',
            'right': '\x1b[C',
            'left': '\x1b[D',
            'home': '\x1b[H',
            'end': '\x1b[F'
        }

        if key not in key_map:
            raise ValueError(f"Unknown special key: {key}. Supported keys: {', '.join(key_map.keys())}")

        sequence = key_map[key]
        await self.session.async_send_text(sequence)

        # Log the special key
        if self.logger:
            self.logger.log_custom_event("SPECIAL_KEY", f"Sent special key: {key}")

        add_span_event("special_key_sent", {"key": key})
    
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
            
        # Initialize monitoring state, but only set to True once we confirm task is running
        import logging
        logger = logging.getLogger("iterm-mcp-session")
        logger.info(f"Setting up monitoring for session {self.id} ({self._name})")
        
        async def monitor_screen_polling():
            """Polling-based screen monitoring as a fallback approach."""
            try:
                logger.info(f"Starting polling-based screen monitoring for session {self.id}")
                
                if self.logger:
                    self.logger.log_custom_event("MONITORING_STARTED", "Polling-based screen monitoring started")
                
                # Use a ready event to signal when monitoring is fully initialized
                monitoring_initialized.set()
                
                last_content = await self.get_screen_contents()
                
                while self._monitoring:
                    try:
                        # Get current content
                        current_content = await self.get_screen_contents()
                        
                        # Check if content has changed
                        if current_content != last_content:
                            # Process the content through any registered callbacks
                            callback_tasks = []
                            for callback in self._monitor_callbacks:
                                # Run each callback in a separate task to prevent blocking
                                try:
                                    # Create and track all callback tasks
                                    task = asyncio.create_task(callback(current_content))
                                    callback_tasks.append(task)
                                except Exception as callback_error:
                                    logger.error(f"Error in callback: {str(callback_error)}")
                            
                            # Wait for all callbacks to complete
                            if callback_tasks:
                                await asyncio.gather(*callback_tasks, return_exceptions=True)
                            
                            # Update last content and timestamp
                            last_content = current_content
                            self._last_screen_update = time.time()
                        
                        # Sleep to prevent excessive CPU usage
                        await asyncio.sleep(update_interval)
                    except Exception as poll_error:
                        # Special handling for SESSION_NOT_FOUND - expected when session is closed
                        if "SESSION_NOT_FOUND" in str(poll_error):
                            if self._monitoring:
                                # Only log at debug level since this is expected during cleanup
                                logger.debug(f"Session no longer available during monitoring (likely closed): {self.id}")
                                # Signal to exit the monitoring loop
                                self._monitoring = False
                                return
                        else:
                            # Log any other errors as actual errors
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
        
        # Create an event to signal when monitoring is fully initialized
        monitoring_initialized = asyncio.Event()
        
        # Start monitoring flag
        self._monitoring = True
        
        # Use polling-based approach instead of subscription-based approach
        # to avoid WebSocket frame errors
        self._monitor_task = asyncio.create_task(monitor_screen_polling())
        
        # Wait for the monitoring to be properly initialized before returning
        try:
            await asyncio.wait_for(monitoring_initialized.wait(), timeout=3.0)
            logger.info(f"Monitoring successfully started for session {self.id}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for monitoring to initialize for session {self.id}")
            # If initialization times out, clean up
            self._monitoring = False
            if not self._monitor_task.done():
                self._monitor_task.cancel()
            self._monitor_task = None
            raise RuntimeError("Timeout waiting for monitoring to initialize")
        
    async def stop_monitoring(self) -> None:
        """Stop monitoring the screen for changes and ensure callbacks are completed."""
        import logging
        logger = logging.getLogger("iterm-mcp-session")
        
        if not self._monitoring or not self._monitor_task:
            logger.info(f"Monitoring already stopped for session {self.id}")
            return
        
        logger.info(f"Stopping monitoring for session {self.id}")
        # Set monitoring flag to False first to signal the loop to exit
        self._monitoring = False
        
        # Cancel the task if it's still running
        if not self._monitor_task.done():
            try:
                # Wait a short time for graceful shutdown
                await asyncio.sleep(0.2)
                # Cancel if still running after grace period
                if not self._monitor_task.done():
                    logger.info(f"Cancelling monitor task for session {self.id}")
                    self._monitor_task.cancel()
                    # Wait for cancellation to complete
                    try:
                        await asyncio.wait_for(self._monitor_task, timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
            except Exception as e:
                logger.error(f"Error stopping monitoring for session {self.id}: {str(e)}")
        
        # Cleanup
        self._monitor_task = None
        logger.info(f"Monitoring stopped for session {self.id}")
        
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
        """Check if the session is being monitored.
        
        Returns True if monitoring is active (flag is set AND task is running)
        """
        # Check both the flag and that the task exists and is not done
        monitoring_active = (
            self._monitoring and 
            self._monitor_task is not None and 
            not self._monitor_task.done()
        )
        return monitoring_active
        
    @property
    def last_update_time(self) -> float:
        """Get the timestamp of the last screen update."""
        return self._last_screen_update

    async def set_background_color(self, red: int, green: int, blue: int, alpha: int = 255) -> None:
        """Set the background color of the session.

        Args:
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)
            alpha: Alpha component (0-255), default fully opaque
        """
        color = iterm2.Color(red, green, blue, alpha)
        change = iterm2.LocalWriteOnlyProfile()
        change.set_background_color(color)
        await self.session.async_set_profile_properties(change)

        if self.logger:
            self.logger.log_custom_event("SET_BACKGROUND", f"Background color set to RGB({red},{green},{blue})")

    async def set_tab_color(self, red: int, green: int, blue: int, enabled: bool = True) -> None:
        """Set the tab color of the session.

        Args:
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)
            enabled: Whether to enable tab coloring
        """
        color = iterm2.Color(red, green, blue)
        change = iterm2.LocalWriteOnlyProfile()
        change.set_tab_color(color)
        change.set_use_tab_color(enabled)
        await self.session.async_set_profile_properties(change)

        if self.logger:
            self.logger.log_custom_event("SET_TAB_COLOR", f"Tab color set to RGB({red},{green},{blue})")

    async def set_badge(self, text: str) -> None:
        """Set the badge text for the session.

        Args:
            text: The badge text to display (supports escape sequences)
        """
        change = iterm2.LocalWriteOnlyProfile()
        change.set_badge_text(text)
        await self.session.async_set_profile_properties(change)

        if self.logger:
            self.logger.log_custom_event("SET_BADGE", f"Badge set to: {text}")

    async def set_cursor_color(self, red: int, green: int, blue: int) -> None:
        """Set the cursor color of the session.

        Args:
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)
        """
        color = iterm2.Color(red, green, blue)
        change = iterm2.LocalWriteOnlyProfile()
        change.set_cursor_color(color)
        await self.session.async_set_profile_properties(change)

        if self.logger:
            self.logger.log_custom_event("SET_CURSOR_COLOR", f"Cursor color set to RGB({red},{green},{blue})")

    async def reset_colors(self) -> None:
        """Reset all color customizations to profile defaults."""
        change = iterm2.LocalWriteOnlyProfile()
        change.set_use_tab_color(False)
        await self.session.async_set_profile_properties(change)

        if self.logger:
            self.logger.log_custom_event("RESET_COLORS", "Colors reset to profile defaults")