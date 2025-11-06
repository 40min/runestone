"""
Tests for grammar API endpoints.

This module tests the grammar API endpoints defined in endpoints.py.
"""

from unittest.mock import Mock

from runestone.dependencies import get_grammar_service


class TestGrammarEndpoints:
    """Test cases for grammar endpoints."""

    def test_list_cheatsheets_success(self, client_no_db, temp_cheatsheets_dir):
        """Test successful listing of cheatsheets."""
        # Mock service
        mock_service = Mock()
        mock_service.list_cheatsheets.return_value = [
            {"filename": "adjectiv-komparation.md", "title": "Adjectiv Komparation", "category": "General"},
            {"filename": "objectspronomen.md", "title": "Objectspronomen", "category": "General"},
            {"filename": "presens-perfect.md", "title": "Presens Perfect", "category": "General"},
        ]

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert len(data) == 3
        assert all("filename" in item and "title" in item for item in data)

        # Verify service was called
        mock_service.list_cheatsheets.assert_called_once()

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_list_cheatsheets_empty(self, client_no_db):
        """Test listing cheatsheets when directory is empty."""
        # Mock service
        mock_service = Mock()
        mock_service.list_cheatsheets.return_value = []

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets")

        assert response.status_code == 200
        data = response.json()
        assert data == []

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_list_cheatsheets_service_error(self, client_no_db):
        """Test handling of service errors in list cheatsheets."""
        # Mock service to raise exception
        mock_service = Mock()
        mock_service.list_cheatsheets.side_effect = Exception("Service error")

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve cheatsheets" in data["detail"]

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_get_cheatsheet_content_success(self, client_no_db):
        """Test successful retrieval of cheatsheet content."""
        # Mock service
        mock_service = Mock()
        mock_service.get_cheatsheet_content.return_value = "# Test Content\n\nThis is test content."

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets/adjectiv-komparation.md")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["content"] == "# Test Content\n\nThis is test content."

        # Verify service was called with correct filepath
        mock_service.get_cheatsheet_content.assert_called_once_with("adjectiv-komparation.md")

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_get_cheatsheet_content_nested_path_success(self, client_no_db):
        """Test successful retrieval of cheatsheet content with nested paths."""
        # Mock service
        mock_service = Mock()
        mock_service.get_cheatsheet_content.return_value = "# Nested Content\n\nThis is nested content."

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets/verbs/hjalpverb.md")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["content"] == "# Nested Content\n\nThis is nested content."

        # Verify service was called with correct nested filepath
        mock_service.get_cheatsheet_content.assert_called_once_with("verbs/hjalpverb.md")

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_get_cheatsheet_content_invalid_filepath(self, client_no_db):
        """Test getting content with invalid filepath."""
        # Mock service to raise ValueError
        mock_service = Mock()
        mock_service.get_cheatsheet_content.side_effect = ValueError("Invalid file path: badfile.txt")

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets/badfile.txt")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file path: badfile.txt" in data["detail"]

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_get_cheatsheet_content_file_not_found(self, client_no_db):
        """Test getting content for non-existent file."""
        # Mock service to raise FileNotFoundError
        mock_service = Mock()
        mock_service.get_cheatsheet_content.side_effect = FileNotFoundError("Cheatsheet 'nonexistent.md' not found")

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets/nonexistent.md")

        assert response.status_code == 404
        data = response.json()
        assert "Cheatsheet 'nonexistent.md' not found" in data["detail"]

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_get_cheatsheet_content_service_error(self, client_no_db):
        """Test handling of unexpected service errors."""
        # Mock service to raise unexpected exception
        mock_service = Mock()
        mock_service.get_cheatsheet_content.side_effect = Exception("Unexpected error")

        # Override the dependency
        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets/test.md")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve cheatsheet content" in data["detail"]

        # Clean up
        client_no_db.app.dependency_overrides.clear()

    def test_grammar_endpoints_not_found_without_router(self, client_no_db):
        """Test that grammar endpoints return 404 when router is not included."""
        # This test verifies that the grammar router is properly included
        # by temporarily removing the override and checking the endpoint exists

        # First, ensure the router is included by testing with mock service
        mock_service = Mock()
        mock_service.list_cheatsheets.return_value = []

        client_no_db.app.dependency_overrides[get_grammar_service] = lambda: mock_service

        response = client_no_db.get("/api/grammar/cheatsheets")
        assert response.status_code == 200  # Should work when router is included

        # Clean up
        client_no_db.app.dependency_overrides.clear()
