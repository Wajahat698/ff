from flask import Flask, request, jsonify
import os
import threading

app = Flask(__name__)

@app.route("/")
def index():
    return "Server is running."

@app.route("/translate", methods=["POST"])
def translate_text():
    try:
        from translation import translate_input
        data = request.get_json()
        sentence = data.get("sentence")
        result = translate_input(sentence)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    def delayed_start():
        # Download and extract in a separate thread to not block Railway boot
        import gdown, zipfile
        if not os.path.exists("models"):
            print("Downloading models...")
            gdown.download("https://drive.google.com/uc?id=14wDgRkXHUlSv1nPRJDFgqByL811XMyU9", "bundle.zip", quiet=False)
            with zipfile.ZipFile("bundle.zip", "r") as zip_ref:
                zip_ref.extractall("models")
            print("Models ready.")

    threading.Thread(target=delayed_start).start()
    app.run(host="0.0.0.0", port=5000)
