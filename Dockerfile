# ONEXUS — operating system for agents
#
# Builds a single container that runs the kernel, the API server, and the
# Aurora dashboard. Health probe: GET /api/system/health. The catalog at
# /opt/onexus/catalog is rebuilt nightly by the GitHub Actions cron and
# baked into a new image.

FROM python:3.14-slim AS base

# System deps for sandboxed code execution + LLM tools.
# Node + bash give the workshop runtime real shells; git lets the catalog
# refresh pull from the onexus-agents repo.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential \
        nodejs npm bash tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/onexus

# Copy project files
COPY pyproject.toml README.md ./
COPY nexus ./nexus

# Install the Python package + its runtime extras
RUN pip install --no-cache-dir --upgrade pip wheel \
 && pip install --no-cache-dir ".[llm,api,messaging]"

# Stage 2 — bake the agent catalog into /opt/onexus/catalog so the API
# can run completely offline if no shared volume is provided. This is
# rebuilt nightly by the workflow.
ARG CATALOG_REF=main
RUN git clone --depth 1 --branch ${CATALOG_REF} \
        https://github.com/AllStreets/ONEXUS-Agents.git \
        /opt/onexus/catalog \
 || (echo "catalog clone failed — continuing without baked catalog" && mkdir -p /opt/onexus/catalog)

ENV NEXUS_AGENTS_CATALOG=/opt/onexus/catalog \
    NEXUS_DATA_DIR=/data \
    PORT=8000

# Run as an unprivileged user. The workshop runtime spawns subprocesses; a
# sandbox escape under a non-root uid cannot touch the rest of the image or
# the host. The data volume and baked catalog are owned by this user.
RUN useradd --system --uid 10001 --create-home --home-dir /home/onexus onexus \
 && mkdir -p /data \
 && chown -R onexus:onexus /opt/onexus /data
USER onexus

VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/system/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "onexus serve --host 0.0.0.0 --port ${PORT}"]
