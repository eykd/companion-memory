# Conventions for the companion-memory project

## When asked to create new conventions

When asked to create a new convention (`CLAUDE.md`), add a second-level
heading section to this document, `CLAUDE.md`.

- Name the new convention heading with a short, descriptive title.
- Use the first line of the section to elaborate on the "When..." of the heading.
- Use bullet points to organize further details for the convention.
- Use full imperative sentences.
- Keep new conventions short and to the point.
- Use short examples for complex conventions.

## Python code style and quality

When writing or editing Python code (`*.py`), follow these quality standards:

- Use PEP8 style with CamelCase for class names and snake_case for variables/functions.
- Include type annotations for all functions, methods, and complex structures.
- Add Google Style docstrings to all packages, modules, functions, classes, and methods.
- Run code quality tools:
  - Format: `uv run ruff format`
  - Lint: `uv run ruff check --fix`
  - Type check: `uv run mypy src tests`

## Hexagonal Architecture

When designing application components (`*.py`), use hexagonal architecture to separate business logic from external concerns:

- Place core business logic at the center, free from direct I/O dependencies.
- Favor a functional style for core business logic.
- Define interfaces (ports) for all external interactions.
- Implement concrete adapters for external systems.
- Inject dependencies through constructor parameters or factory functions.
- When testing, use test doubles (fakes, stubs, mocks) for external dependencies.
- Test adapters separately with integration tests.

## Testing

When writing Python code (`*.py`), follow these testing practices:

- Write tests first for each change using pytest.
- Organize tests in a dedicated `tests/` folder in the project root.
- Name test files by package and module, omitting the root `companion_memory` package name.
  - Example test file name: `tests/test_config_discovery.py` tests code in `src/companion_memory/config/discovery.py`
- Use descriptive names for test functions and methods.
- Group related tests in test classes.
- Use fixtures for complex setup.
- Maintain 100% test coverage for code under `src/`.
- When writing tests, move common fixtures to `tests/conftest.py`.
- Run tests with `./scripts/runtests.sh` (which accepts normal `pytest` arguments and flags).
  - Example: `./scripts/runtests.sh tests/test_config_discovery.py`

## Variable naming

When naming variables in Python code, follow these naming practices:

- Use concise but descriptive variable names that clearly indicate purpose.
- Avoid single-character variable names except in the simplest comprehensions and generator expressions.
- Follow snake_case for all variable names.
- Choose names that reveal intent and make code self-documenting.
- Use plural forms for collections (lists, sets, dictionaries) and singular forms for individual items.
- Prefix boolean variables with verbs like `is_`, `has_`, or `should_`.

## Exception style

When raising exceptions in Python code, follow these practices:

- Do not raise generic exceptions like `Exception` or `RuntimeError`.
- Use a specific exception defined in `src/companion_memory/exceptions.py`.
- When raising a new exception from within an exception handler, always `raise NewError from old_exception`:
  Define a new specific exception in `src/companion_memory/exceptions.py` if none exists for your situation.
- Do not define `__init__` methods on custom exceptions.
- When raising exceptions with a string message, do not use variable substitution in the error message.
- Add extra context as further arguments to the exception instead of embedding variables in the message.
- Example:
  ```python
  # Bad
  try:
      ...
  except Exception:
      raise ValueError(f"Node with ID {node_id} not found")

  # Good
  try:
      ...
  except ValueError as exc:
      raise NodeNotFoundError("Node not found", node_id) from exc
  ```

## TYPE_CHECKING blocks

When using TYPE_CHECKING for import statements in Python code, follow these practices:

- Always add `# pragma: no cover` to the TYPE_CHECKING block to exclude it from coverage reports.
- Place all imports that are only needed for type checking inside this block.
- Example:
  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:  # pragma: no cover
      from some_module import SomeType
  ```


## TDD Commit Style

When following the Red/Green/Refactor loop:

* Use separate commits for red (failing test), green (minimal fix), and refactor (code improvement) stages.
* Each commit should be testable and revertible on its own.
* ALWAYS make a commit once the entire test suite is passing.
* Use descriptive conventional commit messages:

  * `test: add failing test for filter with __contains`
  * `feat: implement __contains lookup for filters`
  * `refactor: isolate filter logic into LookupEvaluator`

## Test Suite Quality Gates

When making any changes to the codebase:

* The complete test suite MUST always pass after GREEN and REFACTOR steps, or any other changes other than RED steps (where a test is expected to fail).
* Code quality tools MUST run clean after each stage (RED, GREEN, and REFACTOR):
  * Format: `uv run ruff format`
  * Lint: `uv run ruff check --fix`
* NEVER commit code that breaks existing tests unless it's part of an intentional RED step.
* Run the full test suite with `./scripts/runtests.sh` to verify all tests pass before committing GREEN or REFACTOR changes.

## 100% Test Coverage Maintenance

When writing or modifying Python code (`*.py`), maintain 100% test coverage:

- NEVER commit code that reduces test coverage below 100%.
- Add tests for all new code paths before committing.
- Use `# pragma: no cover` sparingly and only for:
  - Protocol abstract methods (`...` in Protocol classes)
  - TYPE_CHECKING import blocks
  - Defensive code that should never execute in normal operation
- When adding `# pragma: no cover`, include a comment explaining why coverage exclusion is justified.
- Run `./scripts/runtests.sh --cov-report=term-missing` to verify 100% coverage before committing.
- If coverage drops below 100%, either add tests or add appropriate pragma comments with justification.
