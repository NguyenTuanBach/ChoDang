# syntax=docker/dockerfile:1
# Agent image. Build từ thư mục agent/:  docker build -t vin15/agent:local ./agent
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir=/wheelhouse .

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=bind,from=builder,source=/wheelhouse,target=/wheelhouse \
    pip install --no-cache-dir --no-index --find-links=/wheelhouse 'vin15-agent'

COPY prompts ./prompts

RUN groupadd --gid 10001 vin15 \
    && useradd --uid 10001 --gid vin15 --create-home --shell /usr/sbin/nologin vin15

USER vin15

EXPOSE 8100

CMD ["vin15-agent-api"]
