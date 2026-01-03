#!/bin/bash
cd "/Users/preston/MCP/iterm-mcp-issue-61-add-role-based-session-special"

# Set terminal title
echo -ne "\033]0;Issue #61: Add Role-Based Session Specialization\007"

echo "🤖 Claude Code - Issue #61: Add Role-Based Session Specialization"
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
    EXISTING_PR=$(gh pr list --head "issue-61-add-role-based-session-special" --json number --jq '.[0].number' 2>/dev/null)

    if [ -z "$EXISTING_PR" ]; then
      echo ""
      echo "📤 Pushing branch and creating PR..."

      git push -u origin "issue-61-add-role-based-session-special" 2>/dev/null

      COMMIT_LIST=$(git log origin/main..HEAD --pretty=format:'- %s' | head -10)

      PR_URL=$(gh pr create \
        --title "Fix #61: Add Role-Based Session Specialization" \
        --body "## Summary

Closes #61

## Changes

$COMMIT_LIST

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)" \
        --head "issue-61-add-role-based-session-special" \
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
        echo -ne "\033]0;Issue #61 → PR #$PR_NUM\007"
      fi
    else
      # PR exists, just push new commits
      git push origin "issue-61-add-role-based-session-special" 2>/dev/null
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
claude --dangerously-skip-permissions "$(cat '/Users/preston/MCP/iterm-mcp-issue-61-add-role-based-session-special/.claude-prompt.txt')"

# Clean up prompt file
rm -f '/Users/preston/MCP/iterm-mcp-issue-61-add-role-based-session-special/.claude-prompt.txt'

# Kill the watcher
kill $WATCHER_PID 2>/dev/null

# Final PR check after Claude exits
create_pr > /dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Claude session ended. Terminal staying open."
echo "To clean up after merge: claude-issue clean 61"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Keep terminal open
exec bash
