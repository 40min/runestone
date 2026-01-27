"""
Core constants for the Runestone application.

This module contains constants used across the application to ensure consistency
and maintainability.
"""

# Batch processing size for vocabulary operations
VOCABULARY_BATCH_SIZE = 100

# Agent memory fields in User model
MEMORY_FIELDS = {"personal_info", "areas_to_improve", "knowledge_strengths"}

# Language mapping: Full Name -> ISO-639-1 code
# Based on frontend LANGUAGES list and Whisper API requirements
LANGUAGE_CODE_MAP = {
    "English": "en",
    "Russian": "ru",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Chinese": "zh",
    "Japanese": "ja",
    "Korean": "ko",
    "Portuguese": "pt",
    "Arabic": "ar",
    "Dutch": "nl",
    "Swedish": "sv",
    "Finnish": "fi",
    "Norwegian": "no",
    "Danish": "da",
    "Polish": "pl",
    "Turkish": "tr",
    "Vietnamese": "vi",
    "Hindi": "hi",
    "Bengali": "bn",
    "Urdu": "ur",
    "Czech": "cs",
    "Slovak": "sk",
    "Hungarian": "hu",
    "Romanian": "ro",
    "Greek": "el",
    "Hebrew": "he",
    "Indonesian": "id",
    "Thai": "th",
    "Malay": "ms",
    "Persian": "fa",
    "Bulgarian": "bg",
    "Croatian": "hr",
    "Serbian": "sr",
    "Slovenian": "sl",
    "Lithuanian": "lt",
    "Latvian": "lv",
    "Estonian": "et",
}
