FROM alpine:3.22 AS builder

FROM n8nio/n8n:2.6.3

USER root

# Copy apk from the builder image to restore package management capabilities
COPY --from=builder /sbin/apk /sbin/apk
COPY --from=builder /etc/apk /etc/apk
COPY --from=builder /lib/apk /lib/apk
COPY --from=builder /usr/share/apk /usr/share/apk
COPY --from=builder /var/cache/apk /var/cache/apk

# Install tools for local document processing
# Added font packages to ensure proper rendering
# Added openjdk11-jre for LibreOffice PPTX conversion
RUN apk update && apk add --no-cache \
    libreoffice \
    openjdk11-jre \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-data-eng \
    tesseract-ocr-data-ara \
    font-noto \
    font-noto-cjk \
    terminus-font \
    ttf-freefont \
    bash

# Allow Execute Command node usage
ENV NODES_EXCLUDE="[]"
ENV NODES_ALLOW_BUILTIN="ExecuteCommand"

# Create temp directory for processing if not exists
# Ensure node user owns the directory
RUN mkdir -p /tmp/n8n_processing && \
    chown -R node:node /tmp/n8n_processing && \
    chmod 777 /tmp/n8n_processing

USER node
