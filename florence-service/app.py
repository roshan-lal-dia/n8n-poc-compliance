import os
import logging
import sys
import threading
from unittest.mock import MagicMock

# Mock flash_attn to bypass transformers dynamic module import check.
# Florence-2's modeling file does `import flash_attn` at the top level.
# We mock it so the import succeeds, but we force SDPA attention below
# so flash_attn is never actually called at runtime.
mock_flash = MagicMock()
mock_flash.__spec__ = MagicMock()
mock_flash.__version__ = "2.6.3"
sys.modules["flash_attn"] = mock_flash
sys.modules["flash_attn.flash_attn_interface"] = MagicMock()
sys.modules["flash_attn.bert_padding"] = MagicMock()

from flask import Flask, request, jsonify
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optimization for low-resource CPU envs
torch.set_num_threads(4) 

app = Flask(__name__)

# Global model variables
model = None
processor = None
device = "cuda" if torch.cuda.is_available() else "cpu"
model_id = 'microsoft/Florence-2-large-ft'

def load_model():
    global model, processor
    logger.info(f"Loading model: {model_id}...")
    try:
        # Use SDPA (Scaled Dot Product Attention) — built into PyTorch 2.0+
        # This avoids needing the external flash_attn package while still being fast on A10
        model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            trust_remote_code=True,
            attn_implementation="sdpa"
        ).to(device)
        model.eval() # Explicitly set to eval mode
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        raise e

@app.route('/health', methods=['GET'])
def health():
    if model is None:
        return jsonify({"status": "loading", "message": "Model is loading..."}), 503
    return jsonify({"status": "ready"}), 200

def run_task(image, task_prompt):
    """Run a single Florence-2 task and return the parsed result."""
    with torch.inference_mode():
        inputs = processor(text=task_prompt, images=image, return_tensors="pt").to(device)
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            do_sample=False,
            num_beams=1,
        )
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(
            generated_text,
            task=task_prompt,
            image_size=(image.width, image.height)
        )
        del inputs, generated_ids, generated_text
        return parsed


@app.route('/analyze', methods=['POST'])
def analyze():
    if model is None:
        return jsonify({"error": "Model not ready"}), 503

    data = request.json
    if not data or 'filePath' not in data:
        return jsonify({"error": "Missing 'filePath' in request body"}), 400

    image_path = data['filePath']

    if not os.path.exists(image_path):
        return jsonify({"error": f"File not found: {image_path}"}), 404

    try:
        image = Image.open(image_path)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Task 1: Visual description (for diagram detection & image understanding)
        caption_prompt = "<MORE_DETAILED_CAPTION>"
        caption_result = run_task(image, caption_prompt)
        description = caption_result.get(caption_prompt, "")

        # Task 2: OCR text extraction (replaces Tesseract)
        ocr_prompt = "<OCR>"
        ocr_result = run_task(image, ocr_prompt)
        ocr_text = ocr_result.get(ocr_prompt, "")

        # Cleanup
        import gc
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()

        logger.info(f"Analyzed {image_path}: caption={len(description)} chars, ocr={len(ocr_text)} chars")

        return jsonify({
            "description": description,
            "ocr_text": ocr_text,
            "metadata": {
                "model": model_id,
                "image_size": image.size,
                "device": device
            }
        })

    except Exception as e:
        logger.error(f"Error analyzing image: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Start loading model in background when imported by Gunicorn
if __name__ != '__main__':
    t = threading.Thread(target=load_model)
    t.daemon = True
    t.start()

if __name__ == '__main__':
    load_model()
    # Run on port 5000
    app.run(host='0.0.0.0', port=5000)
