FROM python:3.12-slim
RUN pip install --no-cache-dir evidently==0.7.14 pandas pyarrow s3fs
WORKDIR /app
COPY drift_check.py ./
USER 65534
ENV HOME=/tmp
ENTRYPOINT ["python", "drift_check.py"]
