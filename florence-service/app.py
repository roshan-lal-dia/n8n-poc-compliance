import os
import logging
import sys
import threading
from unittest.mock import MagicMock

# Mock flash_attn to bypass transformers dynamic module import check
# This is required to run Florence-2 on CPU-only environments where flash_attn cannot be installed.
# We set __spec__ to verify it exists, but __version__ to 0.0.0 to force CPU fallback.
mock_flash = MagicMock()
mock_flash.__spec__ = MagicMock()
mock_flash.__version__ = "0.0.0"
sys.modules["flash_attn"] = mock_flash

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
device = "cpu"
model_id = 'microsoft/Florence-2-base'

def load_model():
    global model, processor
    logger.info(f"Loading model: {model_id}...")
    try:
        # Force eager attention to avoid flash_attn requirements
        # We still keep the sys.modules mock above just in case the dynamic code checks imports before config
        model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            trust_remote_code=True,
            attn_implementation="eager" 
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

@app.route('/analyze', methods=['POST'])
def analyze():
    if model is None:
        return jsonify({"error": "Model not ready"}), 503

    data = request.json
    if not data or 'filePath' not in data:
        return jsonify({"error": "Missing 'filePath' in request body"}), 400

    # The file path comes from n8n. 
    # n8n sees it as /tmp/n8n_processing/...
    # We mount that same volume to /shared_data/...
    # So we need to map the path if they differ, or keep them identical.
    # Strategy: We will mount the shared volume to /tmp/n8n_processing in THIS container too.
    image_path = data['filePath']

    if not os.path.exists(image_path):
        return jsonify({"error": f"File not found: {image_path}"}), 404

    try:
        image = Image.open(image_path)
        if image.mode != "RGB":
            image = image.convert("RGB")

        prompt = "<MORE_DETAILED_CAPTION>"
        
        # Run inference in context manager to save memory
        with torch.inference_mode():
            inputs = processor(text=prompt, images=image, return_tensors="pt").to(device)

            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                do_sample=False,
                num_beams=1,
            )

            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = processor.post_process_generation(
                generated_text, 
                task=prompt, 
                image_size=(image.width, image.height)
            )
        
        description = parsed_answer.get(prompt, "")
        
        # Cleanup
        del inputs, generated_ids, generated_text
        import gc
        gc.collect()
        
        return jsonify({
            "description": description,
            "metadata": {
                "model": model_id,
                "image_size": image.size
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
