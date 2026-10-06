import hashlib

from qws.core.models import PassageRow, QuestionRow
from qws.core.rules import SYSTEM_PROMPT, build_prompt, question_hash


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


def _passage(passage_id: str, text: str = "text") -> PassageRow:
    return PassageRow(id=passage_id, document_id=passage_id.split(":")[0], text=text)


def test_one_word_changed_in_the_system_prompt_changes_the_input_hash():
    # spec: 4.5-a
    # GIVEN the Q3 input hash h1
    # (lower interface: the hash is a pure rule; the replay half of 4.5-a is in the replay ticket)
    question = QuestionRow(id="Q3", topic="support", text="When?", question_hash="x")
    passages = [_passage("SUPPORT-v1:p1")]
    h1 = build_prompt(question, passages, "m", {"temperature": 0}).input_hash

    # WHEN one word of the system prompt changes
    changed = SYSTEM_PROMPT.replace("Never", "Always", 1)
    h2 = build_prompt(question, passages, "m", {"temperature": 0}, system=changed).input_hash

    # THEN the input hash is not h1
    assert changed != SYSTEM_PROMPT
    assert h2 != h1


def test_the_input_hash_depends_on_model_settings_question_and_passage_order():
    # spec: 4.5-a
    # GIVEN a prompt input
    question = QuestionRow(id="Q3", topic="support", text="When?", question_hash="x")
    a, b = _passage("A-v1:p1"), _passage("B-v1:p1")
    base = build_prompt(question, [a, b], "m", {"temperature": 0}).input_hash

    # WHEN one part changes
    # THEN the hash changes; the same input gives the same hash
    assert build_prompt(question, [a, b], "m", {"temperature": 0}).input_hash == base
    assert build_prompt(question, [b, a], "m", {"temperature": 0}).input_hash != base
    assert build_prompt(question, [a, b], "m2", {"temperature": 0}).input_hash != base
    assert build_prompt(question, [a, b], "m", {"temperature": 1}).input_hash != base
