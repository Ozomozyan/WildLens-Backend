# ---------- builder ----------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
COPY ai/requirements.txt ./ai-req.txt
RUN pip install --prefix=/install -r requirements.txt && \
    pip install --prefix=/install -r ai-req.txt

# ---------- runtime ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# copy site-packages from builder
COPY --from=builder /install /usr/local

# copy source
WORKDIR /app
COPY . .

# gunicorn + uvicorn worker is fine for DRF
CMD ["gunicorn", "--workers=4", "--bind=0.0.0.0:8000", "wildlens_backend.wsgi"]
