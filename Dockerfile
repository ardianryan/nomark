FROM python:3.11-slim-bookworm

ARG VERSION=development
ARG REVISION=unknown
LABEL org.opencontainers.image.title="NoMark" \
      org.opencontainers.image.source="https://gitlab.com/ardianryan/nomark" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    WATERMARKS_MAX_INPUT_BYTES=20971520 \
    NOMARK_TIMEOUT=60 NOMARK_WORKDIR=/tmp/nomark-work TMPDIR=/tmp \
    OMP_NUM_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libimage-exiftool-perl qpdf ghostscript \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nomark

WORKDIR /app
COPY requirements.lock ./
COPY LICENSE THIRD_PARTY_NOTICES.md ./
RUN pip install --no-cache-dir -r requirements.lock
COPY nomark ./nomark
COPY static ./static
COPY watermarks-remover/service/scripts ./watermarks-remover/service/scripts
COPY watermarks-remover/LICENSE ./watermarks-remover/LICENSE
RUN chmod -R a+rX /app
USER nomark
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,json; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')); assert r['ok'] and r['engine_available'] and r['pdf_ready']"
CMD ["python", "-m", "uvicorn", "nomark.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
