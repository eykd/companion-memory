#!/bin/sh
set -e
set -x

DIR="${GITHUB_WORKSPACE:-$PWD}"
cd $DIR

set -a # automatically export all variables
. $DIR/.env.test
set +a

uv run ruff check
poetry run pytest --cov-fail-under=100
