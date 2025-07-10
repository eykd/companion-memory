"""WSGI entry-point for the web application"""

import logging
import os
import sys

import sentry_sdk

from companion_memory.app import create_app
from companion_memory.llm_client import LLMLClient
from companion_memory.storage import DynamoLogStore

# Configure application logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

# Ensure scheduler logger is set to INFO level
scheduler_logger = logging.getLogger('companion_memory.scheduler')
scheduler_logger.setLevel(logging.INFO)

# Also ensure Flask app logger is configured
app_logger = logging.getLogger('companion_memory.app')
app_logger.setLevel(logging.INFO)

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN', ''),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
)

# Production WSGI uses DynamoDB and LLM by default
log_store = DynamoLogStore()
llm_client = LLMLClient()

# Log application startup
logging.info('Starting companion-memory application with production configuration')

application = create_app(log_store=log_store, llm=llm_client)

logging.info('Companion-memory application created successfully')
