"""WSGI entry-point for the web application"""

import os

import sentry_sdk

from companion_memory.app import create_app

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN', ''),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
)


application = create_app()
