FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
COPY requirements.txt requirements-validation.txt /tmp/
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export PIP_CERT=/run/proxy-ca.pem; fi; \
    pip install --no-cache-dir -r /tmp/requirements-validation.txt
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
