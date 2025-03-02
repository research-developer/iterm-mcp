#!/bin/bash
# Script to run Claude Code CLI with our markup

# Get the Claude CLI executable
CLAUDE=$(which claude)

if [ -z "$CLAUDE" ]; then
    echo "Claude CLI is not installed or not in PATH"
    exit 1
fi

# Parse arguments
PROMPT=""
MARKUP_START="<LLM-INGEST>"
MARKUP_END="</LLM-INGEST>"

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 \"Your prompt here\""
    exit 1
fi

# Combine all arguments
for arg in "$@"; do
    PROMPT="$PROMPT $arg"
done

# Create a temporary file for the output
TEMP_FILE=$(mktemp)

# Run Claude Code and capture output
"$CLAUDE" "$PROMPT" > "$TEMP_FILE"

# Print the output
cat "$TEMP_FILE"

# Extract content between markup tags
echo ""
echo "Extracted content for LLM ingestion:"
echo "-----------------------------------"
sed -n "/$MARKUP_START/,/$MARKUP_END/p" "$TEMP_FILE" | sed "s/$MARKUP_START//g" | sed "s/$MARKUP_END//g"

# Clean up
rm "$TEMP_FILE"