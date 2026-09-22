from daguerre_hoard.lang import detect_non_english


def test_english_query_is_not_flagged():
    assert detect_non_english("dog on the beach") is None


def test_single_colour_word_is_left_alone():
    # Ambiguous / works with the fallback embedder: never call the model for it.
    assert detect_non_english("red") is None
    assert detect_non_english("playa") is None


def test_spanish_query_is_detected():
    assert detect_non_english("una foto de un perro en la playa") == "es"


def test_french_query_is_detected():
    assert detect_non_english("le chien sur la plage") == "fr"


def test_empty_string_is_not_flagged():
    assert detect_non_english("") is None
    assert detect_non_english(None) is None
