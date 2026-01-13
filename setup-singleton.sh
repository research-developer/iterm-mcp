#!/usr/bin/env bash
#
# Setup iTerm MCP as a singleton daemon
#
# This script:
# 1. Installs the launchd service for auto-start
# 2. Configures Claude Code to connect via HTTP
# 3. Removes the old stdio-based config

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_URL="http://127.0.0.1:12345/mcp"
SERVER_NAME="iTerm"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     iTerm MCP Singleton Daemon Setup                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Install launchd service
echo -e "${GREEN}[1/4]${NC} Installing launchd service..."
"${SCRIPT_DIR}/install-daemon.sh"
echo ""

# Step 2: Wait for daemon to be ready
echo -e "${GREEN}[2/4]${NC} Waiting for daemon to be ready..."
for i in {1..10}; do
    if curl -s -o /dev/null -w "%{http_code}" "${DAEMON_URL}" 2>/dev/null | grep -qE "200|405"; then
        echo -e "  ${GREEN}✓${NC} Daemon is responding"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "  ${YELLOW}⚠${NC} Daemon may still be starting. Check: tail -f ~/.iterm-mcp/daemon.log"
    fi
    sleep 1
done
echo ""

# Step 3: Remove old stdio-based MCP config
echo -e "${GREEN}[3/4]${NC} Checking for existing MCP configurations..."

# Check if there's an old iTerm config
OLD_CONFIGS=$(claude mcp list 2>/dev/null | grep -i "iterm" || true)
if [[ -n "${OLD_CONFIGS}" ]]; then
    echo -e "  ${YELLOW}Found existing iTerm configs:${NC}"
    echo "${OLD_CONFIGS}" | sed 's/^/    /'
    echo ""

    # Extract server names that contain 'iterm' (case insensitive)
    for name in $(claude mcp list 2>/dev/null | grep -ioE "^[^ ]+iterm[^ ]*" || true); do
        echo -e "  Removing old config: ${name}"
        claude mcp remove "${name}" --yes 2>/dev/null || true
    done
fi
echo ""

# Step 4: Add HTTP-based config
echo -e "${GREEN}[4/4]${NC} Adding HTTP-based MCP config..."
claude mcp add --transport http "${SERVER_NAME}" "${DAEMON_URL}" 2>/dev/null || {
    echo -e "  ${YELLOW}⚠${NC} Config may already exist or command failed"
    echo "  Try manually: claude mcp add --transport http ${SERVER_NAME} ${DAEMON_URL}"
}
echo ""

# Summary
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Daemon status:"
"${SCRIPT_DIR}/iterm-mcp-daemon" status 2>/dev/null || true
echo ""
echo "Current MCP config:"
claude mcp list 2>/dev/null | head -10
echo ""
echo -e "${GREEN}Benefits of singleton mode:${NC}"
echo "  • Single process for ALL Claude Code instances"
echo "  • ~90% less memory usage (100MB vs 1.5GB for 15 instances)"
echo "  • Single iTerm2 connection"
echo "  • Shared session cache"
echo ""
echo -e "${YELLOW}To revert to stdio mode:${NC}"
echo "  launchctl unload ~/Library/LaunchAgents/com.iterm-mcp.daemon.plist"
echo "  claude mcp remove ${SERVER_NAME}"
echo "  # Then re-add with command/args format"
