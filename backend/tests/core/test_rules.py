import hashlib

from qws.core.rules import question_hash


def test_question_hash_is_sha256_of_topic_and_normalized_text():
    # spec: 1.1-b
    # GIVEN topic "support" and text "When is email support available?"
    # WHEN the question hash is computed
    q3 = question_hash("support", "When is email support available?")
    q1 = question_hash("exports", "Can free-plan users export CSV?")

    # THEN it is the SHA-256 hex of "support|when is email support available?"
    expected = hashlib.sha256(b"support|when is email support available?").hexdigest()
    assert q3 == expected
    assert q1 != q3


def test_question_hash_ignores_case_and_repeated_spaces_but_keeps_punctuation():
    # spec: 1.1-b
    # GIVEN the same question with other spacing and case
    # WHEN the hashes are computed
    # THEN they are equal; a different punctuation gives another hash
    a = question_hash("support", "When is email support available?")
    assert question_hash("support", "  WHEN is  email support   available? ") == a
    assert question_hash("support", "When is email support available") != a
