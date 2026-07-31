FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi==0.118.0 "uvicorn[standard]==0.37.0" \
    pandas==2.3.3 lightgbm==4.6.0 mlflow==3.4.0 boto3==1.40.21 \
    prometheus-fastapi-instrumentator==7.0.0
WORKDIR /app
COPY app.py ./
USER 65534
ENV HOME=/tmp
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
