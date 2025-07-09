"""Tests for LLM client implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from companion_memory.exceptions import LLMConfigurationError, LLMGenerationError
from companion_memory.llm_client import LLMLClient


@pytest.fixture
def mock_llm_module() -> MagicMock:
    """Create a mock llm module with proper exception class."""

    # Create a proper exception class for mocking
    class MockUnknownModelError(Exception):
        pass

    mock_llm = MagicMock()
    mock_llm.UnknownModelError = MockUnknownModelError
    return mock_llm


def test_llm_client_complete_generates_response_with_claude_haiku(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient.complete() generates response using Claude 3.5 Haiku."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = 'This is a test response from Claude 3.5 Haiku'

    mock_model.prompt.return_value = mock_response
    mock_llm_module.get_model.return_value = mock_model

    with patch('companion_memory.llm_client.llm', mock_llm_module):
        client = LLMLClient()
        result = client.complete('Test prompt')

        # Verify model was requested correctly
        mock_llm_module.get_model.assert_called_once_with('anthropic/claude-3-haiku-20240307')

        # Verify prompt was sent
        mock_model.prompt.assert_called_once_with('Test prompt')

        # Verify response was processed
        mock_response.text.assert_called_once()
        assert result == 'This is a test response from Claude 3.5 Haiku'


def test_llm_client_complete_handles_unknown_model_error(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient.complete() handles UnknownModelError gracefully."""
    mock_llm_module.get_model.side_effect = mock_llm_module.UnknownModelError('Model not found')

    with patch('companion_memory.llm_client.llm', mock_llm_module):
        client = LLMLClient()

        with pytest.raises(LLMConfigurationError, match='Unknown model: anthropic/claude-3-haiku-20240307'):
            client.complete('Test prompt')


def test_llm_client_complete_handles_model_configuration_error(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient.complete() handles general model configuration errors."""
    mock_llm_module.get_model.side_effect = Exception('General error')

    with patch('companion_memory.llm_client.llm', mock_llm_module):
        client = LLMLClient()

        with pytest.raises(LLMConfigurationError, match='Error getting model anthropic/claude-3-haiku-20240307'):
            client.complete('Test prompt')


def test_llm_client_complete_handles_generation_error(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient.complete() handles generation errors gracefully."""
    mock_model = MagicMock()
    mock_model.prompt.side_effect = Exception('Generation failed')
    mock_llm_module.get_model.return_value = mock_model

    with patch('companion_memory.llm_client.llm', mock_llm_module):
        client = LLMLClient()

        with pytest.raises(LLMGenerationError, match='Error generating completion'):
            client.complete('Test prompt')


def test_llm_client_complete_with_custom_model(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient.complete() can use a custom model."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = 'Custom model response'

    mock_model.prompt.return_value = mock_response
    mock_llm_module.get_model.return_value = mock_model

    with patch('companion_memory.llm_client.llm', mock_llm_module):
        client = LLMLClient(model_name='gpt-4')
        result = client.complete('Test prompt')

        # Verify custom model was requested
        mock_llm_module.get_model.assert_called_once_with('gpt-4')

        # Verify prompt was sent
        mock_model.prompt.assert_called_once_with('Test prompt')

        # Verify response was processed
        assert result == 'Custom model response'


def test_llm_client_uses_environment_variable_for_model(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient uses LLM_MODEL_NAME environment variable."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = 'Environment model response'

    mock_model.prompt.return_value = mock_response
    mock_llm_module.get_model.return_value = mock_model

    with (
        patch('companion_memory.llm_client.llm', mock_llm_module),
        patch.dict(os.environ, {'LLM_MODEL_NAME': 'gpt-3.5-turbo'}),
    ):
        client = LLMLClient()
        result = client.complete('Test prompt')

        # Verify environment model was requested
        mock_llm_module.get_model.assert_called_once_with('gpt-3.5-turbo')
        assert result == 'Environment model response'


def test_llm_client_constructor_overrides_environment_variable(mock_llm_module: MagicMock) -> None:
    """Test that LLMLClient constructor parameter overrides environment variable."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = 'Constructor model response'

    mock_model.prompt.return_value = mock_response
    mock_llm_module.get_model.return_value = mock_model

    with (
        patch('companion_memory.llm_client.llm', mock_llm_module),
        patch.dict(os.environ, {'LLM_MODEL_NAME': 'gpt-3.5-turbo'}),
    ):
        client = LLMLClient(model_name='claude-3-sonnet')
        result = client.complete('Test prompt')

        # Verify constructor model was requested (not environment)
        mock_llm_module.get_model.assert_called_once_with('claude-3-sonnet')
        assert result == 'Constructor model response'
