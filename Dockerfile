# NeonatalGuard API — production image
# Platform: linux/arm64 (Apple Silicon M2; build with --platform linux/arm64)
FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying source — maximises Docker layer cache reuse.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Pre-create directories that may be volume-mounted at runtime.
RUN mkdir -p data logs models/exports

EXPOSE 8000

# Uvicorn with 1 worker (multi-agent graph holds process-level singletons;
# multiple workers would each initialize separate KB + ONNX instances).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
