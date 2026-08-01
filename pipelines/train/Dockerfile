FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "feast[redis]==0.55.0" s3fs lightgbm==4.6.0 scikit-learn mlflow==3.15.0 boto3 cryptography
WORKDIR /app
COPY train.py promote.py ./
COPY feature_repo ./feature_repo
USER 65534
ENV HOME=/tmp
ENTRYPOINT ["python", "train.py"]
