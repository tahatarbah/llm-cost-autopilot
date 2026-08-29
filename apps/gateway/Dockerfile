FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir hatchling

COPY packages/cost-engine /app/packages/cost-engine
COPY packages/shared /app/packages/shared
COPY apps/gateway /app/apps/gateway

RUN pip install --no-cache-dir \
    /app/packages/cost-engine \
    /app/packages/shared \
    /app/apps/gateway

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8080"]
