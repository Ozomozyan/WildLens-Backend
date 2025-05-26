# ai/Dockerfile

FROM python:3.12-slim
WORKDIR /app

# 1. Copy in your AI dependencies list
COPY requirements.txt .

# 2. Install everything in one go
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the rest of your AI service code
COPY . .

# 4. Expose & run (adjust 'serve.py' to whatever your entrypoint is)
EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
