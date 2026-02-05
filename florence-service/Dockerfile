FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (minimal)
# libgl1 and glib are needed for cv2/pillow operations sometimes
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python deps
# Using --no-cache-dir to keep image small
RUN pip install --no-cache-dir -r requirements.txt

# Create the shared directory structure to match n8n
RUN mkdir -p /tmp/n8n_processing && chmod 777 /tmp/n8n_processing

COPY app.py .

# Pre-download model (optional, but good for caching)
# We can create a small script or just let app.py do it on first run.
# For simplicity, let app.py do it, but we set a cache dir
ENV HF_HOME=/app/hf_cache
RUN mkdir -p /app/hf_cache

EXPOSE 5000

CMD ["python", "app.py"]
