FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastmcp httpx uvicorn
COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
