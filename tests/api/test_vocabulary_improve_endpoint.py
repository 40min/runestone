from runestone.api.schemas import ImprovementMode, VocabularyImproveRequest, VocabularyImproveResponse


async def test_improve_vocabulary_success(client_with_mock_vocabulary_service):
    """Test successful vocabulary improvement endpoint with ALL_FIELDS mode."""
    client, mock_service = client_with_mock_vocabulary_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation="an apple", example_phrase="Jag äter ett äpple varje dag.", extra_info="en-word, noun"
    )
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "all_fields"}

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] == "an apple"
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] == "en-word, noun"

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.ALL_FIELDS


async def test_improve_vocabulary_example_only(client_with_mock_vocabulary_service):
    """Test vocabulary improvement endpoint with EXAMPLE_ONLY mode."""
    client, mock_service = client_with_mock_vocabulary_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase="Jag äter ett äpple varje dag.", extra_info=None
    )
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "example_only"}

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] is None

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.EXAMPLE_ONLY


async def test_improve_vocabulary_extra_info_only(client_with_mock_vocabulary_service):
    """Test vocabulary improvement endpoint with EXTRA_INFO_ONLY mode."""
    client, mock_service = client_with_mock_vocabulary_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase=None, extra_info="en-word, noun, base form: äpple"
    )
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "extra_info_only"}

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] is None
    assert response_data["extra_info"] == "en-word, noun, base form: äpple"

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.EXTRA_INFO_ONLY


async def test_improve_vocabulary_service_error(client_with_mock_vocabulary_service):
    """Test vocabulary improvement endpoint with service error."""
    client, mock_service = client_with_mock_vocabulary_service

    # Mock service to raise exception
    mock_service.improve_item.side_effect = Exception("LLM service error")

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "all_fields"}

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify error response
    assert response.status_code == 500
    response_data = response.json()
    assert "detail" in response_data
    assert response_data["detail"] == "An internal error occurred while improving vocabulary."


async def test_improve_vocabulary_invalid_request(client_with_mock_vocabulary_service):
    """Test vocabulary improvement endpoint with invalid request."""
    client, mock_service = client_with_mock_vocabulary_service

    # Test with missing required field
    request_data = {
        "mode": "all_fields"
        # Missing word_phrase
    }

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify validation error
    assert response.status_code == 422
    response_data = response.json()
    assert "detail" in response_data


async def test_improve_vocabulary_empty_response(client_with_mock_vocabulary_service):
    """Test vocabulary improvement endpoint with empty response."""
    client, mock_service = client_with_mock_vocabulary_service

    # Mock service response with empty fields
    mock_response = VocabularyImproveResponse(translation=None, example_phrase="", extra_info=None)
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "all_fields"}

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == ""
    assert response_data["extra_info"] is None


async def test_improve_vocabulary_default_mode(client_with_mock_vocabulary_service):
    """Test vocabulary improvement endpoint with default mode (EXAMPLE_ONLY)."""
    client, mock_service = client_with_mock_vocabulary_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase="Jag äter ett äpple varje dag.", extra_info=None
    )
    mock_service.improve_item.return_value = mock_response

    # Test request without mode (should default to EXAMPLE_ONLY)
    request_data = {"word_phrase": "ett äpple"}

    response = await client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] is None

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.EXAMPLE_ONLY
