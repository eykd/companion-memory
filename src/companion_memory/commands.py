"""Command handlers for CLI operations."""

import click


def run_scheduler() -> None:
    """Run the companion scheduler."""
    click.echo('Starting companion scheduler...')


def run_web_server() -> None:
    """Run the web server."""
    from companion_memory.app import create_app

    app = create_app()
    click.echo('Starting web server...')
    app.run(host='127.0.0.1', port=5000, debug=True)
