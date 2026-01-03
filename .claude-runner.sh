#!/bin/bash
cd "/Users/preston/MCP/iterm-mcp-issue-65-add-hierarchical-task-delegati"

# Set terminal title
echo -ne "\033]0;Issue #65: Add Hierarchical Task Delegation with Manager Agen\007"

echo "🤖 Claude Code - Issue #65: Add Hierarchical Task Delegation with Manager Agents"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "When Claude commits, a PR will be created automatically."
echo "The terminal stays open for follow-up changes."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to create PR
create_pr() {
  COMMITS=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')

  if [ "$COMMITS" -gt 0 ]; then
    # Check if PR already exists
    EXISTING_PR=$(gh pr list --head "issue-65-add-hierarchical-task-delegati" --json number --jq '.[0].number' 2>/dev/null)

    if [ -z "$EXISTING_PR" ]; then
      echo ""
      echo "📤 Pushing branch and creating PR..."

      git push -u origin "issue-65-add-hierarchical-task-delegati" 2>/dev/null

      COMMIT_LIST=$(git log origin/main..HEAD --pretty=format:'- %s' | head -10)

      PR_URL=$(gh pr create \
        --title "Fix #65: Add Hierarchical Task Delegation with Manager Agents" \
        --body "## Summary

Closes #65

## Changes

$COMMIT_LIST

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)" \
        --head "issue-65-add-hierarchical-task-delegati" \
        --base main 2>/dev/null)

      if [ -n "$PR_URL" ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ PR CREATED!"
        echo ""
        echo "   $PR_URL"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        # Update terminal title with PR info
        PR_NUM=$(echo "$PR_URL" | grep -oE '[0-9]+$')
        echo -ne "\033]0;Issue #65 → PR #$PR_NUM\007"
      fi
    else
      # PR exists, just push new commits
      git push origin "issue-65-add-hierarchical-task-delegati" 2>/dev/null
      echo ""
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      echo "📤 Pushed new commits to PR #$EXISTING_PR"
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      echo ""
    fi
  fi
}

# Watch for new commits in background and create PR
LAST_COMMIT=""
while true; do
  CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null)
  if [ "$CURRENT_COMMIT" != "$LAST_COMMIT" ] && [ -n "$LAST_COMMIT" ]; then
    create_pr > /dev/null
  fi
  LAST_COMMIT="$CURRENT_COMMIT"
  sleep 2
done &
WATCHER_PID=$!

# Run Claude interactively
claude --dangerously-skip-permissions "$(cat '/Users/preston/MCP/iterm-mcp-issue-65-add-hierarchical-task-delegati/.claude-prompt.txt')"

# Clean up prompt file
rm -f '/Users/preston/MCP/iterm-mcp-issue-65-add-hierarchical-task-delegati/.claude-prompt.txt'

# Kill the watcher
kill $WATCHER_PID 2>/dev/null

# Final PR check after Claude exits
create_pr > /dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Claude session ended. Terminal staying open."
echo "To clean up after merge: claude-issue clean 65"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Keep terminal open
exec bash
