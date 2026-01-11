"""
Runestone utilities.
"""


def deep_merge(base: dict, update: dict) -> dict:
    """
    Recursively merge two dictionaries.

    Creates a new dictionary by merging 'update' into 'base'. For nested dictionaries,
    performs recursive merging. For lists, concatenates and removes duplicates.
    Does not mutate the input dictionaries.

    Args:
        base: Base dictionary to merge into
        update: Dictionary with updates to apply

    Returns:
        New dictionary with merged data

    Examples:
        >>> base = {"a": 1, "b": {"c": 2}}
        >>> update = {"b": {"d": 3}, "e": 4}
        >>> deep_merge(base, update)
        {'a': 1, 'b': {'c': 2, 'd': 3}, 'e': 4}

        >>> base = {"items": ["a", "b"]}
        >>> update = {"items": ["b", "c"]}
        >>> deep_merge(base, update)
        {'items': ['a', 'b', 'c']}
    """
    if not isinstance(base, dict) or not isinstance(update, dict):
        # If either is not a dict, return update (replace behavior)
        return update

    # Create a copy of base to avoid mutation
    result = base.copy()

    for key, value in update.items():
        if key in result:
            base_value = result[key]

            # If both values are dicts, recursively merge
            if isinstance(base_value, dict) and isinstance(value, dict):
                result[key] = deep_merge(base_value, value)
            # If both values are lists, concatenate and deduplicate
            elif isinstance(base_value, list) and isinstance(value, list):
                # Preserve order while removing duplicates
                seen = set()
                merged_list = []
                for item in base_value + value:
                    # Use str representation for hashability
                    item_key = str(item) if not isinstance(item, (str, int, float, bool, type(None))) else item
                    if item_key not in seen:
                        seen.add(item_key)
                        merged_list.append(item)
                result[key] = merged_list
            else:
                # For other types, update value replaces base value
                result[key] = value
        else:
            # Key doesn't exist in base, add it
            result[key] = value

    return result
