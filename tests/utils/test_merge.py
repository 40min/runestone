"""
Tests for utility logic functions.

This module contains unit tests for the logic utility functions.
"""

from runestone.utils.merge import deep_merge


class TestDeepMerge:
    """Test cases for deep_merge function."""

    def test_merge_simple_dicts(self):
        """Test merging two simple dictionaries."""
        base = {"a": 1, "b": 2}
        update = {"b": 3, "c": 4}
        result = deep_merge(base, update)

        assert result == {"a": 1, "b": 3, "c": 4}
        # Ensure original dicts are not mutated
        assert base == {"a": 1, "b": 2}
        assert update == {"b": 3, "c": 4}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        update = {"b": {"d": 4, "e": 5}, "f": 6}
        result = deep_merge(base, update)

        assert result == {"a": 1, "b": {"c": 2, "d": 4, "e": 5}, "f": 6}

    def test_merge_deeply_nested_dicts(self):
        """Test merging deeply nested dictionaries."""
        base = {"level1": {"level2": {"level3": {"value": "old"}}}}
        update = {"level1": {"level2": {"level3": {"value": "new", "extra": "data"}}}}
        result = deep_merge(base, update)

        assert result == {"level1": {"level2": {"level3": {"value": "new", "extra": "data"}}}}

    def test_merge_lists_concatenate(self):
        """Test that lists are concatenated."""
        base = {"items": ["a", "b"]}
        update = {"items": ["c", "d"]}
        result = deep_merge(base, update)

        assert result == {"items": ["a", "b", "c", "d"]}

    def test_merge_lists_deduplicate(self):
        """Test that duplicate items in lists are removed."""
        base = {"items": ["a", "b", "c"]}
        update = {"items": ["b", "c", "d"]}
        result = deep_merge(base, update)

        # Should preserve order and remove duplicates
        assert result == {"items": ["a", "b", "c", "d"]}

    def test_merge_lists_with_complex_items(self):
        """Test merging lists with complex items (dicts)."""
        base = {"items": [{"id": 1}, {"id": 2}]}
        update = {"items": [{"id": 2}, {"id": 3}]}
        result = deep_merge(base, update)

        # Complex items are compared by string representation
        assert len(result["items"]) == 3

    def test_merge_empty_base(self):
        """Test merging with empty base dictionary."""
        base = {}
        update = {"a": 1, "b": 2}
        result = deep_merge(base, update)

        assert result == {"a": 1, "b": 2}

    def test_merge_empty_update(self):
        """Test merging with empty update dictionary."""
        base = {"a": 1, "b": 2}
        update = {}
        result = deep_merge(base, update)

        assert result == {"a": 1, "b": 2}

    def test_merge_both_empty(self):
        """Test merging two empty dictionaries."""
        result = deep_merge({}, {})
        assert result == {}

    def test_merge_type_replacement(self):
        """Test that different types are replaced, not merged."""
        base = {"a": {"nested": "value"}}
        update = {"a": "simple string"}
        result = deep_merge(base, update)

        assert result == {"a": "simple string"}

    def test_merge_none_values(self):
        """Test handling of None values."""
        base = {"a": 1, "b": None}
        update = {"b": 2, "c": None}
        result = deep_merge(base, update)

        assert result == {"a": 1, "b": 2, "c": None}

    def test_merge_preserves_order(self):
        """Test that list order is preserved during merge."""
        base = {"items": [1, 2, 3]}
        update = {"items": [4, 5]}
        result = deep_merge(base, update)

        assert result["items"] == [1, 2, 3, 4, 5]

    def test_merge_immutability(self):
        """Test that original dictionaries are not mutated."""
        base = {"a": {"b": 1}}
        update = {"a": {"c": 2}}

        base_copy = {"a": {"b": 1}}
        update_copy = {"a": {"c": 2}}

        deep_merge(base, update)

        assert base == base_copy
        assert update == update_copy

    def test_merge_real_world_memory_example(self):
        """Test with a real-world agent memory scenario."""
        base = {
            "name": "Anna",
            "goal": "B1 level by summer",
            "struggles": ["word order"],
        }
        update = {
            "goal": "B2 level by summer",  # Updated goal
            "struggles": ["word order", "pronunciation"],  # Added struggle
            "strengths": ["vocabulary"],  # New field
        }
        result = deep_merge(base, update)

        assert result == {
            "name": "Anna",
            "goal": "B2 level by summer",
            "struggles": ["word order", "pronunciation"],
            "strengths": ["vocabulary"],
        }

    def test_merge_non_dict_base(self):
        """Test behavior when base is not a dict."""
        result = deep_merge("not a dict", {"a": 1})
        assert result == {"a": 1}

    def test_merge_non_dict_update(self):
        """Test behavior when update is not a dict."""
        result = deep_merge({"a": 1}, "not a dict")
        assert result == "not a dict"
