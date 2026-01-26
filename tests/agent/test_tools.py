from runestone.agent.tools import WordPrioritisationItem


def test_word_prioritisation_item_validation():
    """Test unicode escape decoding validation in WordPrioritisationItem."""

    # Test case 1: Double escaped unicode
    item = WordPrioritisationItem(
        word_phrase="f\\u00f6rs\\u00f6ka", translation="try", example_phrase="Kan du f\\u00f6rs\\u00f6ka?"
    )
    assert item.word_phrase == "försöka"
    assert item.example_phrase == "Kan du försöka?"

    # Test case 2: Normal string
    item = WordPrioritisationItem(word_phrase="försöka", translation="try", example_phrase="Kan du försöka?")
    assert item.word_phrase == "försöka"

    # Test case 3: JSON escaped style mixing (should be handled if it contains \u)
    # Note: if the string passed to Pydantic *is* "abc", it remains "abc".
    # If it is "a\\u0062c", it becomes "abc".
    item = WordPrioritisationItem(word_phrase="a\\u0062c", translation="x", example_phrase="y")
    assert item.word_phrase == "abc"


def test_field_descriptions():
    """Test that the translation field description has been updated."""
    fields = WordPrioritisationItem.model_fields
    translation_desc = fields["translation"].description
    assert "concise" in translation_desc.lower()
    assert "translation of the word_phrase" in translation_desc.lower()
