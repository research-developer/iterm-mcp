# Changelog

## [Unreleased] - 2026-01-01

### Added

#### Agent-Driven Development Feedback System

A comprehensive feedback system that allows AI agents using iterm-mcp to report issues and suggestions via configurable hooks, with feedback triaged into GitHub issues and agents notified when PRs are ready for testing.

##### Core Components (`core/feedback.py`)

- **FeedbackEntry** - Pydantic model for feedback entries with fields:
  - `id` - Auto-generated ID (format: `fb-YYYYMMDD-uuid8`)
  - `agent_id`, `agent_name`, `session_id` - Agent identification
  - `trigger_type` - How feedback was triggered (manual, error_threshold, periodic, pattern_detected)
  - `category` - Feedback category (bug, enhancement, ux, performance, documentation)
  - `title`, `description` - Feedback content
  - `reproduction_steps`, `suggested_improvement`, `error_messages` - Optional details
  - `status` - Lifecycle status (pending, triaged, in_progress, resolved, testing, closed)
  - `github_issue_url`, `github_pr_url` - GitHub integration links
  - `context` - Git and project context

- **FeedbackContext** - Captures environment state:
  - `git_commit`, `git_branch`, `git_diff` - Git state
  - `project_path` - Project isolation
  - `recent_tool_calls`, `recent_errors` - Agent activity
  - `terminal_output_snapshot` - Terminal state

- **FeedbackConfig** - Configuration with sub-configs:
  - `ErrorThresholdConfig` - Trigger after N errors (default: 3)
  - `PeriodicConfig` - Trigger every N tool calls (default: 100, min: 10)
  - `PatternConfig` - Trigger on regex pattern matches (e.g., "this should", "better if")
  - `GitHubConfig` - Repository and label configuration

- **FeedbackHookManager** - Multi-trigger hook system:
  - `record_error(agent_id, error)` - Track errors, trigger at threshold
  - `record_tool_call(agent_id)` - Track tool calls, trigger periodically
  - `check_pattern(agent_id, text)` - Check text for feedback-suggesting patterns
  - `get_stats(agent_id)` - Get current counters and thresholds
  - `clear_state(agent_id)` - Reset all counters for an agent
  - Environment variable overrides: `ITERM_MCP_FEEDBACK_ERROR_THRESHOLD`, `ITERM_MCP_FEEDBACK_PERIODIC_CALLS`

- **FeedbackCollector** - Context capture:
  - `capture_context(project_path, ...)` - Capture git state, recent activity
  - `create_feedback(...)` - Create FeedbackEntry with auto-captured context
  - `write_feedback_file(entry)` - Write feedback to YAML file

- **FeedbackRegistry** - JSONL persistence (follows AgentRegistry pattern):
  - `add(entry)` - Add new feedback entry
  - `get(id)` - Retrieve by ID
  - `update(id, **updates)` - Update entry fields
  - `remove(id)` - Delete entry
  - `query(category, status, agent_name, trigger_type, limit)` - Search with filters
  - `list_all()` - List all entries
  - `link_github_issue(id, url)` - Link to GitHub issue
  - `link_github_pr(id, url)` - Link to GitHub PR
  - `get_by_agent(agent_name)` - Get all feedback from an agent
  - `get_pending()` - Get all pending feedback
  - `get_stats()` - Get statistics

- **FeedbackForker** - Git worktree isolation:
  - `create_worktree(feedback_id)` - Create isolated worktree from HEAD
  - `get_fork_command(session_id, worktree_path)` - Generate `claude --fork-session` command
  - `cleanup_worktree(feedback_id)` - Remove worktree after submission
  - `list_worktrees()` - List all feedback-related worktrees

- **GitHubIntegration** - GitHub CLI (`gh`) integration:
  - `create_issue(feedback, labels, assignee, milestone)` - Create issue from feedback
  - `check_gh_available()` - Verify gh CLI is installed and authenticated
  - Uses `asyncio.create_subprocess_exec` for safe subprocess calls (no shell injection)

##### MCP Tools (`iterm_mcpy/fastmcp_server.py`)

- **submit_feedback** - Manual `/feedback` command
  - Parameters: `agent_name`, `session_id`, `category`, `title`, `description`, `reproduction_steps`, `suggested_improvement`, `error_messages`
  - Returns: Created feedback entry with ID

- **check_feedback_triggers** - Record errors/tool calls and check if triggers fire
  - Parameters: `agent_id`, `error` (optional), `text` (optional for pattern check)
  - Returns: Trigger type if fired, current stats

- **query_feedback** - List/search feedback entries
  - Parameters: `category`, `status`, `agent_name`, `trigger_type`, `limit`
  - Returns: Matching entries

- **fork_for_feedback** - Spawn forked session in git worktree
  - Parameters: `feedback_id`, `session_id`, `agent_name`
  - Returns: Worktree path and fork command

- **triage_feedback_to_github** - Create GitHub issue from feedback
  - Parameters: `feedback_id`, `labels`, `assignee`, `milestone`
  - Returns: Issue URL

- **notify_feedback_update** - Notify agents about PR/status updates
  - Parameters: `feedback_id`, `update_type`, `message`, `pr_url`
  - Returns: Notification confirmation

- **get_feedback_config** - Get/set trigger configuration
  - Parameters: None (returns current config)
  - Returns: Current configuration

##### Exports (`core/__init__.py`)

Added exports for all feedback system classes:
- Enums: `FeedbackCategory`, `FeedbackStatus`, `FeedbackTriggerType`
- Models: `FeedbackContext`, `FeedbackEntry`, `FeedbackConfig`, `ErrorThresholdConfig`, `PeriodicConfig`, `PatternConfig`, `GitHubConfig`
- Core classes: `FeedbackHookManager`, `FeedbackCollector`, `FeedbackRegistry`, `FeedbackForker`, `GitHubIntegration`

##### Tests (`tests/test_feedback.py`)

Comprehensive test suite with 31 tests covering:
- `TestFeedbackEnums` - Enum value validation
- `TestFeedbackContext` - Context model creation
- `TestFeedbackEntry` - Entry model creation and optional fields
- `TestFeedbackConfig` - Default and custom configuration
- `TestFeedbackHookManager` - All trigger types, reset behavior, stats
- `TestFeedbackCollector` - Context capture and feedback creation
- `TestFeedbackRegistry` - CRUD operations, querying, persistence
- `TestFeedbackForker` - Worktree creation and cleanup (mocked)
- `TestGitHubIntegration` - Issue creation (mocked), formatting helpers
- `TestIntegration` - Full workflow test

### Fixed

- **FeedbackHookManager initialization** - Removed invalid `registry` parameter
- **FeedbackForker.project_path** - Made optional with default to current working directory
- **fork_for_feedback method names** - Fixed `create_feedback_worktree` → `create_worktree`
- **Path serialization** - Fixed `worktree_path` → `str(worktree_path)` in JSON response

### Architecture

```
Agent Session --> FeedbackHookManager --> FeedbackCollector --> feedback/*.yaml
                  (multi-trigger)         (context capture)         |
                                                                     v
                                          FeedbackRegistry --> GitHub Issues
                                          (JSONL persist)           |
                                                                     v
                                                             NotificationManager
                                                             (PR ready alerts)
```

### Configuration

Feedback system uses `~/.iterm-mcp/feedback_hooks.json`:

```json
{
  "enabled": true,
  "error_threshold": { "enabled": true, "count": 3 },
  "periodic": { "enabled": true, "tool_call_count": 100 },
  "pattern": { "enabled": true, "patterns": ["this should", "better if"] },
  "github": { "repo": "owner/repo", "default_labels": ["agent-feedback"] }
}
```

Environment variable overrides:
- `ITERM_MCP_FEEDBACK_ERROR_THRESHOLD` - Error count before trigger
- `ITERM_MCP_FEEDBACK_PERIODIC_CALLS` - Tool call count before trigger

### Feedback Lifecycle

```
pending --> triaged --> in_progress --> resolved --> testing --> closed
```

### Files Changed

| File | Lines | Description |
|------|-------|-------------|
| `core/feedback.py` | +1,191 | Core feedback system implementation |
| `core/__init__.py` | +36 | Export feedback classes |
| `iterm_mcpy/fastmcp_server.py` | +547 | MCP tools for feedback |
| `tests/test_feedback.py` | +670 | Comprehensive test suite |
| **Total** | **+2,444** | |
