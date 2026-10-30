FROM python:3.11-slim-bookworm AS models
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
WORKDIR /build
COPY build.lock ./build.lock
RUN pip install --no-cache-dir --require-hashes -r build.lock
COPY models.lock.json build_models.py ./
RUN python build_models.py

FROM python:3.11-slim-bookworm
ARG VERSION=0.1.0-alpha.5
ARG REVISION=unknown
LABEL org.opencontainers.image.title="NoMark NMT" org.opencontainers.image.licenses="MIT AND Apache-2.0" \
      org.opencontainers.image.version=$VERSION org.opencontainers.image.revision=$REVISION
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NMT_MODEL_DIR=/models HOME=/tmp/home
RUN useradd --uid 10002 --create-home nmt
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY --from=models /models /models
COPY nmt_service ./nmt_service
COPY models.lock.json LICENSE.models ./
USER 10002:10002
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
 CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3))['ready']"
CMD ["python", "-m", "uvicorn", "nmt_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
