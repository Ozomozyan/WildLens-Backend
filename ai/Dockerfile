# ai/Dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y curl
WORKDIR /app

COPY ai/requirements.txt ./ai/requirements.txt
RUN pip install --no-cache-dir -r ai/requirements.txt

COPY ai/ ./ai
COPY api/ ./api
EXPOSE 8001
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8001"]