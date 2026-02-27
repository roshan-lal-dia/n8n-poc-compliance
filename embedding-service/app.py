import os
import logging
import threading

from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optimization for low-resource environments
torch.set_num_threads(4) 

app = Flask(__name__)

# Global model variables
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"
model_id = 'intfloat/multilingual-e5-large'

def load_model():
    global model
    logger.info(f"Loading embedding model: {model_id} on {device}...")
    try:
        model = SentenceTransformer(model_id, device=device)
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {str(e)}")
        raise e

@app.route('/health', methods=['GET'])
def health():
    if model is None:
        return jsonify({"status": "loading", "message": "Model is loading..."}), 503
    return jsonify({"status": "ready", "model": model_id, "device": device}), 200

@app.route('/embed', methods=['POST'])
def embed():
    if model is None:
        return jsonify({"error": "Model not ready"}), 503

    data = request.json
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' in request body"}), 400

    text = data['text']
    
    # Handle both single strings and lists of strings
    if isinstance(text, str):
        texts = [text]
    elif isinstance(text, list):
        texts = text
    else:
        return jsonify({"error": "'text' must be a string or a list of strings"}), 400

    try:
        # e5 models recommend prefixing query strings with "query: " for asymmetric tasks (like RAG)
        # For symmetric tasks or indexing, prefix with "passage: "
        # n8n will send the raw text, we will let n8n handle prefixes in the prompt if needed,
        # or we just pass the raw text. For e5-large, raw text works fine, but "query: " is ideal.
        # Check if the user passed an explicit task type
        task_type = data.get('task_type', None) # 'query' or 'passage'
        
        if task_type == 'query':
            processed_texts = [f"query: {t}" if not t.startswith("query: ") else t for t in texts]
        elif task_type == 'passage':
            processed_texts = [f"passage: {t}" if not t.startswith("passage: ") else t for t in texts]
        else:
            processed_texts = texts

        with torch.inference_mode():
            # encode returns a numpy array, convert to list of floats
            embeddings = model.encode(processed_texts, normalize_embeddings=True)
            
        result = [emb.tolist() for emb in embeddings]
        
        # If single string was passed, return single list, not list of lists
        if isinstance(text, str):
            result = result[0]

        return jsonify({
            "embedding": result,
            "metadata": {
                "model": model_id,
                "dimensions": model.get_sentence_embedding_dimension()
            }
        })

    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Start loading model in background when imported by Gunicorn
if __name__ != '__main__':
    t = threading.Thread(target=load_model)
    t.daemon = True
    t.start()

if __name__ == '__main__':
    load_model()
    # Run on port 8080
    app.run(host='0.0.0.0', port=8080)
