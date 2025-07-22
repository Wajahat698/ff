from flask import Flask, request, jsonify
import os
import threading
import time
import logging
import zipfile
import subprocess
import sys

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models_ready = False
extraction_error = None
download_progress = 0

def install_gdown():
    """Install gdown if not available."""
    try:
        import gdown
        return True
    except ImportError:
        logger.info("Installing gdown...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
            import gdown
            return True
        except Exception as e:
            logger.error(f"Failed to install gdown: {e}")
            return False

def download_with_gdown(file_id, destination):
    """Download using gdown with progress."""
    global download_progress
    
    try:
        if not install_gdown():
            raise Exception("Could not install gdown")
        
        import gdown
        
        # Construct the download URL
        url = f"https://drive.google.com/uc?id={file_id}"
        
        logger.info(f"Starting download from: {url}")
        logger.info(f"Destination: {destination}")
        
        # Download with gdown (it handles large files automatically)
        output = gdown.download(url, destination, quiet=False, fuzzy=True)
        
        if output is None:
            raise Exception("gdown failed to download the file")
        
        # Check if file was actually downloaded
        if not os.path.exists(destination):
            raise Exception("File was not downloaded")
        
        file_size = os.path.getsize(destination)
        logger.info(f"Download completed! File size: {file_size / (1024**3):.2f} GB")
        
        # Verify it's a ZIP file
        try:
            with zipfile.ZipFile(destination, 'r') as test_zip:
                file_count = len(test_zip.namelist())
                logger.info(f"ZIP file verified. Contains {file_count} files.")
        except zipfile.BadZipFile:
            logger.error("Downloaded file is not a valid ZIP file!")
            return False
        
        download_progress = 100
        return True
        
    except Exception as e:
        logger.error(f"Download with gdown failed: {e}")
        download_progress = 0
        return False

def extract_models():
    global models_ready, extraction_error, download_progress
    try:
        if not os.path.exists("models"):
            os.makedirs("models")
            
        bundle_path = "bundle.zip"
        model_path = "models/fine_tuned_fr_en_model"
        
        if not os.path.exists(model_path):
            logger.info("Starting download of model bundle...")
            
            file_id = "14wDgRkXHUlSv1nPRJDFgqByL811XMyU9"
            
            # Download the file using gdown
            if not download_with_gdown(file_id, bundle_path):
                raise Exception("Failed to download model bundle with gdown")
            
            logger.info("Download completed. Starting extraction...")
            download_progress = 0  # Reset for extraction
            
            # Extract with progress tracking
            with zipfile.ZipFile(bundle_path, "r") as zip_ref:
                file_list = zip_ref.infolist()
                total_files = len(file_list)
                
                logger.info(f"Extracting {total_files} files...")
                
                for i, file_info in enumerate(file_list):
                    zip_ref.extract(file_info, "models")
                    progress = ((i + 1) / total_files) * 100
                    download_progress = progress
                    
                    if i % 100 == 0 or i == total_files - 1:  # Log every 100 files
                        logger.info(f"Extraction: {progress:.1f}% ({i + 1}/{total_files})")
            
            # Clean up zip file
            if os.path.exists(bundle_path):
                os.remove(bundle_path)
                logger.info("Cleaned up zip file")
            
            # Verify extraction
            if os.path.exists(model_path):
                logger.info(f"✅ Model successfully extracted to: {model_path}")
                
                # List contents to verify
                model_files = os.listdir(model_path)
                logger.info(f"Model directory contains {len(model_files)} files")
                
            else:
                raise Exception(f"Model not found at expected path: {model_path}")
        else:
            logger.info("✅ Models already exist, skipping download")
            
        models_ready = True
        download_progress = 100
        
    except Exception as e:
        extraction_error = str(e)
        download_progress = 0
        logger.error(f"❌ Error: {e}")

@app.route("/")
def index():
    return jsonify({
        "service": "Translation API",
        "status": "ready" if models_ready else "loading",
        "models_ready": models_ready,
        "progress": download_progress,
        "error": extraction_error
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy" if models_ready else ("error" if extraction_error else "loading"),
        "models_ready": models_ready,
        "progress": download_progress,
        "error": extraction_error
    })

@app.route("/progress")
def progress():
    """Get current download/extraction progress."""
    if models_ready:
        message = "✅ Ready for translation"
    elif extraction_error:
        message = f"❌ Error: {extraction_error}"
    elif download_progress > 0:
        message = f"⏳ Processing... {download_progress:.1f}%"
    else:
        message = "🔄 Initializing..."
    
    return jsonify({
        "message": message,
        "progress": download_progress,
        "models_ready": models_ready,
        "error": extraction_error,
        "model_exists": os.path.exists("models/fine_tuned_fr_en_model")
    })

@app.route("/translate", methods=["POST"])
def translate_text():
    if not models_ready:
        error_msg = f"Models not ready: {extraction_error}" if extraction_error else "Models still loading..."
        return jsonify({
            "error": error_msg,
            "progress": download_progress
        }), 503
    
    try:
        from translation import translate_input
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        sentence = data.get("sentence")
        if not sentence:
            return jsonify({"error": "No 'sentence' field provided"}), 400
            
        if len(sentence.strip()) == 0:
            return jsonify({"error": "Empty sentence provided"}), 400
            
        if len(sentence) > 1000:
            return jsonify({"error": "Sentence too long (max 1000 chars)"}), 400
        
        logger.info(f"Translating: {sentence[:50]}...")
        result = translate_input(sentence)
        logger.info(f"Translation completed")
        
        return jsonify(result)
        
    except ImportError as e:
        logger.error(f"Translation module error: {e}")
        return jsonify({"error": "Translation service unavailable"}), 500
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500

if __name__ == "__main__":
    logger.info("🚀 Starting Translation Server...")
    
    # Start model extraction in background
    extraction_thread = threading.Thread(target=extract_models, daemon=True)
    extraction_thread.start()
    
    # Start Flask server
    logger.info("🌐 Server starting on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
