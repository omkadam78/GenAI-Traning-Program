FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/farmer
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt \
    && useradd --create-home --uid 10001 farmer
COPY --chown=farmer:farmer . .
RUN mkdir -p /app/data/chroma_db /app/data/runtime /home/farmer/.cache \
    && chown -R farmer:farmer /app/data /home/farmer
USER farmer
EXPOSE 8000 8501
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
