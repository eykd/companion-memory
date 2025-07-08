"""CLI interface for companion-scheduler."""

import click

from companion_memory.commands import run_scheduler, run_web_server


@click.group()
def cli() -> None:
    """Comem - Work activity tracking and summarization."""


@cli.command()
def scheduler() -> None:
    """Run the companion scheduler."""
    run_scheduler()


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind the server to')
@click.option('--port', default=5000, help='Port to bind the server to')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def web(host: str, port: int, debug: bool) -> None:  # noqa: FBT001
    """Run the web server."""
    run_web_server(host=host, port=port, debug=debug)
