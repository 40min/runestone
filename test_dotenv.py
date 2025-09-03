#!/usr/bin/env python3
"""
Simple test to verify that python-dotenv is loading environment variables correctly.
"""
import os

from dotenv import load_dotenv
from src.runestone.core.logging_config import setup_logging, get_logger

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()

# Test that environment variables are loaded
logger = get_logger(__name__)
logger.info("Testing environment variable loading from .env file:")
logger.info(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
logger.info(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
logger.info(f"OPENAI_MODEL: {os.getenv('OPENAI_MODEL')}")
logger.info(f"VERBOSE: {os.getenv('VERBOSE')}")

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
        logger.info(f"✓ {key}: {actual_value}")
    else:
        logger.error(f"✗ {key}: expected '{expected_value}', got '{actual_value}'")
        success = False

if success:
    logger.info("\n✓ All environment variables loaded successfully from .env file!")
else:
    logger.error("\n✗ Some environment variables were not loaded correctly.")
