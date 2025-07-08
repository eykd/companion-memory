ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir -p /code

WORKDIR /code

RUN python -m pip install uv
COPY . /code
RUN python -m uv sync

EXPOSE 8000

CMD ["python", "-m", "uv", "run", "gunicorn", "--bind", ":8000", "--workers", "2", "companion_memory.wsgi"]
