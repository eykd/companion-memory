"""Custom exceptions for the companion-memory application."""


class CompanionMemoryError(Exception):
    """Base exception class for all companion-memory errors."""


class LLMConfigurationError(CompanionMemoryError):
    """Exception raised when there's an error configuring the LLM client."""


class LLMGenerationError(CompanionMemoryError):
    """Exception raised when there's an error generating LLM completions."""
