"""Concrete implementation of LLMClient using the llm library."""

import llm


class LLMLClient:
    """Concrete implementation of LLMClient using the llm library."""

    def __init__(self, model_name: str = 'claude-3-5-haiku') -> None:
        """Initialize the LLM client with a specific model.

        Args:
            model_name: Name of the LLM model to use. Defaults to Claude 3.5 Haiku.

        """
        self._model_name = model_name

    def complete(self, prompt: str) -> str:
        """Generate completion for given prompt.

        Args:
            prompt: The input prompt for the LLM

        Returns:
            Generated completion text

        """
        model = llm.get_model(self._model_name)
        response = model.prompt(prompt)
        return response.text()
