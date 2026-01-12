"""
Core constants for the Runestone application.

This module contains constants used across the application to ensure consistency
and maintainability.
"""

# Batch processing size for vocabulary operations
VOCABULARY_BATCH_SIZE = 100

# Agent memory fields in User model
MEMORY_FIELDS = {"personal_info", "areas_to_improve", "knowledge_strengths"}
