"""CLI interface for companion-scheduler."""

import click


@click.group()
def cli() -> None:
    """companion-scheduler - Work activity tracking and summarization."""


@cli.command()
def run() -> None:
    """Run the companion scheduler."""
    click.echo('Starting companion scheduler...')
