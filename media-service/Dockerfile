FROM python:3.11-slim-bookworm AS upstream-build
WORKDIR /build
COPY media-service/build.lock ./build.lock
RUN pip install --no-cache-dir --require-hashes -r build.lock
COPY remove-ai-watermarks/pyproject.toml remove-ai-watermarks/README.md remove-ai-watermarks/LICENSE ./upstream/
COPY remove-ai-watermarks/src ./upstream/src
RUN pip wheel --no-cache-dir --no-deps --no-build-isolation ./upstream --wheel-dir /wheels

FROM python:3.11-slim-bookworm
ARG VERSION=0.1.0-alpha.8
ARG REVISION=unknown
LABEL org.opencontainers.image.title="NoMark Media" org.opencontainers.image.licenses="MIT AND Apache-2.0" \
      org.opencontainers.image.version=$VERSION org.opencontainers.image.revision=$REVISION
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 HOME=/tmp/home TMPDIR=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends libseccomp2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10003 --create-home media
WORKDIR /app
COPY media-service/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY --from=upstream-build /wheels /wheels
RUN pip install --no-cache-dir --no-deps /wheels/*.whl && rm -r /wheels
COPY media-service/media_service ./media_service
COPY LICENSE THIRD_PARTY_NOTICES.md ./
COPY remove-ai-watermarks/LICENSE ./LICENSE.remove-ai-watermarks
USER 10003:10003
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
 CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8002/health',timeout=3))['ready']"
CMD ["python", "-m", "uvicorn", "media_service.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
