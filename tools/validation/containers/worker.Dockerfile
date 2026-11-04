FROM python:3.12-slim
COPY requirements.txt requirements-validation.txt /tmp/
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export PIP_CERT=/run/proxy-ca.pem; fi; \
    pip install --no-cache-dir -r /tmp/requirements-validation.txt
