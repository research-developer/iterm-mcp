# Examples

This directory contains example scripts demonstrating various features of iterm-mcp.

## Multi-Agent Orchestration

**File:** `multi_agent_orchestration.py`

Demonstrates how to use iterm-mcp to coordinate multiple Claude Code instances or other processes running in parallel iTerm sessions.

**Features shown:**
- Creating teams and team hierarchies
- Registering agents with metadata
- Creating multi-pane layouts (quad layout)
- Cascading message dispatch with priority (broadcast → team → agent)
- Parallel command execution across multiple sessions
- Message deduplication
- Session persistence and reconnection

**Run the example:**
```bash
python examples/multi_agent_orchestration.py
```

**Note:** This example requires iTerm2 to be running. The script will:
1. Create a new window with 4 panes (quad layout)
2. Register 3 agents (frontend, backend, testing)
3. Demonstrate various orchestration features
4. Keep sessions open after exit (you can Ctrl+C to exit)

**Integration with @steipete/claude-code-mcp:**

To run Claude Code MCP in each session, uncomment the section in step 6 of the script. This will start `@steipete/claude-code-mcp` in each pane, allowing you to:
- Use iterm-mcp for orchestration and coordination
- Use claude-code-mcp for direct code manipulation in each session
- Get the best of both tools

## Future Examples

More examples will be added to demonstrate:
- Output monitoring and filtering
- Session reconnection after disconnect
- Custom layouts
- gRPC client usage
- Integration with CI/CD workflows
