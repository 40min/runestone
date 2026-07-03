"""
Tests for GET /api/vocabulary/distribution endpoint.

Covers authentication, bucket correctness, in_learn filtering,
user isolation, and response shape invariants.
"""

import pytest

from runestone.constants import VOCABULARY_PRIORITY_LABELS
from runestone.db.models import Vocabulary as VocabularyModel


class TestVocabularyDistributionEndpoint:
    """Tests for the vocabulary distribution endpoint."""

    pytestmark = pytest.mark.anyio

    async def test_unauthenticated_returns_403(self, client_no_db):
        """Unauthenticated request is rejected with 403."""
        response = await client_no_db.get("/api/vocabulary/distribution")
        assert response.status_code == 403

    async def test_empty_vocab_returns_all_zero_buckets(self, client):
        """Authenticated user with no vocabulary gets all-zero buckets."""
        response = await client.get("/api/vocabulary/distribution")

        assert response.status_code == 200
        data = response.json()

        assert len(data["priority_distribution"]) == 10
        assert all(item["count"] == 0 for item in data["priority_distribution"])
        assert len(data["learned_times_distribution"]) == 4
        assert all(item["count"] == 0 for item in data["learned_times_distribution"])

    async def test_in_learn_false_excluded(self, client):
        """Words added with in_learn=false do not appear in any distribution bucket."""
        payload = {
            "items": [
                {"word_phrase": "ord1", "translation": "word1", "in_learn": False, "priority_learn": 0},
                {"word_phrase": "ord2", "translation": "word2", "in_learn": False, "priority_learn": 9},
            ],
            "enrich": False,
        }
        post_resp = await client.post("/api/vocabulary", json=payload)
        assert post_resp.status_code == 200

        response = await client.get("/api/vocabulary/distribution")
        assert response.status_code == 200
        data = response.json()

        assert all(item["count"] == 0 for item in data["priority_distribution"])
        assert all(item["count"] == 0 for item in data["learned_times_distribution"])

    async def test_priority_distribution_counts(self, client):
        """Words at priorities 0, 3, 9 each land in their respective buckets."""
        payload = {
            "items": [
                {"word_phrase": "p0", "translation": "t", "in_learn": True, "priority_learn": 0},
                {"word_phrase": "p3", "translation": "t", "in_learn": True, "priority_learn": 3},
                {"word_phrase": "p9", "translation": "t", "in_learn": True, "priority_learn": 9},
            ],
            "enrich": False,
        }
        await client.post("/api/vocabulary", json=payload)

        response = await client.get("/api/vocabulary/distribution")
        assert response.status_code == 200
        data = response.json()

        dist = {item["priority"]: item["count"] for item in data["priority_distribution"]}
        assert dist[0] == 1
        assert dist[3] == 1
        assert dist[9] == 1
        # All other priorities should be 0
        for p in range(10):
            if p not in (0, 3, 9):
                assert dist[p] == 0

    async def test_learned_times_bucket_counts(self, client):
        """Words at boundary learned_times values land in the correct bucket."""
        # Insert rows directly so we can control learned_times
        client.db.add(
            VocabularyModel(
                user_id=client.user.id,
                word_phrase="never",
                translation="t",
                in_learn=True,
                learned_times=0,
                priority_learn=9,
            )
        )
        client.db.add(
            VocabularyModel(
                user_id=client.user.id,
                word_phrase="few",
                translation="t",
                in_learn=True,
                learned_times=5,
                priority_learn=9,
            )
        )
        client.db.add(
            VocabularyModel(
                user_id=client.user.id,
                word_phrase="mid",
                translation="t",
                in_learn=True,
                learned_times=20,
                priority_learn=9,
            )
        )
        client.db.add(
            VocabularyModel(
                user_id=client.user.id,
                word_phrase="many",
                translation="t",
                in_learn=True,
                learned_times=50,
                priority_learn=9,
            )
        )
        await client.db.commit()

        response = await client.get("/api/vocabulary/distribution")
        assert response.status_code == 200
        data = response.json()

        lt_dist = {item["label"]: item["count"] for item in data["learned_times_distribution"]}
        assert lt_dist["Never"] == 1
        assert lt_dist["1\u201310"] == 1
        assert lt_dist["11\u201330"] == 1
        assert lt_dist[">30"] == 1

    async def test_response_has_exactly_10_priority_items_in_order(self, client):
        """priority_distribution always has 10 items ordered 0–9."""
        response = await client.get("/api/vocabulary/distribution")
        assert response.status_code == 200
        data = response.json()

        assert len(data["priority_distribution"]) == 10
        priorities = [item["priority"] for item in data["priority_distribution"]]
        assert priorities == list(range(10))

    async def test_response_has_exactly_4_learned_times_items_in_order(self, client):
        """learned_times_distribution always has 4 items in the fixed label order."""
        response = await client.get("/api/vocabulary/distribution")
        assert response.status_code == 200
        data = response.json()

        labels = [item["label"] for item in data["learned_times_distribution"]]
        assert labels == ["Never", "1\u201310", "11\u201330", ">30"]

    async def test_labels_match_constants(self, client):
        """Each priority label in the response matches VOCABULARY_PRIORITY_LABELS."""
        response = await client.get("/api/vocabulary/distribution")
        assert response.status_code == 200
        data = response.json()

        for item in data["priority_distribution"]:
            assert item["label"] == VOCABULARY_PRIORITY_LABELS[item["priority"]]

    async def test_user_isolation(self, client_with_overrides, db_with_test_user):
        """Each user only sees their own vocabulary in the distribution."""
        import uuid

        from runestone.auth.dependencies import get_current_user
        from runestone.db.models import User

        async for client_a, _ in client_with_overrides():
            # Add 2 words for user A
            await client_a.post(
                "/api/vocabulary",
                json={
                    "items": [
                        {"word_phrase": "user-a-word1", "translation": "t", "in_learn": True, "priority_learn": 0},
                        {"word_phrase": "user-a-word2", "translation": "t", "in_learn": True, "priority_learn": 9},
                    ],
                    "enrich": False,
                },
            )

            # Verify user A sees their 2 words
            response_a = await client_a.get("/api/vocabulary/distribution")
            assert response_a.status_code == 200
            data_a = response_a.json()
            total_a = sum(item["count"] for item in data_a["priority_distribution"])
            assert total_a == 2

            # Create user B in the same DB session (no words)
            user_b = User(
                name="User B",
                email=f"user-b-{uuid.uuid4()}@example.com",
                hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
                timezone="UTC",
                pages_recognised_count=0,
                active=True,
            )
            client_a.db.add(user_b)
            await client_a.db.commit()

            # Temporarily switch the authenticated user to user B
            client_a.app.dependency_overrides[get_current_user] = lambda: user_b
            try:
                response_b = await client_a.get("/api/vocabulary/distribution")
                assert response_b.status_code == 200
                data_b = response_b.json()
                # User B has no words → all zeros
                assert all(item["count"] == 0 for item in data_b["priority_distribution"])
                assert all(item["count"] == 0 for item in data_b["learned_times_distribution"])
            finally:
                client_a.app.dependency_overrides.pop(get_current_user, None)
            break
