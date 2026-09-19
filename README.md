# Nepali Readability Scorer

A lightweight Nepali text readability tool that scores passages based on vocabulary difficulty, orthographic complexity, akshara structure, and sentence length. It includes both a Python scoring library and a small Flask web app for interactive analysis.

## Overview

This project evaluates Nepali reading difficulty with a composite score called the Composite Document Readability Score (CDRS). The model combines:

- Grade-level vocabulary difficulty from a custom Nepali word list
- Orthographic complexity based on matras and halants
- Akshara count as a proxy for syllabic complexity
- Average sentence length and hard-word density

The result is intended for classroom, editorial, and content-quality use when assessing how suitable a given passage is for a target grade level.

## Features

- Python library for scoring Nepali passages
- Web interface for quick analysis in the browser
- Adjustable scoring weights and thresholds
- Word-by-word breakdown of difficulty factors
- Grade-band interpretation for the final score
- Word list cache support for editing the vocabulary file without server restart

## Project structure

```text
nepali_readability_scorer/
├── README.md
├── requirements.txt
├── nepali_scorer/
│   ├── __init__.py
│   ├── scorer.py
│   └── words_by_grade.json
└── webapp/
    ├── app.py
    ├── static/
    │   ├── script.js
    │   └── style.css
    └── templates/
        └── index.html
```

## Requirements

- Python 3.9+
- Flask 3.x

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the web app

From the project root:

```bash
python webapp/app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The interface allows you to paste Nepali text, adjust the weights, and view a detailed readability breakdown.

## Using the scoring library

Example:

```python
import json
from nepali_scorer.scorer import ReadabilityScorer

with open("nepali_scorer/words_by_grade.json", "r", encoding="utf-8") as f:
    words_by_grade = json.load(f)

scorer = ReadabilityScorer(words_by_grade)
result = scorer.score_text("मेरो नाम सानु हो। म कक्षा दुईमा पढ्छु।")

print(result["cdrs"])
print(result["band"])
```

The returned dictionary includes:

- `total_words`
- `total_sentences`
- `asl` (average sentence length)
- `hwd` (hard-word density)
- `rds_bar` (mean word difficulty)
- `cdrs` (final composite readability score)
- `band` (grade-band label)
- `words` (word-by-word scores)

## Scoring model

The library uses the following concepts:

- `F_G`: grade-level factor based on the word list
- `F_C`: orthographic complexity factor from matras and halants
- `F_A`: akshara factor based on syllable/akshara count
- `RDS_w`: word-level readability score
- `HWD`: hard-word density
- `ASL`: average sentence length
- `CDRS`: weighted composite score combining the above

The default weights are normalized automatically if custom values do not sum to 1.

## Notes

- Words not present in `nepali_scorer/words_by_grade.json` use the configured fallback grade.
- The app uses a simple cache to reload the word list if the file changes.
- The scoring is heuristic and is best used as an analytical aid rather than an absolute measure of reading difficulty.
