#!/bin/bash

# Simple polling-based test runner (runs every 5 seconds)
# For file-change detection, consider using fswatch or inotifywait
# Usage: ./scripts/watch_tests.sh

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Starting Local CI - Watching for changes..."

while true; do
    echo "----------------------------------------"
    echo "Running tests at $(date)"
    
    if python -m unittest discover tests; then
        echo -e "${GREEN}Tests Passed!${NC}"
    else
        echo -e "${RED}Tests Failed!${NC}"
        # Optional: Notify on Mac
        if [[ "$OSTYPE" == "darwin"* ]]; then
            osascript -e 'display notification "Tests Failed!" with title "Local CI"'
        fi
    fi
    
    # Wait for 5 seconds before next run
    sleep 5
done
