"""Concrete implementation of LLMClient using the llm library."""

import logging
import os

import llm

from companion_memory.exceptions import LLMConfigurationError, LLMGenerationError

logger = logging.getLogger(__name__)


class LLMLClient:
    """Concrete implementation of LLMClient using the llm library."""

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize the LLM client with a specific model.

        Args:
            model_name: Name of the LLM model to use. If None, uses environment variable
                       LLM_MODEL_NAME or defaults to Claude 3.5 Haiku.

        """
        self._model_name = model_name or os.getenv('LLM_MODEL_NAME', 'claude-3-5-haiku')
        logger.info('Initializing LLM client with model: %s', self._model_name)

    def complete(self, prompt: str) -> str:
        """Generate completion for given prompt.

        Args:
            prompt: The input prompt for the LLM

        Returns:
            Generated completion text

        Raises:
            LLMConfigurationError: If the model is not found or not properly configured
            LLMGenerationError: If there's an error generating the completion

        """
        try:
            logger.debug('Getting model: %s', self._model_name)
            model = llm.get_model(self._model_name)
        except llm.UnknownModelError as exc:
            logger.exception('Unknown model: %s', self._model_name)
            error_msg = f'Unknown model: {self._model_name}'
            raise LLMConfigurationError(error_msg) from exc
        except Exception as exc:
            logger.exception('Error getting model %s', self._model_name)
            error_msg = f'Error getting model {self._model_name}'
            raise LLMConfigurationError(error_msg) from exc

        try:
            logger.debug('Generating completion for prompt: %s...', prompt[:100])
            response = model.prompt(prompt)
            result = response.text()
            logger.debug('Generated completion: %s...', result[:100])
        except Exception as exc:
            logger.exception('Error generating completion')
            raise LLMGenerationError('Error generating completion') from exc
        else:
            return result
