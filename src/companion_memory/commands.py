"""Command handlers for CLI operations."""

import click


def run_scheduler() -> None:
    """Run the companion scheduler."""
    click.echo('Starting companion scheduler...')


def run_web_server(host: str = '127.0.0.1', port: int = 5000, debug: bool = True) -> None:  # noqa: FBT001, FBT002
    """Run the web server.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        debug: Enable debug mode

    """
    from companion_memory.app import create_app

    app = create_app()
    click.echo(f'Starting web server on {host}:{port} (debug={debug})...')
    app.run(host=host, port=port, debug=debug)
