"""
Tests for vocabulary API endpoints.

This module contains tests for the vocabulary API.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import os

from runestone.api.main import app
from runestone.db.database import Base, get_db


class TestVocabularyAPI:
    """Test cases for vocabulary API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client with file-based database."""
        # Use a temporary database file for testing
        test_db_url = "sqlite:///./test_vocabulary.db"

        # Override the database dependency for testing
        def override_get_db():
            engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=engine)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        yield client
        app.dependency_overrides.clear()

        # Clean up the test database file
        if os.path.exists("./test_vocabulary.db"):
            os.remove("./test_vocabulary.db")

    def test_save_vocabulary_success(self, client):
        """Test successful vocabulary saving."""
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag."
                },
                {
                    "word_phrase": "en banan",
                    "translation": "a banana",
                    "example_phrase": None
                }
            ]
        }

        response = client.post("/api/vocabulary", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Vocabulary saved successfully"

    def test_save_vocabulary_duplicate(self, client):
        """Test saving vocabulary with duplicates."""
        # First save
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag."
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Second save with same word_phrase
        payload2 = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Ett äpple är rött."
                }
            ]
        }
        response = client.post("/api/vocabulary", json=payload2)

        assert response.status_code == 200

        # Check that only one entry exists
        response = client.get("/api/vocabulary")
        data = response.json()
        assert len(data) == 1
        assert data[0]["word_phrase"] == "ett äpple"
        assert data[0]["example_phrase"] == "Jag äter ett äpple varje dag."

    def test_get_vocabulary_empty(self, client):
        """Test getting vocabulary when database is empty."""
        response = client.get("/api/vocabulary")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_vocabulary_with_data(self, client):
        """Test getting vocabulary with data."""
        # Save some data first
        payload = {
            "items": [
                {
                    "word_phrase": "ett äpple",
                    "translation": "an apple",
                    "example_phrase": "Jag äter ett äpple varje dag."
                }
            ]
        }
        client.post("/api/vocabulary", json=payload)

        # Get the data
        response = client.get("/api/vocabulary")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        vocab = data[0]
        assert vocab["word_phrase"] == "ett äpple"
        assert vocab["translation"] == "an apple"
        assert vocab["example_phrase"] == "Jag äter ett äpple varje dag."
        assert vocab["user_id"] == 1
        assert "id" in vocab
        assert "created_at" in vocab
        assert "updated_at" in vocab