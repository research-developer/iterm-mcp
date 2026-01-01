# Changelog

All notable changes to the iTerm MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Update README with new features documentation ([89a7179](../../commit/89a7179))
- Correct project structure in documentation ([89a7179](../../commit/89a7179))
- Add comprehensive documentation for parallel multi-agent orchestration ([1bf9784](../../commit/1bf9784))
- Document team management and cascading message patterns ([1bf9784](../../commit/1bf9784))
- Add Epic status documentation ([9335c84](../../commit/9335c84))
- Fix protobuf duplicates ([9335c84](../../commit/9335c84))
- Add coverage reporting to CI ([9335c84](../../commit/9335c84))
- Add comprehensive integration analysis documentation ([4bc91ae](../../commit/4bc91ae))
- Document claude-code-mcp integration patterns ([4bc91ae](../../commit/4bc91ae))
- Add documentation for follow-up enhancement issues ([8f48f58](../../commit/8f48f58))
- Complete final epic review documentation ([8f48f58](../../commit/8f48f58))

### Changed
- Add .worktrees directory to .gitignore ([1399fbb](../../commit/1399fbb))
- Update CI configuration for improved testing ([abd973e](../../commit/abd973e))
- Add testing documentation updates ([abd973e](../../commit/abd973e))
- Upgrade codecov GitHub action ([b9206f6](../../commit/b9206f6))
- Make coverage omit patterns explicit in configuration ([b9206f6](../../commit/b9206f6))
- Improve CI test selection logic ([94ea55f](../../commit/94ea55f))
- Update package configuration based on review ([94ea55f](../../commit/94ea55f))
- Add 1mcp-linux-x64 to .gitignore ([0921ea2](../../commit/0921ea2))
- Fix .gitignore formatting for Jupyter patterns ([0921ea2](../../commit/0921ea2))
- Minor updates to logging utilities ([af07e2a](../../commit/af07e2a))
- Update server to maintain persistent connections ([8aea9e8](../../commit/8aea9e8))
- Improve session management reliability ([8aea9e8](../../commit/8aea9e8))
- Update .gitignore with new patterns ([7d16faa](../../commit/7d16faa))

### Fixed
- Apply code review feedback for parallel multi-agent PR ([e305a4c](../../commit/e305a4c))
- Improve code quality and documentation ([e305a4c](../../commit/e305a4c))
- Address final code review comments for PR #12 ([8459a0c](../../commit/8459a0c))
- Apply remaining nitpick fixes ([8459a0c](../../commit/8459a0c))
- Apply PR review feedback for gRPC support ([7e75f0c](../../commit/7e75f0c))
- Improve code quality based on review ([7e75f0c](../../commit/7e75f0c))
- Fix import organization in example script ([e92a2b8](../../commit/e92a2b8))
- Apply code review feedback ([e92a2b8](../../commit/e92a2b8))
- Remove unused `session_map` variable from example code ([63fce96](../../commit/63fce96))
- Clean up example code ([63fce96](../../commit/63fce96))

## [0.5.0] - 2025-12-23

### Added
- Add focus cooldown mechanism to prevent rapid session switching ([6b06458](../../commit/6b06458))
- Improve user experience with controlled focus transitions ([6b06458](../../commit/6b06458))
- Add session tagging system with CRUD operations ([899bc5d](../../commit/899bc5d))
- Add session locking with agent enforcement ([899bc5d](../../commit/899bc5d))
- Add `set_session_tags` MCP tool for tag management ([899bc5d](../../commit/899bc5d))
- Add `lock_session`, `unlock_session`, and `request_session_access` MCP tools ([899bc5d](../../commit/899bc5d))
- Add comprehensive test suite with 24 tests for tagging and locking ([899bc5d](../../commit/899bc5d))
- Add `AgentType` literal support for claude, gemini, codex, copilot CLIs ([6376457](../../commit/6376457))
- Add `agent_type` field to `SessionConfig` for auto-launching agent CLIs ([6376457](../../commit/6376457))
- Add notification system with `NotificationManager` ring buffer storage ([6376457](../../commit/6376457))
- Add `get_notifications`, `get_agent_status_summary`, `notify` MCP tools ([6376457](../../commit/6376457))
- Add `wait_for_agent` tool with polling, timeout, and progress summaries ([6376457](../../commit/6376457))

### Fixed
- Prevent new sessions from stealing focus during creation ([02d3f36](../../commit/02d3f36))
- Improve focus cooldown behavior for better session management ([02d3f36](../../commit/02d3f36))
- Add `calculate_text_delay()` function for dynamic delay based on text length ([bb40b05](../../commit/bb40b05))
- Fix race condition where Enter was processed before large text pastes completed ([bb40b05](../../commit/bb40b05))
- Apply delay scaling: base 50ms + 0.02ms/char, max 500ms ([bb40b05](../../commit/bb40b05))

## [0.4.0] - 2025-12-10

### BREAKING CHANGES
- Rename `set_session_appearances` to `modify_sessions` ([8ff8a18](../../commit/8ff8a18))
- Add `focus` and `set_active` parameters to session modifications ([8ff8a18](../../commit/8ff8a18))
- Consolidate session appearance and focus operations into single tool ([8ff8a18](../../commit/8ff8a18))
- Change default `use_encoding` from 'auto' to False ([cad4823](../../commit/cad4823))
- Direct command sending is now the default behavior ([cad4823](../../commit/cad4823))

### Added
- Add `ColorSpec`, `SessionAppearance` models to core/models.py ([bd60113](../../commit/bd60113))
- Add color and badge methods to `ItermSession`: `set_background_color`, `set_tab_color`, `set_cursor_color`, `set_badge`, `reset_colors` ([bd60113](../../commit/bd60113))
- Add `set_session_appearances` MCP tool for bulk appearance updates ([bd60113](../../commit/bd60113))
- Add `agents_only` filter parameter to `list_sessions` tool ([bd60113](../../commit/bd60113))

### Changed
- Rename `set_session_appearances` to `modify_sessions` ([8ff8a18](../../commit/8ff8a18))
- Add `focus` and `set_active` parameters to session modifications ([8ff8a18](../../commit/8ff8a18))
- Consolidate session appearance and focus operations into single tool ([8ff8a18](../../commit/8ff8a18))
- Combine focus and set active session functionality ([591312c](../../commit/591312c))
- Improve session navigation user experience ([591312c](../../commit/591312c))
- Change default `use_encoding` from 'auto' to False ([cad4823](../../commit/cad4823))
- Direct command sending is now the default behavior ([cad4823](../../commit/cad4823))

### Fixed
- Fix `WriteResult` model conflicting state handling ([14ffbc4](../../commit/14ffbc4))
- Remove unused imports for cleaner codebase ([14ffbc4](../../commit/14ffbc4))
- Fix type hint in `send_hierarchical_message` to accept Optional values ([67f744f](../../commit/67f744f))
- Improve type safety for hierarchical message dispatch ([67f744f](../../commit/67f744f))

## [0.3.0] - 2025-12-07

### BREAKING CHANGES
- Update gRPC proto definitions for parallel operations ([d335ef6](../../commit/d335ef6))
- Update gRPC client to support new parallel API ([d335ef6](../../commit/d335ef6))
- Add `Agent`, `Team`, `AgentRegistry` classes with JSONL persistence ([fd2279f](../../commit/fd2279f))
- Add Pydantic models: `SessionTarget`, `SessionMessage`, `WriteToSessionsRequest` ([fd2279f](../../commit/fd2279f))
- Rename `write_to_terminal` to `write_to_sessions`, `read_terminal_output` to `read_sessions` ([fd2279f](../../commit/fd2279f))
- Implement parallel execution using `asyncio.gather` ([fd2279f](../../commit/fd2279f))
- Add `send_conditions` regex for conditional message dispatch ([fd2279f](../../commit/fd2279f))
- Implement duplicate message prevention with SHA256 hashing ([fd2279f](../../commit/fd2279f))
- Add cascading message support (broadcast -> team -> agent specificity) ([fd2279f](../../commit/fd2279f))
- Add `register_agent`, `create_team`, `assign_agent_to_team` MCP tools ([fd2279f](../../commit/fd2279f))
- Add `set_active_session` for default session targeting ([fd2279f](../../commit/fd2279f))

### Added
- Add support for hierarchical pane layouts ([ac30651](../../commit/ac30651))
- Implement cascading control flow for message dispatch ([ac30651](../../commit/ac30651))
- Add `send_hierarchical_message` for team/agent targeting ([ac30651](../../commit/ac30651))
- Add `Playbook`, `PlaybookCommand` models for orchestration ([fbb4ae2](../../commit/fbb4ae2))
- Add `orchestrate_playbook` MCP tool for layout + commands + cascade + reads ([fbb4ae2](../../commit/fbb4ae2))
- Align FastMCP schema with gRPC definitions ([fbb4ae2](../../commit/fbb4ae2))
- Add comprehensive model tests ([fbb4ae2](../../commit/fbb4ae2))
- Add comprehensive documentation for iTerm2 orchestration agent ([4042ec9](../../commit/4042ec9))
- Include usage examples and API reference ([4042ec9](../../commit/4042ec9))
- Add `remove_agent` MCP tool for unregistering agents ([d637aed](../../commit/d637aed))
- Add `remove_team` MCP tool for team cleanup ([d637aed](../../commit/d637aed))
- Add comprehensive test suite for agent registry ([a1f87bf](../../commit/a1f87bf))
- Add model validation tests for Pydantic schemas ([a1f87bf](../../commit/a1f87bf))
- Add `Agent`, `Team`, `AgentRegistry` classes with JSONL persistence ([fd2279f](../../commit/fd2279f))
- Add Pydantic models: `SessionTarget`, `SessionMessage`, `WriteToSessionsRequest` ([fd2279f](../../commit/fd2279f))
- Rename `write_to_terminal` to `write_to_sessions`, `read_terminal_output` to `read_sessions` ([fd2279f](../../commit/fd2279f))
- Implement parallel execution using `asyncio.gather` ([fd2279f](../../commit/fd2279f))
- Add `send_conditions` regex for conditional message dispatch ([fd2279f](../../commit/fd2279f))
- Implement duplicate message prevention with SHA256 hashing ([fd2279f](../../commit/fd2279f))
- Add cascading message support (broadcast -> team -> agent specificity) ([fd2279f](../../commit/fd2279f))
- Add `register_agent`, `create_team`, `assign_agent_to_team` MCP tools ([fd2279f](../../commit/fd2279f))
- Add `set_active_session` for default session targeting ([fd2279f](../../commit/fd2279f))
- Add smart base64 encoding option for command execution ([e8fae0f](../../commit/e8fae0f))
- Handle special characters and quotes in commands ([e8fae0f](../../commit/e8fae0f))

### Changed
- Update gRPC proto definitions for parallel operations ([d335ef6](../../commit/d335ef6))
- Update gRPC client to support new parallel API ([d335ef6](../../commit/d335ef6))

### Fixed
- Fix uuid import issues in tests ([b3f6fe1](../../commit/b3f6fe1))
- Resolve event loop issues for async test execution ([b3f6fe1](../../commit/b3f6fe1))
- Fix `layout_type` values to use lowercase format ([199e7be](../../commit/199e7be))
- Ensure compatibility with `create_sessions` tool expectations ([199e7be](../../commit/199e7be))
- Update FastMCP resource handlers for compatibility ([ef22fe9](../../commit/ef22fe9))
- Add direct runner script for easier server startup ([ef22fe9](../../commit/ef22fe9))

## [0.2.0] - 2025-12-02

### BREAKING CHANGES
- Implement gRPC server alongside FastMCP server ([165ea64](../../commit/165ea64))
- Rename module from `server` to `iterm_mcpy` ([165ea64](../../commit/165ea64))
- Add protobuf definitions in `protos/iterm_mcp.proto` ([165ea64](../../commit/165ea64))
- Add generated protobuf files ([165ea64](../../commit/165ea64))
- Add `watch_tests.sh` script for development ([165ea64](../../commit/165ea64))
- Add gRPC smoke tests ([165ea64](../../commit/165ea64))

### Added
- Add parameter validation for `max_lines` in `GetScreenContents` ([d0e5ab1](../../commit/d0e5ab1))
- Improve input validation and error messages ([d0e5ab1](../../commit/d0e5ab1))
- Add gRPC client implementation for programmatic access ([cec294c](../../commit/cec294c))
- Add CI workflow for automated testing ([cec294c](../../commit/cec294c))
- Implement gRPC server alongside FastMCP server ([165ea64](../../commit/165ea64))
- Rename module from `server` to `iterm_mcpy` ([165ea64](../../commit/165ea64))
- Add protobuf definitions in `protos/iterm_mcp.proto` ([165ea64](../../commit/165ea64))
- Add generated protobuf files ([165ea64](../../commit/165ea64))
- Add `watch_tests.sh` script for development ([165ea64](../../commit/165ea64))
- Add gRPC smoke tests ([165ea64](../../commit/165ea64))
- Add `execute_command()` method with base64 encoding support ([9c82229](../../commit/9c82229))
- Fix quote and special character handling issues ([9c82229](../../commit/9c82229))
- Commands are encoded, sent as eval wrapper, decoded and executed ([9c82229](../../commit/9c82229))
- Add optional `use_encoding` flag for backwards compatibility ([9c82229](../../commit/9c82229))
- Update .gitignore with additional patterns ([8edde75](../../commit/8edde75))
- Add comprehensive test suite for command output tracking ([8edde75](../../commit/8edde75))
- Add `execute_command()` method to `ItermTerminal` ([9b7b776](../../commit/9b7b776))
- Add command position tracking via `_last_command_index` in logger ([9b7b776](../../commit/9b7b776))
- Add `get_output_since_last_command()` method ([9b7b776](../../commit/9b7b776))
- Enable retrieval of output generated since the last command ([9b7b776](../../commit/9b7b776))

### Changed
- Refactor tests to use `AsyncMock` for async initialization ([c582c52](../../commit/c582c52))
- Improve async test patterns and reliability ([c582c52](../../commit/c582c52))
- Apply code review feedback to session.py ([cc809d7](../../commit/cc809d7))
- Improve code quality and readability ([cc809d7](../../commit/cc809d7))
- Move base64 import from function-level to module-level ([f38b1ce](../../commit/f38b1ce))
- Improve import organization ([f38b1ce](../../commit/f38b1ce))

### Fixed
- Fix `ListSessions` test to pass proper `Empty` message ([301ff10](../../commit/301ff10))
- Resolve protobuf compatibility issue in tests ([301ff10](../../commit/301ff10))
- Update protobuf version requirement in dependencies ([dfdd11a](../../commit/dfdd11a))
- Ensure compatibility with generated protobuf code ([dfdd11a](../../commit/dfdd11a))

## [0.1.0] - 2025-03-04

### BREAKING CHANGES
- Remove TypeScript implementation and dependencies ([08de414](../../commit/08de414))
- Move code from `iterm_mcp_python/` to root directory ([08de414](../../commit/08de414))
- Simplify project structure for better maintainability ([08de414](../../commit/08de414))

### Added
- Add `send_special_key` method supporting Enter, Tab, Escape, arrow keys, etc. ([de3ace0](../../commit/de3ace0))
- Add `send_special_key` MCP tool ([de3ace0](../../commit/de3ace0))
- Add `execute` parameter to `write_to_terminal` for CLI interaction ([de3ace0](../../commit/de3ace0))
- Change server port to 12340-12349 range to avoid conflicts ([de3ace0](../../commit/de3ace0))
- Add automatic port selection if primary port is busy ([de3ace0](../../commit/de3ace0))
- Improve `install_claude_desktop.py` with server status checking ([de3ace0](../../commit/de3ace0))
- Create FastMCP-based implementation using official MCP Python SDK ([6c64cac](../../commit/6c64cac))
- Convert all tools to decorator-based syntax ([6c64cac](../../commit/6c64cac))
- Add resources for terminal output and information ([6c64cac](../../commit/6c64cac))
- Add prompts for monitoring and command execution ([6c64cac](../../commit/6c64cac))
- Implement proper lifespan management for iTerm2 connections ([6c64cac](../../commit/6c64cac))
- Fix WebSocket close frame issues by using official SDK ([6c64cac](../../commit/6c64cac))
- Add aggressive termination to prevent hanging on exit ([6c64cac](../../commit/6c64cac))
- Document known WebSocket close frame issue in CLAUDE.md ([455af6b](../../commit/455af6b))
- Provide workaround guidance ([455af6b](../../commit/455af6b))
- Implement MCP server for iTerm2 controller ([f85a2bb](../../commit/f85a2bb))
- Expose terminal management via MCP tools ([f85a2bb](../../commit/f85a2bb))
- Add resources for session information ([f85a2bb](../../commit/f85a2bb))
- Create prompts for command execution and monitoring ([f85a2bb](../../commit/f85a2bb))
- Add Claude Desktop integration setup ([f85a2bb](../../commit/f85a2bb))
- Update dependencies to include MCP SDK ([f85a2bb](../../commit/f85a2bb))
- Implement UUID-based persistent session IDs for reconnection ([b358b60](../../commit/b358b60))
- Add persistent session storage in `~/.iterm_mcp_logs/persistent_sessions.json` ([b358b60](../../commit/b358b60))
- Create `get_session_by_persistent_id` method for session lookup ([b358b60](../../commit/b358b60))
- Add configurable line limits for screen content retrieval ([b358b60](../../commit/b358b60))
- Implement per-session and global default line limits ([b358b60](../../commit/b358b60))
- Create overflow tracking for large terminal outputs ([b358b60](../../commit/b358b60))
- Add comprehensive test suites for both features ([b358b60](../../commit/b358b60))
- Add documentation for advanced features in README ([0a69602](../../commit/0a69602))
- Include usage examples for new functionality ([0a69602](../../commit/0a69602))
- Add multi-session management capabilities ([979b117](../../commit/979b117))
- Create enhanced demo script with advanced features ([979b117](../../commit/979b117))
- Implement screen monitoring using iTerm2's API ([e8c01fe](../../commit/e8c01fe))
- Add snapshot files for real-time output access ([e8c01fe](../../commit/e8c01fe))
- Create regex-based output filtering system ([e8c01fe](../../commit/e8c01fe))
- Support callbacks for terminal output processing ([e8c01fe](../../commit/e8c01fe))
- Add tests for monitoring and filtering functionality ([e8c01fe](../../commit/e8c01fe))
- Refactor core implementation to use iTerm2 Python API ([c9335f1](../../commit/c9335f1))
- Create comprehensive session and terminal management classes ([c9335f1](../../commit/c9335f1))
- Add logging system for tracking session activity ([c9335f1](../../commit/c9335f1))
- Implement layout management with named panes ([c9335f1](../../commit/c9335f1))
- Add test suite for functionality verification ([c9335f1](../../commit/c9335f1))
- Create demo script showing basic functionality ([c9335f1](../../commit/c9335f1))
- Update documentation with usage examples ([c9335f1](../../commit/c9335f1))
- Add CLAUDE.md project documentation file ([0fb2027](../../commit/0fb2027))
- Document fixed issues and remaining work ([0fb2027](../../commit/0fb2027))
- Add next steps and development guidance ([0fb2027](../../commit/0fb2027))
- Add recent changes section documenting March 2025 updates ([ab5ff3b](../../commit/ab5ff3b))
- Include special key support and FastMCP documentation ([ab5ff3b](../../commit/ab5ff3b))

### Changed
- Remove TypeScript references from CLAUDE.md ([7eb46f0](../../commit/7eb46f0))
- Document latest changes and project structure ([7eb46f0](../../commit/7eb46f0))
- Remove TypeScript implementation and dependencies ([08de414](../../commit/08de414))
- Move code from `iterm_mcp_python/` to root directory ([08de414](../../commit/08de414))
- Simplify project structure for better maintainability ([08de414](../../commit/08de414))

### Fixed
- Fix test imports for reorganized directory structure ([ffb0d07](../../commit/ffb0d07))
- Ensure all tests pass with new layout ([ffb0d07](../../commit/ffb0d07))
- Update imports throughout codebase for new structure ([f4f1495](../../commit/f4f1495))
- Update install script for new directory layout ([f4f1495](../../commit/f4f1495))
- Replace subscription-based monitoring with polling-based approach ([143e0ff](../../commit/143e0ff))
- Add async initialization waiting with timeout for monitoring ([143e0ff](../../commit/143e0ff))
- Implement event-based signaling for monitor task readiness ([143e0ff](../../commit/143e0ff))
- Fix line-by-line filtering to correctly process individual output lines ([143e0ff](../../commit/143e0ff))
- Change `stop_monitoring` to async method for proper cleanup ([143e0ff](../../commit/143e0ff))
- Implement robust error handling in all async functions ([a78998c](../../commit/a78998c))
- Add detailed logging for all operations ([a78998c](../../commit/a78998c))
- Fix WebSocket frame handling with comprehensive try/except blocks ([a78998c](../../commit/a78998c))
- Fix parameter mismatch in `create_layout` function ([1f03d32](../../commit/1f03d32))
- Keep parameter name as `session_names` in MCP server, pass as `pane_names` to layout manager ([1f03d32](../../commit/1f03d32))
- Improve Claude Desktop integration process ([4ad2f54](../../commit/4ad2f54))
- Add better error handling for integration setup ([4ad2f54](../../commit/4ad2f54))
