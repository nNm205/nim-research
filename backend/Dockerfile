FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10 \
    HF_HOME=/app/.cache/huggingface \
    DOCLING_CACHE_DIR=/app/.cache/docling

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        poppler-utils \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip

# Install CPU-only torch BEFORE the main requirements. Without this, docling
# resolves to torch with the full CUDA bundle (~3 GB of nvidia-* + cuda-*)
# which is useless on a CPU Docker host and reliably breaks the build with
# IncompleteRead on flaky connections.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.5.1 torchvision==0.20.1

RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/storage /app/logs /app/.cache/huggingface /app/.cache/docling

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
