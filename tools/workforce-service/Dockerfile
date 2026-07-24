FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY shared/python /app/shared/python
COPY tools/workforce-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir /app/shared/python
COPY tools/workforce-service/app ./app
RUN groupadd --system optiflow \
    && useradd --system --gid optiflow --home-dir /app --shell /usr/sbin/nologin optiflow \
    && mkdir -p /app/data \
    && chown -R optiflow:optiflow /app
USER optiflow
EXPOSE 8103
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8103"]
