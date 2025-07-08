"""Command handlers for CLI operations."""

import click


def run_scheduler() -> None:
    """Run the companion scheduler."""
    click.echo('Starting companion scheduler...')
