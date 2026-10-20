FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.crt,mode=0444 \
    if [ -f /tmp/build-ca.crt ]; then export NODE_EXTRA_CA_CERTS=/tmp/build-ca.crt; fi; npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.crt,mode=0444 \
    if [ -f /tmp/build-ca.crt ]; then export SSL_CERT_FILE=/tmp/build-ca.crt; fi; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::https::CaInfo="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}" update -o APT::Update::Error-Mode=any \
    && apt-get -o Acquire::https::CaInfo="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}" install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 pulse && useradd --uid 10001 --gid pulse --create-home pulse
WORKDIR /app
COPY requirements.lock ./
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.crt,mode=0444 \
    if [ -f /tmp/build-ca.crt ]; then export PIP_CERT=/tmp/build-ca.crt; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.lock
COPY --chown=pulse:pulse backend/ ./backend/
COPY --chown=pulse:pulse scripts/ ./scripts/
COPY --chown=pulse:pulse docs/ ./docs/
COPY --from=frontend --chown=pulse:pulse /build/dist ./frontend/dist
RUN mkdir -p /app/data && chown -R pulse:pulse /app/data
USER pulse
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log"]
