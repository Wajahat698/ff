from flask import Flask, request, jsonify
import os
import threading
import time
import logging
import zipfile
import gdown

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models_ready = False
extraction_error = None

def extract_models():
    global models_ready, extraction_error
    try:
        if not os.path.exists("models"):
            os.makedirs("models")
            
        if not os.path.exists("models/fine_tuned_fr_en_model"):
            logger.info("Downloading model bundle...")
            gdown.download(
                "https://limewire.com/d/V5bkI#W5cHADsi1N",
                "bundle.zip",
                quiet=False
            )
            
            logger.info("Extracting models...")
            with zipfile.ZipFile("bundle.zip", "r") as zip_ref:
                zip_ref.extractall("models")
            
            # Clean up zip file
            os.remove("bundle.zip")
            logger.info("Models extracted successfully.")
        else:
            logger.info("Models already exist, skipping download.")
            
        models_ready = True
    except Exception as e:
        extraction_error = str(e)
        logger.error(f"Error downloading or extracting models: {e}")

@app.route("/")
def index():
    return jsonify({
        "status": "Server is running",
        "models_ready": models_ready,
        "error": extraction_error
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy" if models_ready else "loading",
        "models_ready": models_ready,
        "error": extraction_error
    })

@app.route("/translate", methods=["POST"])
def translate_text():
    global models_ready, extraction_error
    
    if not models_ready:
        if extraction_error:
            return jsonify({"error": f"Model loading failed: {extraction_error}"}), 503
        return jsonify({"error": "Models not ready yet. Please wait."}), 503
    
    try:
        from translation import translate_input
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided."}), 400
            
        sentence = data.get("sentence")
        if not sentence:
            return jsonify({"error": "No sentence provided."}), 400
            
        if len(sentence) > 1000:  # Limit input length
            return jsonify({"error": "Sentence too long. Maximum 1000 characters."}), 400
            
        result = translate_input(sentence)
        return jsonify(result)
        
    except ImportError as e:
        logger.error(f"Translation module import error: {e}")
        return jsonify({"error": "Translation service unavailable."}), 500
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return jsonify({"error": "Translation failed."}), 500

if __name__ == "__main__":
    # Start model extraction in a background thread
    extraction_thread = threading.Thread(target=extract_models)
    extraction_thread.daemon = True
    extraction_thread.start()
    
    # Run Flask server
    app.run(host="0.0.0.0", port=5000, debug=False)
