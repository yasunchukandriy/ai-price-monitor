FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY seed/ seed/

RUN pip install --no-cache-dir . \
    && rm -rf /root/.cache

CMD ["python", "-m", "ai_price_monitor.main"]
