FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV MINIO_ENDPOINT=minio:9000
ENV MINIO_ACCESS_KEY=milly-admin
ENV MINIO_SECRET_KEY=
ENV MINIO_SECURE=false
ENV DEFAULT_BUCKET=transfers

EXPOSE 8000

CMD ["python", "server.py"]
