"""WSGI entry-point for the web application"""

import os

import sentry_sdk

from companion_memory.app import create_app
from companion_memory.llm_client import LLMLClient
from companion_memory.storage import DynamoLogStore

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN', ''),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
)

# Production WSGI uses DynamoDB and LLM by default
log_store = DynamoLogStore()
llm_client = LLMLClient()
application = create_app(log_store=log_store, llm=llm_client)
