#!/bin/bash

# Bootstrap script to initialize state directory with proper permissions.
# This script ensures containers can write to the shared state directory, offset file,
# cache directories, and database without manual configuration.

set -e

STATE_DIR="./state"
OFFSET_FILE="$STATE_DIR/offset.txt"
HF_CACHE_DIR="$STATE_DIR/hf-cache"

echo "🔧 Initializing state directory, caches, and database..."

# Create state directory if it doesn't exist
if [ ! -d "$STATE_DIR" ]; then
    echo "📁 Creating state directory: $STATE_DIR"
    mkdir -p "$STATE_DIR"
fi

if [ ! -d "$HF_CACHE_DIR" ]; then
    echo "📁 Creating Hugging Face cache directory: $HF_CACHE_DIR"
    mkdir -p "$HF_CACHE_DIR"
fi

# Set permissions to allow container access
# Use 777 for the directory to ensure containers can create required files regardless of UID mapping
echo "🔐 Setting permissions for container access..."
chmod 777 "$STATE_DIR"
chmod 777 "$HF_CACHE_DIR"

# Create offset.txt file if it doesn't exist
if [ ! -f "$OFFSET_FILE" ]; then
    echo "📝 Creating offset file"
    echo "0" > "$OFFSET_FILE"
fi
chmod 666 "$OFFSET_FILE"

# Note: Database is now stored in state directory, so it inherits proper permissions automatically
DB_FILE="$STATE_DIR/runestone.db"
if [ -f "$DB_FILE" ]; then
    echo "🗃️  Database found in state directory"
    chmod 666 "$DB_FILE"
fi

echo "✅ State directory and database initialization complete"
echo "   - Directory: $STATE_DIR (permissions: $(stat -c %a "$STATE_DIR" 2>/dev/null || stat -f %A "$STATE_DIR"))"
echo "   - Offset file: $OFFSET_FILE (permissions: $(stat -c %a "$OFFSET_FILE" 2>/dev/null || stat -f %A "$OFFSET_FILE"))"
echo "   - HF cache: $HF_CACHE_DIR (permissions: $(stat -c %a "$HF_CACHE_DIR" 2>/dev/null || stat -f %A "$HF_CACHE_DIR"))"
if [ -f "$DB_FILE" ]; then
    echo "   - Database: $DB_FILE (permissions: $(stat -c %a "$DB_FILE" 2>/dev/null || stat -f %A "$DB_FILE"))"
fi
