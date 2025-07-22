import os
import zipfile
import gdown
import importlib.util
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
ZIP_URL = "https://drive.google.com/uc?id=YOUR_FILE_ID"  # Replace YOUR_FILE_ID with actual ID
ZIP_PATH = "models_bundle.zip"
EXTRACT_DIR = "models"

# --- Download & Extract ZIP ---
if not os.path.exists(EXTRACT_DIR):
    print("Downloading model zip from Google Drive...")
    gdown.download(ZIP_URL, ZIP_PATH, quiet=False)

    print("Extracting...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    # Remove broken app.py (but KEEP translation.py)
    try:
        os.remove(os.path.join(EXTRACT_DIR, "app.py"))
    except FileNotFoundError:
        pass

# --- Load translation.py from ZIP ---
spec = importlib.util.spec_from_file_location("translation", os.path.join(EXTRACT_DIR, "translation.py"))
translation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(translation)

# --- Flask Route ---
@app.route("/translate", methods=["POST"])
def translate():
    data = request.json
    text = data.get("text")
    src = data.get("source_lang")
    tgt = data.get("target_lang")

    result = translation.translate_text(text, src, tgt, base_path=EXTRACT_DIR)
    return jsonify({"translation": result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
