"""Tests for Flask web application."""

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from companion_memory.app import create_app

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient


@pytest.fixture
def client() -> Generator['FlaskClient', None, None]:
    """Create a test client for the Flask app."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_root_url_returns_200(client: 'FlaskClient') -> None:
    """Test that root URL returns 200 status code."""
    response = client.get('/')
    assert response.status_code == 200
