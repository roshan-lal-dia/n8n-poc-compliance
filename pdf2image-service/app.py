#!/usr/bin/env python3
"""
pdf2image REST API service for n8n
Converts PDF pages to PNG images with configurable DPI
"""

from flask import Flask, request, send_file, jsonify
from pdf2image import convert_from_bytes
import io
import zipfile
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_FORMATS = ['png', 'jpeg', 'jpg']
DEFAULT_DPI = 300


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'pdf2image-api',
        'version': '1.0.0'
    })


@app.route('/convert/pdf-to-images', methods=['POST'])
def convert_pdf_to_images():
    """
    Convert PDF pages to images (PNG/JPEG)
    
    Request (multipart/form-data):
        - file: PDF file (required)
        - format: Output format - 'png' or 'jpeg' (optional, default: png)
        - dpi: Resolution - 150-600 (optional, default: 300)
        - quality: JPEG quality 1-100 (optional, default: 95, only for JPEG)
    
    Response:
        - application/zip containing page_001.png, page_002.png, etc.
    """
    try:
        # Validate file presence
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        pdf_file = request.files['file']
        
        if pdf_file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Read PDF data
        pdf_data = pdf_file.read()
        
        if len(pdf_data) > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)'}), 400
        
        # Get parameters
        output_format = request.form.get('format', 'png').lower()
        if output_format not in ALLOWED_FORMATS:
            return jsonify({'error': f'Invalid format. Allowed: {ALLOWED_FORMATS}'}), 400
        
        # Normalize format
        if output_format == 'jpg':
            output_format = 'jpeg'
        
        # Get DPI setting
        try:
            dpi = int(request.form.get('dpi', DEFAULT_DPI))
            if dpi < 150 or dpi > 600:
                return jsonify({'error': 'DPI must be between 150 and 600'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid DPI value'}), 400
        
        # Get quality for JPEG
        quality = 95
        if output_format == 'jpeg':
            try:
                quality = int(request.form.get('quality', 95))
                if quality < 1 or quality > 100:
                    quality = 95
            except ValueError:
                quality = 95
        
        logger.info(f"Converting PDF to {output_format.upper()} at {dpi} DPI")
        
        # Convert PDF to images
        try:
            images = convert_from_bytes(
                pdf_data,
                dpi=dpi,
                fmt=output_format
            )
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            return jsonify({'error': f'PDF conversion failed: {str(e)}'}), 500
        
        if not images:
            return jsonify({'error': 'No pages found in PDF'}), 400
        
        logger.info(f"Converted {len(images)} pages")
        
        # Create ZIP archive with images
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, image in enumerate(images):
                # Create image buffer
                img_buffer = io.BytesIO()
                
                # Save image with appropriate format and quality
                if output_format == 'jpeg':
                    image.save(img_buffer, format='JPEG', quality=quality, optimize=True)
                else:  # PNG
                    image.save(img_buffer, format='PNG', optimize=True)
                
                # Add to ZIP with zero-padded filename
                filename = f'page_{i+1:03d}.{output_format}'
                zip_file.writestr(filename, img_buffer.getvalue())
                logger.info(f"Added {filename} to archive")
        
        zip_buffer.seek(0)
        
        # Return ZIP file
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='pages.zip'
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


if __name__ == '__main__':
    # For development only - production uses gunicorn
    app.run(host='0.0.0.0', port=3001, debug=False)
