#!/bin/bash

# Bootstrap script to initialize state directory with proper permissions
# This script ensures containers can write to the state directory and database without manual configuration

set -e

STATE_DIR="./state"
STATE_FILE="$STATE_DIR/state.json"
STATE_EXAMPLE="./state.example.json"

echo "🔧 Initializing state directory and database..."

# Create state directory if it doesn't exist
if [ ! -d "$STATE_DIR" ]; then
    echo "📁 Creating state directory: $STATE_DIR"
    mkdir -p "$STATE_DIR"
fi

# Create state.json from example if it doesn't exist
if [ ! -f "$STATE_FILE" ]; then
    if [ -f "$STATE_EXAMPLE" ]; then
        echo "📋 Creating state.json from template"
        cp "$STATE_EXAMPLE" "$STATE_FILE"
    else
        echo "⚠️  Warning: state.example.json not found, creating minimal state.json"
        cat > "$STATE_FILE" << EOF
{
  "update_offset": 0,
  "users": {}
}
EOF
    fi
fi

# Set permissions to allow container access
# Use 777 for the directory to ensure containers can create backup files regardless of UID mapping
echo "🔐 Setting permissions for container access..."
chmod 777 "$STATE_DIR"
chmod 666 "$STATE_FILE"

# Create offset.txt file if it doesn't exist (used by StateManager)
OFFSET_FILE="$STATE_DIR/offset.txt"
if [ ! -f "$OFFSET_FILE" ]; then
    echo "📝 Creating offset file"
    echo "0" > "$OFFSET_FILE"
    chmod 666 "$OFFSET_FILE"
fi

# Note: Database is now stored in state directory, so it inherits proper permissions automatically
DB_FILE="$STATE_DIR/runestone.db"
if [ -f "$DB_FILE" ]; then
    echo "🗃️  Database found in state directory"
    chmod 666 "$DB_FILE"
fi

echo "✅ State directory and database initialization complete"
echo "   - Directory: $STATE_DIR (permissions: $(stat -c %a "$STATE_DIR" 2>/dev/null || stat -f %A "$STATE_DIR"))"
echo "   - State file: $STATE_FILE (permissions: $(stat -c %a "$STATE_FILE" 2>/dev/null || stat -f %A "$STATE_FILE"))"
echo "   - Offset file: $OFFSET_FILE (permissions: $(stat -c %a "$OFFSET_FILE" 2>/dev/null || stat -f %A "$OFFSET_FILE"))"
if [ -f "$DB_FILE" ]; then
    echo "   - Database: $DB_FILE (permissions: $(stat -c %a "$DB_FILE" 2>/dev/null || stat -f %A "$DB_FILE"))"
fi