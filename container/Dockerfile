FROM ghcr.io/astral-sh/uv:0.13.3 AS uv
FROM ubuntu:24.04
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG PYTHON_VERSION=3.12.15
ENV PYTHON_VERSION=${PYTHON_VERSION}
RUN uv python install "${PYTHON_VERSION}" \
    && uv venv --python "${PYTHON_VERSION}" /opt/opengris-scaler
COPY requirements-worker-linux-amd64.lock /opt/worker-requirements.txt
RUN uv pip install --python /opt/opengris-scaler/bin/python -r /opt/worker-requirements.txt
COPY app/montecarlo /opt/mcqs/app/montecarlo
COPY container/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENV PATH="/opt/opengris-scaler/bin:${PATH}" PYTHONPATH=/opt/mcqs/app
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
