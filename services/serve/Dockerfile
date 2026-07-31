FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" \
    "feast[redis]==0.55.0" s3fs lightgbm==4.6.0 mlflow==3.4.0 boto3 \
    prometheus-fastapi-instrumentator
WORKDIR /app
COPY app.py ./
COPY feature_repo ./feature_repo
USER 65534
ENV HOME=/tmp
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
