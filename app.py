from flask import Flask, request, jsonify
import os
import threading
import time

app = Flask(__name__)

models_ready = False

def extract_models():
    global models_ready
    try:
        import gdown, zipfile

        if not os.path.exists("models/fine_tuned_fr_en_model"):
            print("Downloading model bundle...")
            gdown.download(
                "https://drive.google.com/uc?id=14wDgRkXHUlSv1nPRJDFgqByL811XMyU9",
                "bundle.zip",
                quiet=False
            )
            with zipfile.ZipFile("bundle.zip", "r") as zip_ref:
                zip_ref.extractall("models")
            print("Models extracted.")
        models_ready = True
    except Exception as e:
        print(f"Error downloading or extracting models: {e}")

@app.route("/")
def index():
    return "Server is running."

@app.route("/translate", methods=["POST"])
def translate_text():
    global models_ready
    if not models_ready:
        return jsonify({"error": "Models not ready yet. Please wait."}), 503
    try:
        from translation import translate_input
        data = request.get_json()
        sentence = data.get("sentence")
        if not sentence:
            return jsonify({"error": "No sentence provided."}), 400
        result = translate_input(sentence)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Start model extraction in a background thread
    threading.Thread(target=extract_models).start()
    # Run Flask server
    app.run(host="0.0.0.0", port=5000)
