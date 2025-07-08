"""WSGI entry-point for the web application"""

from companion_memory.app import create_app  # pragma: no cover

application = create_app()  # pragma: no cover
