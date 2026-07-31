FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pandas==2.3.3 pyarrow==21.0.0 s3fs==2025.9.0 \
    lightgbm==4.6.0 scikit-learn==1.7.2 mlflow==3.4.0 boto3==1.40.21
WORKDIR /app
COPY train.py ./
USER 65534
ENTRYPOINT ["python", "train.py"]
