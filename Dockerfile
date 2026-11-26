FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 evalvo \
    && mkdir -p /data/files /data/runtime \
    && chown -R evalvo:evalvo /data
COPY shared/ shared/
COPY services/ services/
USER evalvo
