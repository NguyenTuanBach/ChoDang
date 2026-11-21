# syntax=docker/dockerfile:1
# Backend image. Build từ thư mục be/:  docker build -t vin15/backend:local ./be
# BE KHÔNG import code của agent: hai service chỉ nói chuyện với nhau qua HTTP (xem be/README.md).
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
    pip install --no-cache-dir --no-index --find-links=/wheelhouse 'vin15-be'

RUN groupadd --gid 10001 vin15 \
    && useradd --uid 10001 --gid vin15 --create-home --shell /usr/sbin/nologin vin15

USER vin15

EXPOSE 8000

CMD ["python", "-m", "vin15"]
