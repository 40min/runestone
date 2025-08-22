#!/usr/bin/env python3
"""
Simple test to verify that python-dotenv is loading environment variables correctly.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Test that environment variables are loaded
print("Testing environment variable loading from .env file:")
print(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
print(f"OPENAI_MODEL: {os.getenv('OPENAI_MODEL')}")
print(f"VERBOSE: {os.getenv('VERBOSE')}")

# Verify expected values
expected_values = {
    'LLM_PROVIDER': 'openai',
    'OPENAI_API_KEY': 'test-openai-key',
    'OPENAI_MODEL': 'gpt-4o',
    'VERBOSE': 'true'
}

success = True
for key, expected_value in expected_values.items():
    actual_value = os.getenv(key)
    if actual_value == expected_value:
        print(f"✓ {key}: {actual_value}")
    else:
        print(f"✗ {key}: expected '{expected_value}', got '{actual_value}'")
        success = False

if success:
    print("\n✓ All environment variables loaded successfully from .env file!")
else:
    print("\n✗ Some environment variables were not loaded correctly.")