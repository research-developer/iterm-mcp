"""
Changelog entries for iTerm MCP Python implementation.

This module contains structured changelog entries for all meaningful commits
from the Python API implementation (starting at 06ce8b0) to HEAD.

Structure follows Keep a Changelog format:
- Added: for new features
- Changed: for changes in existing functionality
- Fixed: for bug fixes
- Removed: for removed features
- Deprecated: for soon-to-be removed features
- Security: for security improvements
"""

CHANGELOG_ENTRIES = {
    # December 2025 - Multi-agent and Session Management
    "02d3f36": {
        "date": "2025-12-23",
        "title": "Prevent new sessions from stealing focus and improve cooldown",
        "type": "Fixed",
        "entries": [
            "Prevent new sessions from stealing focus during creation",
            "Improve focus cooldown behavior for better session management"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "6b06458": {
        "date": "2025-12-23",
        "title": "Add focus cooldown to prevent rapid session switching",
        "type": "Added",
        "entries": [
            "Add focus cooldown mechanism to prevent rapid session switching",
            "Improve user experience with controlled focus transitions"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "899bc5d": {
        "date": "2025-12-23",
        "title": "Add session tagging and lock enforcement with MCP tooling",
        "type": "Added",
        "entries": [
            "Add session tagging system with CRUD operations",
            "Add session locking with agent enforcement",
            "Add `set_session_tags` MCP tool for tag management",
            "Add `lock_session`, `unlock_session`, and `request_session_access` MCP tools",
            "Add comprehensive test suite with 24 tests for tagging and locking"
        ],
        "breaking": False,
        "pr_number": 53,
    },
    "bb40b05": {
        "date": "2025-12-23",
        "title": "Fix large text paste timing issue with dynamic delay scaling",
        "type": "Fixed",
        "entries": [
            "Add `calculate_text_delay()` function for dynamic delay based on text length",
            "Fix race condition where Enter was processed before large text pastes completed",
            "Apply delay scaling: base 50ms + 0.02ms/char, max 500ms"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "6376457": {
        "date": "2025-12-23",
        "title": "Add multi-agent support, notifications, and wait_for_agent",
        "type": "Added",
        "entries": [
            "Add `AgentType` literal support for claude, gemini, codex, copilot CLIs",
            "Add `agent_type` field to `SessionConfig` for auto-launching agent CLIs",
            "Add notification system with `NotificationManager` ring buffer storage",
            "Add `get_notifications`, `get_agent_status_summary`, `notify` MCP tools",
            "Add `wait_for_agent` tool with polling, timeout, and progress summaries"
        ],
        "breaking": False,
        "pr_number": 40,  # Combined #40, #43, #44
    },
    "8ff8a18": {
        "date": "2025-12-10",
        "title": "Consolidate session tools: add focus param, rename to modify_sessions",
        "type": "Changed",
        "entries": [
            "Rename `set_session_appearances` to `modify_sessions`",
            "Add `focus` and `set_active` parameters to session modifications",
            "Consolidate session appearance and focus operations into single tool"
        ],
        "breaking": True,
        "pr_number": None,
    },
    "591312c": {
        "date": "2025-12-10",
        "title": "Consolidate focus_session to also set active session",
        "type": "Changed",
        "entries": [
            "Combine focus and set active session functionality",
            "Improve session navigation user experience"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "bd60113": {
        "date": "2025-12-10",
        "title": "Add visual appearance models and session customization tools",
        "type": "Added",
        "entries": [
            "Add `ColorSpec`, `SessionAppearance` models to core/models.py",
            "Add color and badge methods to `ItermSession`: `set_background_color`, `set_tab_color`, `set_cursor_color`, `set_badge`, `reset_colors`",
            "Add `set_session_appearances` MCP tool for bulk appearance updates",
            "Add `agents_only` filter parameter to `list_sessions` tool"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "cad4823": {
        "date": "2025-12-09",
        "title": "Change default use_encoding from 'auto' to False for direct command sending",
        "type": "Changed",
        "entries": [
            "Change default `use_encoding` from 'auto' to False",
            "Direct command sending is now the default behavior"
        ],
        "breaking": True,
        "pr_number": None,
    },
    "14ffbc4": {
        "date": "2025-12-09",
        "title": "Fix WriteResult conflicting states and remove unused imports",
        "type": "Fixed",
        "entries": [
            "Fix `WriteResult` model conflicting state handling",
            "Remove unused imports for cleaner codebase"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "67f744f": {
        "date": "2025-12-09",
        "title": "Fix type hint in send_hierarchical_message to accept Optional values",
        "type": "Fixed",
        "entries": [
            "Fix type hint in `send_hierarchical_message` to accept Optional values",
            "Improve type safety for hierarchical message dispatch"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "ac30651": {
        "date": "2025-12-07",
        "title": "Support hierarchical pane layouts and cascading controls",
        "type": "Added",
        "entries": [
            "Add support for hierarchical pane layouts",
            "Implement cascading control flow for message dispatch",
            "Add `send_hierarchical_message` for team/agent targeting"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "fbb4ae2": {
        "date": "2025-12-07",
        "title": "Add playbook orchestration and align FastMCP schema",
        "type": "Added",
        "entries": [
            "Add `Playbook`, `PlaybookCommand` models for orchestration",
            "Add `orchestrate_playbook` MCP tool for layout + commands + cascade + reads",
            "Align FastMCP schema with gRPC definitions",
            "Add comprehensive model tests"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "4042ec9": {
        "date": "2025-12-05",
        "title": "Create iTerm2 orchestration agent documentation",
        "type": "Added",
        "entries": [
            "Add comprehensive documentation for iTerm2 orchestration agent",
            "Include usage examples and API reference"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "b3f6fe1": {
        "date": "2025-12-05",
        "title": "Fix test infrastructure: uuid import and event loop issues",
        "type": "Fixed",
        "entries": [
            "Fix uuid import issues in tests",
            "Resolve event loop issues for async test execution"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "199e7be": {
        "date": "2025-12-05",
        "title": "Fix layout_type values to use lowercase format expected by create_sessions tool",
        "type": "Fixed",
        "entries": [
            "Fix `layout_type` values to use lowercase format",
            "Ensure compatibility with `create_sessions` tool expectations"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "d637aed": {
        "date": "2025-12-05",
        "title": "Add missing remove_agent and remove_team MCP tools",
        "type": "Added",
        "entries": [
            "Add `remove_agent` MCP tool for unregistering agents",
            "Add `remove_team` MCP tool for team cleanup"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "e305a4c": {
        "date": "2025-12-05",
        "title": "Address PR #16 review comments from code review",
        "type": "Fixed",
        "entries": [
            "Apply code review feedback for parallel multi-agent PR",
            "Improve code quality and documentation"
        ],
        "breaking": False,
        "pr_number": 16,
    },
    "1bf9784": {
        "date": "2025-12-05",
        "title": "Add parallel multi-agent orchestration documentation",
        "type": "Added",
        "entries": [
            "Add comprehensive documentation for parallel multi-agent orchestration",
            "Document team management and cascading message patterns"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "d335ef6": {
        "date": "2025-12-05",
        "title": "Update gRPC proto and client for new parallel API",
        "type": "Changed",
        "entries": [
            "Update gRPC proto definitions for parallel operations",
            "Update gRPC client to support new parallel API"
        ],
        "breaking": True,
        "pr_number": None,
    },
    "a1f87bf": {
        "date": "2025-12-05",
        "title": "Add comprehensive tests for agent registry and models",
        "type": "Added",
        "entries": [
            "Add comprehensive test suite for agent registry",
            "Add model validation tests for Pydantic schemas"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "fd2279f": {
        "date": "2025-12-05",
        "title": "Add parallel multi-agent orchestration with teams and cascading messages",
        "type": "Added",
        "entries": [
            "Add `Agent`, `Team`, `AgentRegistry` classes with JSONL persistence",
            "Add Pydantic models: `SessionTarget`, `SessionMessage`, `WriteToSessionsRequest`",
            "Rename `write_to_terminal` to `write_to_sessions`, `read_terminal_output` to `read_sessions`",
            "Implement parallel execution using `asyncio.gather`",
            "Add `send_conditions` regex for conditional message dispatch",
            "Implement duplicate message prevention with SHA256 hashing",
            "Add cascading message support (broadcast -> team -> agent specificity)",
            "Add `register_agent`, `create_team`, `assign_agent_to_team` MCP tools",
            "Add `set_active_session` for default session targeting"
        ],
        "breaking": True,
        "pr_number": None,
    },
    "e8fae0f": {
        "date": "2025-12-05",
        "title": "Smart base64 encoding for commands",
        "type": "Added",
        "entries": [
            "Add smart base64 encoding option for command execution",
            "Handle special characters and quotes in commands"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "ef22fe9": {
        "date": "2025-12-05",
        "title": "Update FastMCP resource handlers and add direct runner",
        "type": "Fixed",
        "entries": [
            "Update FastMCP resource handlers for compatibility",
            "Add direct runner script for easier server startup"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "301ff10": {
        "date": "2025-12-02",
        "title": "Fix: Pass proper Empty message instead of None in ListSessions test",
        "type": "Fixed",
        "entries": [
            "Fix `ListSessions` test to pass proper `Empty` message",
            "Resolve protobuf compatibility issue in tests"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "d0e5ab1": {
        "date": "2025-12-02",
        "title": "Add validation for max_lines parameter in GetScreenContents",
        "type": "Added",
        "entries": [
            "Add parameter validation for `max_lines` in `GetScreenContents`",
            "Improve input validation and error messages"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "dfdd11a": {
        "date": "2025-11-30",
        "title": "Fix: Update protobuf version requirement to match generated code",
        "type": "Fixed",
        "entries": [
            "Update protobuf version requirement in dependencies",
            "Ensure compatibility with generated protobuf code"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "cec294c": {
        "date": "2025-11-30",
        "title": "Add gRPC client implementation with CI workflow",
        "type": "Added",
        "entries": [
            "Add gRPC client implementation for programmatic access",
            "Add CI workflow for automated testing"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "c582c52": {
        "date": "2025-11-28",
        "title": "Refactor: Use AsyncMock for async initialization",
        "type": "Changed",
        "entries": [
            "Refactor tests to use `AsyncMock` for async initialization",
            "Improve async test patterns and reliability"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "165ea64": {
        "date": "2025-11-27",
        "title": "Implement gRPC support and rename module to iterm_mcpy",
        "type": "Added",
        "entries": [
            "Implement gRPC server alongside FastMCP server",
            "Rename module from `server` to `iterm_mcpy`",
            "Add protobuf definitions in `protos/iterm_mcp.proto`",
            "Add generated protobuf files",
            "Add `watch_tests.sh` script for development",
            "Add gRPC smoke tests"
        ],
        "breaking": True,
        "pr_number": None,
    },
    "cc809d7": {
        "date": "2025-11-27",
        "title": "Refactor: Address PR review feedback for session.py",
        "type": "Changed",
        "entries": [
            "Apply code review feedback to session.py",
            "Improve code quality and readability"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "f38b1ce": {
        "date": "2025-11-27",
        "title": "Refactor: Move base64 import to module level",
        "type": "Changed",
        "entries": [
            "Move base64 import from function-level to module-level",
            "Improve import organization"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "9c82229": {
        "date": "2025-10-26",
        "title": "Add smart base64 encoding for command execution",
        "type": "Added",
        "entries": [
            "Add `execute_command()` method with base64 encoding support",
            "Fix quote and special character handling issues",
            "Commands are encoded, sent as eval wrapper, decoded and executed",
            "Add optional `use_encoding` flag for backwards compatibility"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "8edde75": {
        "date": "2025-10-26",
        "title": "Update .gitignore and add comprehensive tests for command output tracking",
        "type": "Added",
        "entries": [
            "Update .gitignore with additional patterns",
            "Add comprehensive test suite for command output tracking"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "9b7b776": {
        "date": "2025-10-25",
        "title": "Add command output tracking functionality",
        "type": "Added",
        "entries": [
            "Add `execute_command()` method to `ItermTerminal`",
            "Add command position tracking via `_last_command_index` in logger",
            "Add `get_output_since_last_command()` method",
            "Enable retrieval of output generated since the last command"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "8aea9e8": {
        "date": "2025-04-15",
        "title": "Updated server to be persistent",
        "type": "Changed",
        "entries": [
            "Update server to maintain persistent connections",
            "Improve session management reliability"
        ],
        "breaking": False,
        "pr_number": None,
    },
    # March 2025 - Initial Python Implementation
    "7eb46f0": {
        "date": "2025-03-04",
        "title": "Update CLAUDE.md to remove TypeScript references and add latest changes",
        "type": "Changed",
        "entries": [
            "Remove TypeScript references from CLAUDE.md",
            "Document latest changes and project structure"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "ffb0d07": {
        "date": "2025-03-04",
        "title": "Fix test imports for new directory structure",
        "type": "Fixed",
        "entries": [
            "Fix test imports for reorganized directory structure",
            "Ensure all tests pass with new layout"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "f4f1495": {
        "date": "2025-03-04",
        "title": "Fix: Update imports and install script for new directory structure",
        "type": "Fixed",
        "entries": [
            "Update imports throughout codebase for new structure",
            "Update install script for new directory layout"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "08de414": {
        "date": "2025-03-04",
        "title": "Reorganize project structure to remove TypeScript code",
        "type": "Changed",
        "entries": [
            "Remove TypeScript implementation and dependencies",
            "Move code from `iterm_mcp_python/` to root directory",
            "Simplify project structure for better maintainability"
        ],
        "breaking": True,
        "pr_number": None,
    },
    "de3ace0": {
        "date": "2025-03-04",
        "title": "Add special key support, improve command execution, and update port configuration",
        "type": "Added",
        "entries": [
            "Add `send_special_key` method supporting Enter, Tab, Escape, arrow keys, etc.",
            "Add `send_special_key` MCP tool",
            "Add `execute` parameter to `write_to_terminal` for CLI interaction",
            "Change server port to 12340-12349 range to avoid conflicts",
            "Add automatic port selection if primary port is busy",
            "Improve `install_claude_desktop.py` with server status checking"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "6c64cac": {
        "date": "2025-03-04",
        "title": "Implement FastMCP server using official MCP Python SDK",
        "type": "Added",
        "entries": [
            "Create FastMCP-based implementation using official MCP Python SDK",
            "Convert all tools to decorator-based syntax",
            "Add resources for terminal output and information",
            "Add prompts for monitoring and command execution",
            "Implement proper lifespan management for iTerm2 connections",
            "Fix WebSocket close frame issues by using official SDK",
            "Add aggressive termination to prevent hanging on exit"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "455af6b": {
        "date": "2025-03-02",
        "title": "Document WebSocket close frame issue",
        "type": "Added",
        "entries": [
            "Document known WebSocket close frame issue in CLAUDE.md",
            "Provide workaround guidance"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "143e0ff": {
        "date": "2025-03-02",
        "title": "Resolve screen monitoring and output filtering issues",
        "type": "Fixed",
        "entries": [
            "Replace subscription-based monitoring with polling-based approach",
            "Add async initialization waiting with timeout for monitoring",
            "Implement event-based signaling for monitor task readiness",
            "Fix line-by-line filtering to correctly process individual output lines",
            "Change `stop_monitoring` to async method for proper cleanup"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "a78998c": {
        "date": "2025-03-02",
        "title": "Address major MCP server issues",
        "type": "Fixed",
        "entries": [
            "Implement robust error handling in all async functions",
            "Add detailed logging for all operations",
            "Fix WebSocket frame handling with comprehensive try/except blocks"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "1f03d32": {
        "date": "2025-03-02",
        "title": "Update parameter names in create_layout function",
        "type": "Fixed",
        "entries": [
            "Fix parameter mismatch in `create_layout` function",
            "Keep parameter name as `session_names` in MCP server, pass as `pane_names` to layout manager"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "4ad2f54": {
        "date": "2025-03-02",
        "title": "Improve Claude Desktop integration",
        "type": "Fixed",
        "entries": [
            "Improve Claude Desktop integration process",
            "Add better error handling for integration setup"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "f85a2bb": {
        "date": "2025-03-02",
        "title": "Add MCP server integration",
        "type": "Added",
        "entries": [
            "Implement MCP server for iTerm2 controller",
            "Expose terminal management via MCP tools",
            "Add resources for session information",
            "Create prompts for command execution and monitoring",
            "Add Claude Desktop integration setup",
            "Update dependencies to include MCP SDK"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "b358b60": {
        "date": "2025-03-02",
        "title": "Add persistent sessions and configurable line limits",
        "type": "Added",
        "entries": [
            "Implement UUID-based persistent session IDs for reconnection",
            "Add persistent session storage in `~/.iterm_mcp_logs/persistent_sessions.json`",
            "Create `get_session_by_persistent_id` method for session lookup",
            "Add configurable line limits for screen content retrieval",
            "Implement per-session and global default line limits",
            "Create overflow tracking for large terminal outputs",
            "Add comprehensive test suites for both features"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "0a69602": {
        "date": "2025-03-02",
        "title": "Update README with advanced feature descriptions",
        "type": "Added",
        "entries": [
            "Add documentation for advanced features in README",
            "Include usage examples for new functionality"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "979b117": {
        "date": "2025-03-02",
        "title": "Add multi-session management and enhanced demo",
        "type": "Added",
        "entries": [
            "Add multi-session management capabilities",
            "Create enhanced demo script with advanced features"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "e8c01fe": {
        "date": "2025-03-02",
        "title": "Add real-time session monitoring and log filtering",
        "type": "Added",
        "entries": [
            "Implement screen monitoring using iTerm2's API",
            "Add snapshot files for real-time output access",
            "Create regex-based output filtering system",
            "Support callbacks for terminal output processing",
            "Add tests for monitoring and filtering functionality"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "c9335f1": {
        "date": "2025-03-02",
        "title": "Implement Python-based iTerm2 API integration",
        "type": "Added",
        "entries": [
            "Refactor core implementation to use iTerm2 Python API",
            "Create comprehensive session and terminal management classes",
            "Add logging system for tracking session activity",
            "Implement layout management with named panes",
            "Add test suite for functionality verification",
            "Create demo script showing basic functionality",
            "Update documentation with usage examples"
        ],
        "breaking": False,
        "pr_number": None,
    },
    # Documentation-only commits
    "89a7179": {
        "date": "2025-12-10",
        "title": "Update README with new features and corrected project structure",
        "type": "Added",
        "entries": [
            "Update README with new features documentation",
            "Correct project structure in documentation"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "abd973e": {
        "date": "2025-12-05",
        "title": "Update CI config and testing documentation",
        "type": "Changed",
        "entries": [
            "Update CI configuration for improved testing",
            "Add testing documentation updates"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "9335c84": {
        "date": "2025-12-05",
        "title": "Add Epic status documentation and quick wins",
        "type": "Added",
        "entries": [
            "Add Epic status documentation",
            "Fix protobuf duplicates",
            "Add coverage reporting to CI"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "4bc91ae": {
        "date": "2025-12-05",
        "title": "Add comprehensive claude-code-mcp integration analysis and documentation",
        "type": "Added",
        "entries": [
            "Add comprehensive integration analysis documentation",
            "Document claude-code-mcp integration patterns"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "0fb2027": {
        "date": "2025-03-02",
        "title": "Add CLAUDE.md with documentation of fixed issues and next steps",
        "type": "Added",
        "entries": [
            "Add CLAUDE.md project documentation file",
            "Document fixed issues and remaining work",
            "Add next steps and development guidance"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "ab5ff3b": {
        "date": "2025-03-02",
        "title": "Add recent changes section to CLAUDE.md",
        "type": "Added",
        "entries": [
            "Add recent changes section documenting March 2025 updates",
            "Include special key support and FastMCP documentation"
        ],
        "breaking": False,
        "pr_number": None,
    },
    # Minor/chore commits
    "1399fbb": {
        "date": "2025-12-17",
        "title": "Added .worktrees to .gitignore",
        "type": "Changed",
        "entries": [
            "Add .worktrees directory to .gitignore"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "0921ea2": {
        "date": "2025-11-27",
        "title": "Ignore 1mcp-linux-x64 and add newline after Untitled*.ipynb in .gitignore",
        "type": "Changed",
        "entries": [
            "Add 1mcp-linux-x64 to .gitignore",
            "Fix .gitignore formatting for Jupyter patterns"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "7d16faa": {
        "date": "2025-03-04",
        "title": "Updated gitignore",
        "type": "Changed",
        "entries": [
            "Update .gitignore with new patterns"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "af07e2a": {
        "date": "2025-10-26",
        "title": "Update utils/logging.py",
        "type": "Changed",
        "entries": [
            "Minor updates to logging utilities"
        ],
        "breaking": False,
        "pr_number": None,
    },
    # PR review and refinement commits
    "8459a0c": {
        "date": "2025-12-05",
        "title": "Address remaining PR #12 nitpicks",
        "type": "Fixed",
        "entries": [
            "Address final code review comments for PR #12",
            "Apply remaining nitpick fixes"
        ],
        "breaking": False,
        "pr_number": 12,
    },
    "7e75f0c": {
        "date": "2025-12-05",
        "title": "Address PR #12 review comments",
        "type": "Fixed",
        "entries": [
            "Apply PR review feedback for gRPC support",
            "Improve code quality based on review"
        ],
        "breaking": False,
        "pr_number": 12,
    },
    "b9206f6": {
        "date": "2025-12-05",
        "title": "Final refinements: upgrade codecov action and make coverage omit patterns explicit",
        "type": "Changed",
        "entries": [
            "Upgrade codecov GitHub action",
            "Make coverage omit patterns explicit in configuration"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "e92a2b8": {
        "date": "2025-12-05",
        "title": "Fix import organization in example script per code review",
        "type": "Fixed",
        "entries": [
            "Fix import organization in example script",
            "Apply code review feedback"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "94ea55f": {
        "date": "2025-12-05",
        "title": "Address code review feedback: improve CI test selection and package configuration",
        "type": "Changed",
        "entries": [
            "Improve CI test selection logic",
            "Update package configuration based on review"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "63fce96": {
        "date": "2025-12-05",
        "title": "Remove unused session_map variable from example",
        "type": "Fixed",
        "entries": [
            "Remove unused `session_map` variable from example code",
            "Clean up example code"
        ],
        "breaking": False,
        "pr_number": None,
    },
    "8f48f58": {
        "date": "2025-12-05",
        "title": "Add follow-up enhancement issues and final epic review documentation",
        "type": "Added",
        "entries": [
            "Add documentation for follow-up enhancement issues",
            "Complete final epic review documentation"
        ],
        "breaking": False,
        "pr_number": None,
    },
}

# Commits to skip (merge commits, initial plans, trivial updates)
SKIPPED_COMMITS = [
    "5839563",  # Merge PR #35
    "f9b4346",  # Merge main into branch
    "72f2973",  # Merge PR #31
    "dfe8004",  # Merge PR #36
    "f8e6903",  # Minor update to grpc_server.py
    "a289bde",  # Minor update to fastmcp_server.py
    "f3f7dc9",  # Minor update to fastmcp_server.py
    "f027579",  # Minor update to fastmcp_server.py
    "51ef97e",  # Initial plan
    "13f82e9",  # Merge PR #19
    "88904b9",  # Merge branch
    "54edf94",  # Merge PR #18
    "0c75074",  # Merge PR #20
    "6ac114b",  # Initial plan
    "baa61a3",  # Initial plan
    "123d46b",  # Merge PR #12
    "7074506",  # Merge PR #16
    "510a963",  # Merge PR #2
    "1affec8",  # Merge PR #3
    "3fb5588",  # Merge PR #4
    "d07b783",  # Initial plan
    "f5c3a9e",  # Initial plan
    "be9bfee",  # Merge PR #1
    "1ec8a1a",  # Merge branch
    "cd8abaf",  # Apply Copilot suggestion
    "2ad3cab",  # Apply Copilot suggestion
]

# Version mapping for releases (can be used to generate CHANGELOG.md)
VERSION_MAPPING = {
    "0.5.0": {
        "date": "2025-12-23",
        "commits": ["02d3f36", "6b06458", "899bc5d", "bb40b05", "6376457"],
        "description": "Multi-agent CLI support, notifications, session locking"
    },
    "0.4.0": {
        "date": "2025-12-10",
        "commits": ["8ff8a18", "591312c", "bd60113", "cad4823", "14ffbc4", "67f744f"],
        "description": "Session appearance customization, tool consolidation"
    },
    "0.3.0": {
        "date": "2025-12-07",
        "commits": ["ac30651", "fbb4ae2", "4042ec9", "b3f6fe1", "199e7be", "d637aed",
                   "d335ef6", "a1f87bf", "fd2279f", "e8fae0f", "ef22fe9"],
        "description": "Parallel multi-agent orchestration, playbook support, hierarchical messaging"
    },
    "0.2.0": {
        "date": "2025-11-30",
        "commits": ["301ff10", "d0e5ab1", "dfdd11a", "cec294c", "c582c52", "165ea64",
                   "cc809d7", "f38b1ce", "9c82229", "8edde75", "9b7b776"],
        "description": "gRPC support, smart base64 encoding, command output tracking"
    },
    "0.1.0": {
        "date": "2025-03-04",
        "commits": ["7eb46f0", "ffb0d07", "f4f1495", "08de414", "de3ace0", "6c64cac",
                   "455af6b", "143e0ff", "a78998c", "1f03d32", "4ad2f54", "f85a2bb",
                   "b358b60", "0a69602", "979b117", "e8c01fe", "c9335f1", "0fb2027",
                   "ab5ff3b"],
        "description": "Initial Python implementation with FastMCP, MCP tools, persistent sessions"
    },
}


def get_entries_by_type(entry_type: str) -> dict:
    """Get all entries of a specific type (Added, Changed, Fixed, etc.)."""
    return {
        hash_: entry for hash_, entry in CHANGELOG_ENTRIES.items()
        if entry["type"] == entry_type
    }


def get_breaking_changes() -> dict:
    """Get all entries marked as breaking changes."""
    return {
        hash_: entry for hash_, entry in CHANGELOG_ENTRIES.items()
        if entry.get("breaking", False)
    }


def get_entries_by_date_range(start_date: str, end_date: str) -> dict:
    """Get entries within a date range (YYYY-MM-DD format)."""
    return {
        hash_: entry for hash_, entry in CHANGELOG_ENTRIES.items()
        if start_date <= entry["date"] <= end_date
    }


def get_entries_by_pr(pr_number: int) -> dict:
    """Get all entries associated with a specific PR."""
    return {
        hash_: entry for hash_, entry in CHANGELOG_ENTRIES.items()
        if entry.get("pr_number") == pr_number
    }
