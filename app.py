# app.py
from flask import Flask, request, jsonify
from translation import translate_input

app = Flask(__name__)

@app.route("/translate", methods=["POST"])
def translate_text():
    data = request.get_json()
    if not data or "sentence" not in data:
        return jsonify({"error": "Missing 'sentence' in request body"}), 400

    sentence = data["sentence"]
    result = translate_input(sentence)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
