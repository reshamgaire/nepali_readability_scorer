# -*- coding: utf-8 -*-
"""
scorer.py
Implements the "Nepali Reading Difficulty Scorer" methodology:
  1. Word-level difficulty score (RDS_w) from three factors:
       F_G - Curricular Grade Factor  (needs words_by_grade.json)
       F_C - Orthographic Complexity Factor (matras / halants per akshara)
       F_A - Akshara Factor (syllable length)
  2. Passage-level metrics: mean word difficulty, average sentence length,
     hard-word density.
  3. Composite Document Readability Score (CDRS).
"""

import re
import unicodedata
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------
# Devanagari character classes (Unicode block U+0900-U+097F)
# --------------------------------------------------------------------------

INDEPENDENT_VOWELS = set(
    '\u0904\u0905\u0906\u0907\u0908\u0909\u090A\u090B\u090C'
    '\u090D\u090E\u090F\u0910\u0911\u0912\u0913\u0914'
    '\u0960\u0961\u0972\u0973\u0974\u0975'
)
CONSONANTS = (
    {chr(c) for c in range(0x0915, 0x093A)}   # क..ह
    | {chr(c) for c in range(0x0958, 0x0960)}  # क़..य़ (nukta consonants)
    | set('\u0978\u0979\u097A\u097B\u097C\u097E\u097F')
)
NUKTA = '\u093C'
VOWEL_SIGNS = {chr(c) for c in range(0x093E, 0x094D)} | set('\u0955\u0956\u0957')
HALANT = '\u094D'
MODIFIERS = set('\u0901\u0902\u0903')  # chandrabindu, anusvara, visarga
DEVANAGARI_DIGITS = {chr(c) for c in range(0x0966, 0x0970)}


def is_consonant(c: str) -> bool: return c in CONSONANTS
def is_independent_vowel(c: str) -> bool: return c in INDEPENDENT_VOWELS
def is_vowel_sign(c: str) -> bool: return c in VOWEL_SIGNS
def is_halant(c: str) -> bool: return c == HALANT
def is_nukta(c: str) -> bool: return c == NUKTA
def is_modifier(c: str) -> bool: return c in MODIFIERS
def is_devanagari_digit(c: str) -> bool: return c in DEVANAGARI_DIGITS


def segment_aksharas(word: str) -> List[str]:
    """Heuristic segmentation of a Devanagari word into orthographic
    syllables (aksharas). An akshara is a consonant (or a chain of
    consonants joined by halants, i.e. a conjunct), plus its nukta,
    optional dependent vowel sign (matra), and any nasalisation/visarga
    marks -- or a standalone independent vowel with its own marks.
    Non-Devanagari characters (digits, Latin letters, punctuation) are
    skipped for syllable-counting purposes.
    """
    aksharas = []
    i, n = 0, len(word)
    while i < n:
        c = word[i]
        if is_consonant(c) or is_independent_vowel(c):
            start = i
            i += 1
            if i < n and is_nukta(word[i]):
                i += 1
            # conjunct chain: halant + consonant, repeated
            while i < n and is_halant(word[i]) and (i + 1) < n and is_consonant(word[i + 1]):
                i += 2
                if i < n and is_nukta(word[i]):
                    i += 1
            # word-final halant with nothing to attach to
            if i < n and is_halant(word[i]):
                i += 1
            # dependent vowel sign
            if i < n and is_vowel_sign(word[i]):
                i += 1
            # nasalisation / visarga
            while i < n and is_modifier(word[i]):
                i += 1
            aksharas.append(word[start:i])
        else:
            i += 1
    return aksharas


def word_orthographic_counts(word: str) -> Tuple[int, int, int]:
    """Return (base_chars, matras, halants) totals for the whole word,
    as used by the Orthographic Complexity Factor formula."""
    base_chars = matras = halants = 0
    for c in word:
        if is_halant(c):
            halants += 1
        elif is_vowel_sign(c):
            matras += 1
        elif is_consonant(c) or is_independent_vowel(c) or is_modifier(c) or is_nukta(c):
            base_chars += 1
        elif is_devanagari_digit(c) or c.isdigit():
            base_chars += 1
    return base_chars, matras, halants


# --------------------------------------------------------------------------
# Tokenization
# --------------------------------------------------------------------------

SENTENCE_SPLIT_RE = re.compile(r'(?<=[।॥!?.])\s+')
WORD_SPLIT_RE = re.compile(r'\s+')
PUNCT_STRIP = '।॥,;:!?."\'“”‘’()[]{}—–-…«»'


def split_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    parts = SENTENCE_SPLIT_RE.split(text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts or [text]


def tokenize_words(text: str) -> List[str]:
    raw_tokens = WORD_SPLIT_RE.split(text.strip())
    words = []
    for tok in raw_tokens:
        w = tok.strip(PUNCT_STRIP)
        if w:
            words.append(unicodedata.normalize('NFC', w))
    return words


# --------------------------------------------------------------------------
# Defaults (see ASSUMPTIONS.md for rationale — all are adjustable at runtime)
# --------------------------------------------------------------------------

DEFAULT_WEIGHTS = {'w1': 0.3, 'w2': 0.35, 'w3': 0.35}          # RDS_w: F_G, F_C, F_A
DEFAULT_CDRS_WEIGHTS = {'alpha': 0.3, 'beta': 0.4, 'gamma': 0.3} 
DEFAULT_THRESHOLD = 40       # tau, hard-word cutoff
DEFAULT_FALLBACK_GRADE = 10  # grade assigned to words absent from words_by_grade.json


def interpret_band(cdrs: float) -> Dict[str, str]:
    if cdrs <= 30:
        return {'label': 'Early Primary', 'grades': 'Grades 1–3', 'range': '0–30'}
    if cdrs <= 60:
        return {'label': 'Middle School', 'grades': 'Grades 4–8', 'range': '31–60'}
    if cdrs <= 80:
        return {'label': 'Secondary', 'grades': 'Grades 9–10', 'range': '61–80'}
    return {'label': 'Higher Secondary / Advanced', 'grades': 'Grades 11–12+', 'range': '81–100'}


class ReadabilityScorer:
    def __init__(self, words_by_grade: Dict[str, int]):
        self.words_by_grade = words_by_grade or {}

    def score_word(self, word: str, w1: float, w2: float, w3: float, fallback_grade: int) -> Dict:
        aksharas = segment_aksharas(word)
        a_eff = len(aksharas) if aksharas else 1

        base_chars, matras, halants = word_orthographic_counts(word)
        c_value = (base_chars + 0.5 * matras + 2.0 * halants) / a_eff
        f_c = min(max((c_value - 1.0) / 2.0, 0.0), 1.0) * 100
        f_a = min(max((a_eff - 1) / 4.0, 0.0), 1.0) * 100

        in_wordlist = word in self.words_by_grade
        grade = self.words_by_grade.get(word, fallback_grade)
        grade = min(max(int(grade), 1), 12)
        f_g = ((grade - 1) / 11.0) * 100

        rds_w = w1 * f_g + w2 * f_c + w3 * f_a

        return {
            'word': word,
            'grade': grade,
            'in_wordlist': in_wordlist,
            'akshara_count': a_eff,
            'aksharas': aksharas,
            'F_G': round(f_g, 2),
            'F_C': round(f_c, 2),
            'F_A': round(f_a, 2),
            'RDS_w': round(rds_w, 2),
        }

    def score_text(
        self,
        text: str,
        w1: float = DEFAULT_WEIGHTS['w1'],
        w2: float = DEFAULT_WEIGHTS['w2'],
        w3: float = DEFAULT_WEIGHTS['w3'],
        alpha: float = DEFAULT_CDRS_WEIGHTS['alpha'],
        beta: float = DEFAULT_CDRS_WEIGHTS['beta'],
        gamma: float = DEFAULT_CDRS_WEIGHTS['gamma'],
        threshold: float = DEFAULT_THRESHOLD,
        fallback_grade: int = DEFAULT_FALLBACK_GRADE,
    ) -> Dict:
        # defensively re-normalize weights so they always sum to 1.0
        wsum = w1 + w2 + w3
        if wsum <= 0:
            w1, w2, w3, wsum = (0.3, 0.35, 0.35, 1.0)
        w1, w2, w3 = w1 / wsum, w2 / wsum, w3 / wsum

        csum = alpha + beta + gamma
        if csum <= 0:
            alpha, beta, gamma, csum = (0.3, 0.4, 0.3, 1.0)
        alpha, beta, gamma = alpha / csum, beta / csum, gamma / csum

        sentences = split_sentences(text)
        words = tokenize_words(text)
        total_words = len(words)
        total_sentences = max(len(sentences), 1)

        if total_words == 0:
            return {'error': 'No words found in the supplied text.'}

        word_scores = [self.score_word(w, w1, w2, w3, fallback_grade) for w in words]

        rds_bar = sum(ws['RDS_w'] for ws in word_scores) / total_words
        hard_count = sum(1 for ws in word_scores if ws['RDS_w'] >= threshold)
        hwd = (hard_count / total_words) * 100
        asl = total_words / total_sentences
        f_asl = min(max((asl - 2) / 12.0, 0.0), 1.0) * 100

        cdrs = alpha * rds_bar + beta * hwd + gamma * f_asl

        return {
            'total_words': total_words,
            'total_sentences': total_sentences,
            'asl': round(asl, 2),
            'f_asl': round(f_asl, 2),
            'rds_bar': round(rds_bar, 2),
            'hwd': round(hwd, 2),
            'hard_word_count': hard_count,
            'cdrs': round(cdrs, 2),
            'band': interpret_band(cdrs),
            'weights_used': {
                'w1': round(w1, 4), 'w2': round(w2, 4), 'w3': round(w3, 4),
                'alpha': round(alpha, 4), 'beta': round(beta, 4), 'gamma': round(gamma, 4),
            },
            'threshold': threshold,
            'fallback_grade': fallback_grade,
            'contributions': {
                'rds_component': round(alpha * rds_bar, 2),
                'hwd_component': round(beta * hwd, 2),
                'asl_component': round(gamma * f_asl, 2),
            },
            'words': word_scores,
        }
