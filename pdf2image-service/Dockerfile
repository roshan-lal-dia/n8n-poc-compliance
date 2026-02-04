FROM python:3.11-slim

# Install poppler-utils (required by pdf2image for PDF rendering) and curl for healthcheck
RUN apt-get update && \
    apt-get install -y poppler-utils curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir pdf2image Pillow Flask gunicorn

WORKDIR /app

# Copy application code
COPY app.py .

# Expose the API port
EXPOSE 3001

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:3001", "--workers", "2", "--timeout", "600", "app:app"]
