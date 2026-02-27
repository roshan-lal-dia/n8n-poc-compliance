FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Optimization: Install PyTorch with CUDA 12.1 support for GPU acceleration
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
# Install remaining deps (including gunicorn for production)
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY app.py .

# Pre-download model path (we mount a volume here)
ENV HF_HOME=/app/hf_cache
RUN mkdir -p /app/hf_cache

EXPOSE 8080

# Use Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--workers", "2", "--threads", "2", "app:app"]
