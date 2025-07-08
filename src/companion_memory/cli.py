"""CLI interface for companion-scheduler."""

import click

from companion_memory.commands import run_scheduler, run_web_server


@click.group()
def cli() -> None:
    """companion-scheduler - Work activity tracking and summarization."""


@cli.command()
def run() -> None:
    """Run the companion scheduler."""
    run_scheduler()


@cli.command()
def web() -> None:
    """Run the web server."""
    run_web_server()
