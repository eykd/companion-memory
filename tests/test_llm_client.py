"""Tests for LLM client implementation."""

from unittest.mock import MagicMock, patch

import pytest
from companion_memory.llm_client import LLMLClient


def test_llm_client_complete_generates_response_with_claude_haiku() -> None:
    """Test that LLMLClient.complete() generates response using Claude 3.5 Haiku."""
    # Mock the llm module
    mock_llm = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = 'This is a test response from Claude 3.5 Haiku'

    mock_model.prompt.return_value = mock_response
    mock_llm.get_model.return_value = mock_model

    with patch('companion_memory.llm_client.llm', mock_llm):
        client = LLMLClient()
        result = client.complete('Test prompt')

        # Verify model was requested correctly
        mock_llm.get_model.assert_called_once_with('claude-3-5-haiku')

        # Verify prompt was sent
        mock_model.prompt.assert_called_once_with('Test prompt')

        # Verify response was processed
        mock_response.text.assert_called_once()
        assert result == 'This is a test response from Claude 3.5 Haiku'


def test_llm_client_complete_handles_llm_errors() -> None:
    """Test that LLMLClient.complete() handles LLM errors gracefully."""
    # Mock the llm module to raise an exception
    mock_llm = MagicMock()
    mock_llm.get_model.side_effect = Exception('Model not found')

    with patch('companion_memory.llm_client.llm', mock_llm):
        client = LLMLClient()

        with pytest.raises(Exception, match='Model not found'):
            client.complete('Test prompt')


def test_llm_client_complete_with_custom_model() -> None:
    """Test that LLMLClient.complete() can use a custom model."""
    # Mock the llm module
    mock_llm = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = 'Custom model response'

    mock_model.prompt.return_value = mock_response
    mock_llm.get_model.return_value = mock_model

    with patch('companion_memory.llm_client.llm', mock_llm):
        client = LLMLClient(model_name='gpt-4')
        result = client.complete('Test prompt')

        # Verify custom model was requested
        mock_llm.get_model.assert_called_once_with('gpt-4')

        # Verify prompt was sent
        mock_model.prompt.assert_called_once_with('Test prompt')

        # Verify response was processed
        assert result == 'Custom model response'
