from flask import Flask, request, jsonify
import os
import threading
import time
import logging
import zipfile
import requests
import re

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

models_ready = False
extraction_error = None
download_progress = 0

def get_confirm_token(response_text):
    """Extract confirmation token from Google Drive response."""
    patterns = [
        r'name="confirm"\s+value="([^"]+)"',
        r'"confirm":"([^"]+)"',
        r'confirm=([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response_text)
        if match:
            return match.group(1)
    return None

def download_google_drive_file(file_id, destination):
    """Download file from Google Drive using requests."""
    global download_progress
    
    try:
        session = requests.Session()
        
        # Headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        session.headers.update(headers)
        
        # Initial request to get confirmation page
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        logger.info(f"Making initial request to: {download_url}")
        
        response = session.get(download_url, stream=True)
        logger.info(f"Initial response status: {response.status_code}")
        logger.info(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
        logger.info(f"Content-Length: {response.headers.get('content-length', 'Unknown')}")
        
        # Check if we got HTML (confirmation page)
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type:
            logger.info("Received HTML page, looking for confirmation token...")
            
            # Get the HTML content
            html_content = response.text
            
            # Extract confirmation token
            confirm_token = get_confirm_token(html_content)
            
            if confirm_token:
                logger.info(f"Found confirmation token: {confirm_token}")
                
                # Make request with confirmation token
                confirmed_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                logger.info(f"Making confirmed request to: {confirmed_url}")
                
                response = session.get(confirmed_url, stream=True)
                logger.info(f"Confirmed response status: {response.status_code}")
                logger.info(f"Confirmed content-length: {response.headers.get('content-length', 'Unknown')}")
                
            else:
                # Try alternative approaches
                logger.info("No confirmation token found, trying alternative method...")
                
                # Look for download warning cookie
                for cookie_name, cookie_value in response.cookies.items():
                    if 'download_warning' in cookie_name.lower():
                        logger.info(f"Found download warning cookie: {cookie_name}={cookie_value}")
                        confirmed_url = f"https://drive.google.com/uc?export=download&confirm={cookie_value}&id={file_id}"
                        response = session.get(confirmed_url, stream=True)
                        break
                else:
                    # Try with 't' confirmation (common for large files)
                    logger.info("Trying with default confirmation token...")
                    confirmed_url = f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"
                    response = session.get(confirmed_url, stream=True)
        
        # Verify we have a good response
        response.raise_for_status()
        
        # Check content length
        total_size = int(response.headers.get('content-length', 0))
        if total_size == 0:
            logger.warning("No content-length header, will download without progress tracking")
        else:
            logger.info(f"Expected file size: {total_size / (1024**3):.2f} GB")
        
        # Download the file
        downloaded = 0
        download_progress = 0
        
        logger.info("Starting file download...")
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=32768):  # 32KB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        download_progress = progress
                        
                        # Log every 5% progress
                        if int(progress) % 5 == 0 and progress > 0:
                            prev_progress = int((downloaded - len(chunk)) / total_size * 100)
                            if int(progress) != prev_progress:
                                logger.info(f"Download: {progress:.1f}% ({downloaded / (1024**2):.1f} MB / {total_size / (1024**2):.1f} MB)")
                    else:
                        # No total size, just log downloaded amount
                        if downloaded % (50 * 1024 * 1024) == 0:  # Every 50MB
                            logger.info(f"Downloaded: {downloaded / (1024**2):.1f} MB")
        
        final_size = os.path.getsize(destination)
        logger.info(f"Download completed! Final size: {final_size / (1024**3):.2f} GB")
        
        # Basic validation - check if it's actually a large file
        if final_size < 100 * 1024:  # Less than 100KB is suspicious
            logger.error(f"Downloaded file is suspiciously small ({final_size} bytes). Might be an error page.")
            return False
        
        # Try to verify it's a ZIP file
        try:
            with zipfile.ZipFile(destination, 'r') as test_zip:
                file_count = len(test_zip.namelist())
                logger.info(f"✅ ZIP file verified. Contains {file_count} files.")
        except zipfile.BadZipFile:
            logger.warning("⚠️ Downloaded file is not a valid ZIP file, but proceeding...")
        
        download_progress = 100
        return True
        
    except requests.RequestException as e:
        logger.error(f"Network error during download: {e}")
        download_progress = 0
        return False
    except Exception as e:
        logger.error(f"Download failed: {e}")
        download_progress = 0
        return False

def extract_models():
    global models_ready, extraction_error, download_progress
    
    try:
        # Create models directory
        if not os.path.exists("models"):
            os.makedirs("models")
            logger.info("Created models directory")
        
        model_path = "models/fine_tuned_fr_en_model"
        bundle_path = "bundle.zip"
        
        if not os.path.exists(model_path):
            logger.info("🔄 Starting model download and extraction process...")
            
            # Google Drive file ID
            file_id = "14wDgRkXHUlSv1nPRJDFgqByL811XMyU9"
            
            # Download the model bundle
            logger.info("📥 Downloading model bundle (this may take several minutes)...")
            if not download_google_drive_file(file_id, bundle_path):
                raise Exception("Failed to download model bundle from Google Drive")
            
            logger.info("📦 Starting extraction...")
            download_progress = 0  # Reset for extraction progress
            
            # Extract files
            with zipfile.ZipFile(bundle_path, 'r') as zip_ref:
                file_list = zip_ref.infolist()
                total_files = len(file_list)
                
                logger.info(f"Extracting {total_files} files...")
                
                for i, file_info in enumerate(file_list):
                    zip_ref.extract(file_info, "models")
                    
                    # Update progress
                    progress = ((i + 1) / total_files) * 100
                    download_progress = progress
                    
                    # Log progress every 10% or every 500 files
                    if (i + 1) % 500 == 0 or progress % 10 < (progress - 1) % 10 or i == total_files - 1:
                        logger.info(f"Extraction: {progress:.1f}% ({i + 1}/{total_files})")
            
            # Clean up
            if os.path.exists(bundle_path):
                os.remove(bundle_path)
                logger.info("🗑️ Cleaned up zip file")
            
            # Verify extraction
            if os.path.exists(model_path):
                model_files = os.listdir(model_path)
                logger.info(f"✅ Model extracted successfully! Found {len(model_files)} files in model directory")
            else:
                raise Exception(f"Model directory not found after extraction: {model_path}")
        else:
            logger.info("✅ Models already exist, skipping download")
        
        models_ready = True
        download_progress = 100
        logger.info("🎉 Models are ready for translation!")
        
    except Exception as e:
        extraction_error = str(e)
        download_progress = 0
        logger.error(f"❌ Model setup failed: {e}")

# Flask routes
@app.route("/")
def index():
    return jsonify({
        "service": "Translation API Server",
        "status": "ready" if models_ready else ("error" if extraction_error else "initializing"),
        "models_ready": models_ready,
        "progress": f"{download_progress:.1f}%",
        "error": extraction_error
    })

@app.route("/status")
def status():
    if models_ready:
        message = "✅ Ready for translation"
        status_code = "ready"
    elif extraction_error:
        message = f"❌ Error: {extraction_error}"
        status_code = "error"
    elif download_progress > 0:
        message = f"⏳ Processing: {download_progress:.1f}%"
        status_code = "loading"
    else:
        message = "🔄 Starting up..."
        status_code = "initializing"
    
    return jsonify({
        "message": message,
        "status": status_code,
        "progress": download_progress,
        "models_ready": models_ready,
        "error": extraction_error,
        "model_path_exists": os.path.exists("models/fine_tuned_fr_en_model")
    })

@app.route("/translate", methods=["POST"])
def translate_text():
    # Check if models are ready
    if not models_ready:
        error_msg = extraction_error if extraction_error else "Models are still loading"
        return jsonify({
            "error": error_msg,
            "progress": f"{download_progress:.1f}%",
            "status": "not_ready"
        }), 503
    
    try:
        # Import translation module
        from translation import translate_input
        
        # Validate request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        sentence = data.get("sentence")
        if not sentence:
            return jsonify({"error": "Missing 'sentence' field"}), 400
        
        sentence = sentence.strip()
        if not sentence:
            return jsonify({"error": "Empty sentence provided"}), 400
        
        if len(sentence) > 1000:
            return jsonify({"error": "Sentence too long (max 1000 characters)"}), 400
        
        # Perform translation
        logger.info(f"Translating: '{sentence[:50]}{'...' if len(sentence) > 50 else ''}'")
        result = translate_input(sentence)
        logger.info("Translation completed successfully")
        
        return jsonify(result)
        
    except ImportError as e:
        logger.error(f"Translation module import failed: {e}")
        return jsonify({"error": "Translation service unavailable"}), 500
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500

if __name__ == "__main__":
    logger.info("🚀 Starting Translation Server...")
    
    # Start model extraction in background thread
    extraction_thread = threading.Thread(target=extract_models, daemon=True)
    extraction_thread.start()
    
    # Start Flask server
    logger.info("🌐 Server will be available at: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
