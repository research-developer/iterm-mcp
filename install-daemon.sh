#!/usr/bin/env bash
#
# Install iTerm MCP daemon as a launchd service
#
# This installs the daemon to run automatically on login.
# The daemon provides a singleton MCP server for all Claude Code instances.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.iterm-mcp.daemon.plist"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}"
PLIST_DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
LOG_DIR="${HOME}/.iterm-mcp"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo -e "${GREEN}Installing iTerm MCP daemon...${NC}"

# Create log directory
mkdir -p "${LOG_DIR}"

# Stop existing service if running
if launchctl list | grep -q "com.iterm-mcp.daemon"; then
    echo -e "${YELLOW}Stopping existing service...${NC}"
    launchctl unload "${PLIST_DST}" 2>/dev/null || true
fi

# Copy plist to LaunchAgents
echo "Installing launchd plist..."
cp "${PLIST_SRC}" "${PLIST_DST}"

# Load the service
echo "Loading service..."
launchctl load "${PLIST_DST}"

# Check status
sleep 2
if launchctl list | grep -q "com.iterm-mcp.daemon"; then
    echo -e "${GREEN}Service installed and running!${NC}"
    echo ""
    echo "Daemon endpoint: http://127.0.0.1:12345/mcp"
    echo "Logs: ${LOG_DIR}/daemon.log"
    echo ""
    echo "To check status:  launchctl list | grep iterm-mcp"
    echo "To stop:          launchctl unload ${PLIST_DST}"
    echo "To start:         launchctl load ${PLIST_DST}"
    echo "To uninstall:     rm ${PLIST_DST} && launchctl unload ${PLIST_DST}"
else
    echo -e "${YELLOW}Service installed but may not be running. Check logs:${NC}"
    echo "  tail -f ${LOG_DIR}/daemon.log"
fi
