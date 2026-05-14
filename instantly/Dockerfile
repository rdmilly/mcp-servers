FROM node:20-slim
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv --no-install-recommends && rm -rf /var/lib/apt/lists/*
COPY repo/ /app/
WORKDIR /app
RUN python3 -m venv /venv && /venv/bin/pip install -e . --quiet
RUN npm install -g supergateway --quiet
EXPOSE 8000
