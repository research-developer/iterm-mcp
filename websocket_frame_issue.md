# WebSocket Close Frame Issue in iTerm MCP Server

## Problem Description
- **Error Message:** `Error sending command: no close frame received or sent`
- **Trigger:** Sending commands with `wait_for_prompt: true` in Claude Desktop
- **Function Affected:** Command execution to terminal sessions
- **Priority:** CRITICAL - blocks core functionality

## Reproduction Steps
1. Install iTerm MCP server in Claude Desktop
2. Use Claude Desktop to send a command with parameters:
   ```json
   {
     "command": "cd ~/Projects/mlp && pwd",
     "wait_for_prompt": true,
     "session_identifier": "~/MCP (-zsh)"
   }
   ```
3. Observe WebSocket error: "no close frame received or sent"

## Technical Analysis
The issue appears to be in the WebSocket connection handling during command execution. When `wait_for_prompt` is set to true, the server needs to:
1. Send the command to the terminal
2. Wait for the command to complete (prompt to return)
3. Properly close the WebSocket frame
4. Return the result to Claude

One of these steps is failing, likely due to:
- Race conditions in async execution
- Improper handling of WebSocket close frames
- Timeout issues in waiting for the prompt
- Possible session identification problems

## Investigation Plan
1. Add detailed logging around WebSocket frame handling
2. Test command execution with and without the `wait_for_prompt` flag
3. Check session identification logic with different session names
4. Analyze async flow for potential race conditions
5. Add explicit timeout handling and recovery mechanisms

## Potential Fixes
1. Add proper WebSocket close frame sending in command execution path
2. Implement better error handling and recovery for WebSocket operations
3. Add timeout handling with graceful cleanup
4. Ensure all async operations complete properly before connection close
5. Improve session identification robustness

## Development Status
- [x] Issue identified and documented
- [ ] Added detailed logging to pinpoint exact failure point
- [ ] Tested with various session identifiers
- [ ] Implemented WebSocket close frame handling
- [ ] Added timeout and recovery mechanisms
- [ ] Fixed issue and verified with Claude Desktop
- [ ] Added regression tests

## Related Files
- `iterm_mcp_python/server/mcp_server.py` - Main server implementation
- `iterm_mcp_python/core/session.py` - Terminal session handling
- `iterm_mcp_python/core/terminal.py` - Terminal management

## Notes
This issue persists even after the recent fixes to monitoring and filtering functionality. While those improvements have made the tests pass, this WebSocket frame issue is specifically affecting the integration with Claude Desktop in real-world usage scenarios.