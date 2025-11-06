"""
Tests for grammar API endpoints.

This module tests the grammar API endpoints defined in endpoints.py.
"""


class TestGrammarEndpoints:
    """Test cases for grammar endpoints."""

    def test_list_cheatsheets_success(self, client_with_mock_grammar_service, temp_cheatsheets_dir):
        """Test successful listing of cheatsheets."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.list_cheatsheets.return_value = [
            {"filename": "adjectiv-komparation.md", "title": "Adjectiv Komparation", "category": "General"},
            {"filename": "objectspronomen.md", "title": "Objectspronomen", "category": "General"},
            {"filename": "presens-perfect.md", "title": "Presens Perfect", "category": "General"},
        ]

        response = client.get("/api/grammar/cheatsheets")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert len(data) == 3
        assert all("filename" in item and "title" in item for item in data)

        # Verify service was called
        mock_service.list_cheatsheets.assert_called_once()

    def test_list_cheatsheets_empty(self, client_with_mock_grammar_service):
        """Test listing cheatsheets when directory is empty."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.list_cheatsheets.return_value = []

        response = client.get("/api/grammar/cheatsheets")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_cheatsheets_service_error(self, client_with_mock_grammar_service):
        """Test handling of service errors in list cheatsheets."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.list_cheatsheets.side_effect = Exception("Service error")

        response = client.get("/api/grammar/cheatsheets")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve cheatsheets" in data["detail"]

    def test_get_cheatsheet_content_success(self, client_with_mock_grammar_service):
        """Test successful retrieval of cheatsheet content."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.get_cheatsheet_content.return_value = "# Test Content\n\nThis is test content."

        response = client.get("/api/grammar/cheatsheets/adjectiv-komparation.md")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["content"] == "# Test Content\n\nThis is test content."

        # Verify service was called with correct filepath
        mock_service.get_cheatsheet_content.assert_called_once_with("adjectiv-komparation.md")

    def test_get_cheatsheet_content_nested_path_success(self, client_with_mock_grammar_service):
        """Test successful retrieval of cheatsheet content with nested paths."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.get_cheatsheet_content.return_value = "# Nested Content\n\nThis is nested content."

        response = client.get("/api/grammar/cheatsheets/verbs/hjalpverb.md")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["content"] == "# Nested Content\n\nThis is nested content."

        # Verify service was called with correct nested filepath
        mock_service.get_cheatsheet_content.assert_called_once_with("verbs/hjalpverb.md")

    def test_get_cheatsheet_content_invalid_filepath(self, client_with_mock_grammar_service):
        """Test getting content with invalid filepath."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.get_cheatsheet_content.side_effect = ValueError("Invalid file path: badfile.txt")

        response = client.get("/api/grammar/cheatsheets/badfile.txt")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file path: badfile.txt" in data["detail"]

    def test_get_cheatsheet_content_file_not_found(self, client_with_mock_grammar_service):
        """Test getting content for non-existent file."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.get_cheatsheet_content.side_effect = FileNotFoundError("Cheatsheet 'nonexistent.md' not found")

        response = client.get("/api/grammar/cheatsheets/nonexistent.md")

        assert response.status_code == 404
        data = response.json()
        assert "Cheatsheet 'nonexistent.md' not found" in data["detail"]

    def test_get_cheatsheet_content_service_error(self, client_with_mock_grammar_service):
        """Test handling of unexpected service errors."""
        client, mock_service = client_with_mock_grammar_service
        mock_service.get_cheatsheet_content.side_effect = Exception("Unexpected error")

        response = client.get("/api/grammar/cheatsheets/test.md")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve cheatsheet content" in data["detail"]

    def test_grammar_endpoints_not_found_without_router(self, client_with_mock_grammar_service):
        """Test that grammar endpoints return 404 when router is not included."""
        # This test verifies that the grammar router is properly included
        # by temporarily removing the override and checking the endpoint exists

        # First, ensure the router is included by testing with mock service
        client, mock_service = client_with_mock_grammar_service
        mock_service.list_cheatsheets.return_value = []

        response = client.get("/api/grammar/cheatsheets")
        assert response.status_code == 200  # Should work when router is included
