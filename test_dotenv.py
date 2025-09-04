#!/usr/bin/env python3
"""
Simple test to verify that python-dotenv is loading environment variables correctly.
"""
import os

from dotenv import load_dotenv
from src.runestone.core.console_config import setup_console

# Load environment variables from .env file
load_dotenv()

# Setup console
console = setup_console()

# Test that environment variables are loaded
console.print("Testing environment variable loading from .env file:")
console.print(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
console.print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
console.print(f"OPENAI_MODEL: {os.getenv('OPENAI_MODEL')}")
console.print(f"VERBOSE: {os.getenv('VERBOSE')}")

# Verify expected values
expected_values = {
    "LLM_PROVIDER": "openai",
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_MODEL": "gpt-4o-mini",
    "VERBOSE": "true",
}

success = True
for key, expected_value in expected_values.items():
    actual_value = os.getenv(key)
    if actual_value == expected_value:
        console.print(f"[green]✓[/green] {key}: {actual_value}")
    else:
        console.print(f"[red]✗[/red] {key}: expected '{expected_value}', got '{actual_value}'")
        success = False

if success:
    console.print("\n[green]✓[/green] All environment variables loaded successfully from .env file!")
else:
    console.print("\n[red]✗[/red] Some environment variables were not loaded correctly.")
