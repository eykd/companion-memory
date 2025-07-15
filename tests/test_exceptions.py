"""Tests for custom exception classes."""

import pytest

from companion_memory.exceptions import CompanionMemoryError, LLMConfigurationError, LLMGenerationError

pytestmark = pytest.mark.block_network


def test_companion_memory_error_is_base_exception() -> None:
    """Test that CompanionMemoryError is the base exception class."""
    assert issubclass(CompanionMemoryError, Exception)


def test_llm_configuration_error_inherits_from_base() -> None:
    """Test that LLMConfigurationError inherits from CompanionMemoryError."""
    assert issubclass(LLMConfigurationError, CompanionMemoryError)
    assert issubclass(LLMConfigurationError, Exception)


def test_llm_generation_error_inherits_from_base() -> None:
    """Test that LLMGenerationError inherits from CompanionMemoryError."""
    assert issubclass(LLMGenerationError, CompanionMemoryError)
    assert issubclass(LLMGenerationError, Exception)


def test_llm_configuration_error_can_be_raised_with_message() -> None:
    """Test that LLMConfigurationError can be raised with a message."""
    with pytest.raises(LLMConfigurationError, match='Test configuration error'):
        raise LLMConfigurationError('Test configuration error')


def test_llm_generation_error_can_be_raised_with_message() -> None:
    """Test that LLMGenerationError can be raised with a message."""
    with pytest.raises(LLMGenerationError, match='Test generation error'):
        raise LLMGenerationError('Test generation error')


def test_exceptions_can_be_caught_as_base_exception() -> None:
    """Test that specific exceptions can be caught as CompanionMemoryError."""
    with pytest.raises(CompanionMemoryError):
        raise LLMConfigurationError('Test error')

    with pytest.raises(CompanionMemoryError):
        raise LLMGenerationError('Test error')
