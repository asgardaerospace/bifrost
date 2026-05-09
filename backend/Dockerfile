# syntax=docker/dockerfile:1.6
#
# Bifrost backend — production multi-stage build.
#
# Stage 1 (builder): install deps into a virtualenv we copy forward — keeps
# the runtime image free of build toolchains.
# Stage 2 (runtime): minimal runtime, non-root user, healthcheck, deterministic
# startup via the entrypoint.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app \
    BIFROST_ENV=production

# Non-root runtime user.
RUN groupadd --system --gid 1001 bifrost \
 && useradd --system --uid 1001 --gid bifrost --home-dir /app --shell /usr/sbin/nologin bifrost \
 && mkdir -p /app /app/var \
 && chown -R bifrost:bifrost /app

# Bring the pre-built virtualenv from the builder.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=bifrost:bifrost alembic.ini ./alembic.ini
COPY --chown=bifrost:bifrost alembic ./alembic
COPY --chown=bifrost:bifrost app ./app
COPY --chown=bifrost:bifrost docker/entrypoint.sh /usr/local/bin/bifrost-entrypoint
RUN chmod +x /usr/local/bin/bifrost-entrypoint

USER bifrost
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; \
import os; \
url=os.environ.get('BIFROST_HEALTH_URL','http://127.0.0.1:8000/api/v1/health'); \
sys.exit(0) if urllib.request.urlopen(url, timeout=3).status==200 else sys.exit(1)" \
 || exit 1

ENTRYPOINT ["/usr/local/bin/bifrost-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
