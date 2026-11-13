FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY assistant-service/ /app/

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "assistant_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
