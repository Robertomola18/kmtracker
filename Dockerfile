FROM python:3.11-slim
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev && \
    rm -rf /var/lib/apt/lists/* && \
    python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/static/uploads /data && chmod 755 /app/static/uploads && chmod +x /app/entrypoint.sh

VOLUME ["/data", "/app/static/uploads"]

EXPOSE 5050

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-w", "1", "--threads", "2", "--preload", "--max-requests", "500", "--max-requests-jitter", "50", "-b", "0.0.0.0:5050", "--access-logfile", "/dev/null", "--error-logfile", "/dev/null", "app:app"]
