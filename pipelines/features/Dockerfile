FROM python:3.12-slim
RUN pip install --no-cache-dir "feast[redis]==0.55.0" s3fs
WORKDIR /app
COPY build_features.py ./
COPY feature_repo ./feature_repo
USER 65534
ENV HOME=/tmp
ENTRYPOINT ["feast"]
