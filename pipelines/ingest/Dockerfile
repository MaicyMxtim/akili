FROM python:3.12-slim
RUN pip install --no-cache-dir pandas==2.3.3 pyarrow==21.0.0 "pandera[pandas]==0.26.1" s3fs==2025.9.0
WORKDIR /app
COPY schema.py ingest.py ./
USER 65534
ENTRYPOINT ["python", "ingest.py"]
