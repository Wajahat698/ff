# translation.py
import pandas as pd
import re
from langdetect import detect
from transformers import MarianMTModel, MarianTokenizer

# ----------- Load Translation Models -----------
def load_model_and_tokenizer(model_name):
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    return tokenizer, model

# ----------- Load Dataset -----------
df = pd.read_csv("data (1).csv")
french_to_shimarore = dict(zip(df['text'].str.lower(), df['target'].str.lower()))
shimarore_to_french = dict(zip(df['target'].str.lower(), df['text'].str.lower()))

# ----------- Word Replacers -----------
def replace_french_with_shimarore(text):
    words = text.lower().split()
    replaced = False
    for i, word in enumerate(words):
        if word in french_to_shimarore:
            words[i] = french_to_shimarore[word]
            replaced = True
    return ' '.join(words), replaced

def replace_shimarore_with_french(text):
    words = text.lower().split()
    replaced = False
    for i, word in enumerate(words):
        if word in shimarore_to_french:
            words[i] = shimarore_to_french[word]
            replaced = True
    return ' '.join(words), replaced

# ----------- Translation Core -----------
def translate(text, tokenizer, model):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    outputs = model.generate(**inputs)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

# ----------- Clean Input for Detection -----------
def clean_text(text):
    return re.sub(r"[^\w\s]", "", text.lower())

# ----------- Load All Models Once -----------
fr_en_tokenizer, fr_en_model = load_model_and_tokenizer("fine_tuned_fr_en_model")
en_fr_tokenizer, en_fr_model = load_model_and_tokenizer("fine_tuned_en_fr_model")
sw_en_tokenizer, sw_en_model = load_model_and_tokenizer("fine_tuned_sw_en_model")
en_sw_tokenizer, en_sw_model = load_model_and_tokenizer("fine_tuned_en_sw_model")

# ----------- Main Interface -----------
def translate_input(sentence):
    original = sentence.strip().lower()
    cleaned = clean_text(original)
    words = cleaned.split()

    result = {
        "input": original,
        "detected_language": None,
        "translation": None,
        "status": "success"
    }

    # --- Check Single Word Mappings ---
    if len(words) == 1:
        word = words[0]
        if word in french_to_shimarore:
            result["detected_language"] = "fr"
            result["translation"] = french_to_shimarore[word]
            return result
        elif word in shimarore_to_french:
            result["detected_language"] = "sw"
            result["translation"] = shimarore_to_french[word]
            return result
        else:
            result["status"] = "word not found"
            return result

    # --- Check Sentence Language from Dictionary First ---
    is_french_like = any(w in french_to_shimarore for w in words)
    is_shimarore_like = any(w in shimarore_to_french for w in words)

    try:
        if is_french_like:
            result["detected_language"] = "fr"
            processed, _ = replace_french_with_shimarore(original)
            english = translate(processed, fr_en_tokenizer, fr_en_model)
            shim = translate(english, en_sw_tokenizer, en_sw_model)
            result["translation"] = shim

        elif is_shimarore_like:
            result["detected_language"] = "sw"
            processed, _ = replace_shimarore_with_french(original)
            english = translate(processed, sw_en_tokenizer, sw_en_model)
            french = translate(english, en_fr_tokenizer, en_fr_model)
            result["translation"] = french

        else:
            detected = detect(cleaned)
            result["detected_language"] = detected

            if detected == "fr":
                processed, _ = replace_french_with_shimarore(original)
                english = translate(processed, fr_en_tokenizer, fr_en_model)
                shim = translate(english, en_sw_tokenizer, en_sw_model)
                result["translation"] = shim
            elif detected == "sw":
                processed, _ = replace_shimarore_with_french(original)
                english = translate(processed, sw_en_tokenizer, sw_en_model)
                french = translate(english, en_fr_tokenizer, en_fr_model)
                result["translation"] = french
            else:
                result["status"] = "unsupported language"

    except Exception as e:
        result["status"] = f"error: {str(e)}"

    return result
