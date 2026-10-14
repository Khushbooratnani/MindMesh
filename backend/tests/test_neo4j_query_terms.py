from app.db.neo4j import _query_terms


def test_query_terms_drop_question_words_and_normalize_plural_terms():
    assert _query_terms("how to take care of orchids") == ["orchid"]


def test_query_terms_normalize_common_nature_plurals():
    assert _query_terms("flowers in the mountains and hills") == [
        "flower",
        "hill",
        "mountain",
    ]


def test_query_terms_keep_trailing_e_when_normalizing_temples():
    assert _query_terms("temples I visited") == ["temple"]
