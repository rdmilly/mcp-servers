FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV KB_ROOT=/data/workdocs
ENV GIT_AUTO_COMMIT=true

EXPOSE 8000

CMD ["python", "server.py"]
