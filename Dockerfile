FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/farmer
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 nginx \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-dev.txt \
    && useradd --create-home --uid 1000 farmer
COPY --chown=farmer:farmer . .
RUN mkdir -p /app/data/chroma_db /app/data/runtime /home/farmer/.cache \
    && chown -R farmer:farmer /app/data /home/farmer
USER farmer
# Bake the public-data index and embedding model into the image, not the first request.
RUN python -m app.vectorstore
EXPOSE 7860 8000 8501
CMD ["python", "-m", "deploy.serve"]
