import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, render_template, request
from nepali_scorer.scorer import (
    DEFAULT_CDRS_WEIGHTS,
    DEFAULT_FALLBACK_GRADE,
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHTS,
    ReadabilityScorer,
)

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORDLIST_PATH = os.path.join(BASE_DIR, "nepali_scorer", "words_by_grade.json")

# Simple mtime-based cache so the word list can be edited/replaced without
# restarting the server.
_wordlist_cache = {"mtime": None, "data": {}}


def load_words_by_grade():
    try:
        mtime = os.path.getmtime(WORDLIST_PATH)
    except OSError:
        return {}
    if _wordlist_cache["mtime"] != mtime:
        with open(WORDLIST_PATH, "r", encoding="utf-8") as f:
            _wordlist_cache["data"] = json.load(f)
        _wordlist_cache["mtime"] = mtime
    return _wordlist_cache["data"]


EXAMPLES = {
    "simple": "मेरो नाम सानु हो। म कक्षा दुईमा पढ्छु। म बिहान सबेरै उठ्छु र हातमुख धुन्छु। मलाई किताब पढ्न र चित्र कोर्न मन पर्छ। मेरो घर नजिकै एउटा सानो बगैँचा छ। त्यहाँ राम्रा फूलहरू फुल्छन्।",
    "complex": "सङ्घीय लोकतान्त्रिक गणतन्त्रात्मक शासन व्यवस्थाको सुदृढीकरणका निम्ति राज्यका निर्देशक सिद्धान्त तथा नीतिहरूको निष्ठापूर्वक कार्यान्वयन हुनु अपरिहार्य छ। शक्ति पृथकीकरण, नियन्त्रण र सन्तुलनको लोकतान्त्रिक मान्यताअनुरूप संवैधानिक अङ्गहरूको स्वायत्तता अक्षुण्ण राख्दै उत्तरदायी र पारदर्शी प्रशासनिक संयन्त्रको पुनर्स्थापना गर्नु वर्तमान परिप्रेक्ष्यमा प्रमुख चुनौती बनेको छ।",
}


@app.route("/")
def index():
    words_by_grade = load_words_by_grade()
    return render_template(
        "index.html",
        wordlist_count=len(words_by_grade),
        wordlist_filename=os.path.basename(WORDLIST_PATH),
        default_weights=DEFAULT_WEIGHTS,
        default_cdrs_weights=DEFAULT_CDRS_WEIGHTS,
        default_threshold=DEFAULT_THRESHOLD,
        default_fallback_grade=DEFAULT_FALLBACK_GRADE,
        examples=EXAMPLES,
    )

@app.route("/api/score", methods=["POST"])
def api_score():
    payload = request.get_json(force=True, silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Please provide some Nepali text to analyze."}), 400

    weights = payload.get("weights", {}) or {}
    cdrs_weights = payload.get("cdrs_weights", {}) or {}

    try:
        threshold = float(payload.get("threshold", DEFAULT_THRESHOLD))
        fallback_grade = int(payload.get("fallback_grade", DEFAULT_FALLBACK_GRADE))
        w1 = float(weights.get("w1", DEFAULT_WEIGHTS["w1"]))
        w2 = float(weights.get("w2", DEFAULT_WEIGHTS["w2"]))
        w3 = float(weights.get("w3", DEFAULT_WEIGHTS["w3"]))
        alpha = float(cdrs_weights.get("alpha", DEFAULT_CDRS_WEIGHTS["alpha"]))
        beta = float(cdrs_weights.get("beta", DEFAULT_CDRS_WEIGHTS["beta"]))
        gamma = float(cdrs_weights.get("gamma", DEFAULT_CDRS_WEIGHTS["gamma"]))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid numeric parameter supplied."}), 400

    words_by_grade = load_words_by_grade()
    scorer = ReadabilityScorer(words_by_grade)
    result = scorer.score_text(
        text,
        w1=w1, w2=w2, w3=w3,
        alpha=alpha, beta=beta, gamma=gamma,
        threshold=threshold, fallback_grade=fallback_grade,
    )

    if "error" in result:
        return jsonify(result), 400

    result["wordlist_size"] = len(words_by_grade)
    return jsonify(result)


@app.route("/api/wordlist-info")
def wordlist_info():
    words_by_grade = load_words_by_grade()
    return jsonify({"count": len(words_by_grade), "filename": os.path.basename(WORDLIST_PATH)})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
