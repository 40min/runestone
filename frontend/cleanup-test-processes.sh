#!/bin/bash
# Script to clean up any orphaned test processes

echo "Checking for orphaned test processes..."

# Find and kill vitest processes
VITEST_PIDS=$(ps aux | grep -E "vitest" | grep -v grep | awk '{print $2}')
if [ -n "$VITEST_PIDS" ]; then
  echo "Found vitest processes: $VITEST_PIDS"
  echo "$VITEST_PIDS" | xargs kill -9 2>/dev/null
  echo "Killed vitest processes"
else
  echo "No vitest processes found"
fi

# Find and kill esbuild processes related to tests
ESBUILD_PIDS=$(ps aux | grep -E "esbuild.*runestone/frontend" | grep -v grep | awk '{print $2}')
if [ -n "$ESBUILD_PIDS" ]; then
  echo "Found esbuild processes: $ESBUILD_PIDS"
  echo "$ESBUILD_PIDS" | xargs kill -9 2>/dev/null
  echo "Killed esbuild processes"
else
  echo "No esbuild processes found"
fi

echo "Cleanup complete!"
