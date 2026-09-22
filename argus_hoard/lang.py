"""A tiny, dependency-free "is this English?" heuristic.

CLIP matches English text far better than any other language, so the UI
search box offers to translate a non-English query before embedding it
(the MCP tool tells the agent to translate itself instead -- see
mcp_server.py). Getting this exactly right needs a real language
detector; that is not worth a new pinned dependency (with matching cp313
win_amd64 wheels) for one heuristic. Instead: count stopword hits per
candidate language and only call it non-English when some other language
clearly outscores English. An ambiguous or single-word query (e.g. "red",
a colour that works with the fallback embedder) is left alone.
"""
from __future__ import annotations

import re

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Short, high-frequency stopword lists: enough to separate "una foto de un
# perro en la playa" from "dog on the beach" without pulling in a corpus.
_STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the", "a", "an", "of", "in", "on", "at", "for", "with", "and", "or",
        "is", "are", "my", "our", "from", "to", "photo", "photos", "picture",
        "pictures", "image", "images", "last", "this", "that", "where",
        "when", "who", "some", "with", "near",
    },
    "es": {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
        "en", "con", "y", "o", "es", "son", "mi", "mis", "nuestro", "desde",
        "foto", "fotos", "imagen", "imágenes", "último", "última", "donde",
        "dónde", "cuando", "cuándo", "quien", "quién", "playa", "perro",
    },
    "fr": {
        "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "est",
        "sont", "mon", "ma", "mes", "notre", "depuis", "photo", "photos",
        "image", "images", "dernier", "dernière", "où", "quand", "qui",
        "plage", "chien",
    },
    "de": {
        "der", "die", "das", "ein", "eine", "und", "oder", "ist", "sind",
        "mein", "meine", "unser", "von", "foto", "fotos", "bild", "bilder",
        "letzte", "letzter", "wo", "wann", "wer", "strand", "hund",
    },
    "pt": {
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da",
        "e", "ou", "é", "são", "meu", "minha", "nosso", "desde", "foto",
        "fotos", "imagem", "imagens", "último", "última", "onde", "quando",
        "quem", "praia", "cachorro", "cão",
    },
    "it": {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "e",
        "o", "è", "sono", "mio", "mia", "nostro", "da", "foto", "immagine",
        "immagini", "ultimo", "ultima", "dove", "quando", "chi", "spiaggia",
        "cane",
    },
}


def detect_non_english(text: str) -> str | None:
    """Return a language code (e.g. "es") if `text` looks confidently
    non-English, else None (English, or too ambiguous to call)."""
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    if len(words) < 2:
        return None  # a single word ("red", "sunset") is left alone
    scores = {lang: sum(1 for w in words if w in stops) for lang, stops in _STOPWORDS.items()}
    en_score = scores.pop("en")
    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score >= 1 and best_score > en_score:
        return best_lang
    return None
