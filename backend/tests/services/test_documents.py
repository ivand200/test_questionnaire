import json
import re

from qws.config import REPO_DIR

README = REPO_DIR / "README.md"
MANIFEST = REPO_DIR / "ai-workflow" / "manifest.json"
LLM_USAGE = REPO_DIR / "docs" / "llm-usage.md"


def code_blocks(text: str) -> list[str]:
    return re.findall(r"```[a-z]*\n(.*?)```", text, flags=re.DOTALL)


def test_readme_has_one_workflow_block_with_the_steps_and_cases():
    # spec: 9.1-a
    # GIVEN the README
    text = README.read_text()

    # WHEN a reader looks for the workflow
    labels = ["LOAD", "[1]", "[2]", "[3]", "[4]", "support check", "[Case 5]", "[Case 6]"]
    blocks = [block for block in code_blocks(text) if "LOAD" in block]

    # THEN one monospace block holds every step and case label
    assert len(blocks) == 1
    assert [label for label in labels if label not in blocks[0]] == []


def test_readme_names_the_two_status_words():
    # spec: 9.1-a
    # GIVEN the README
    text = README.read_text()

    # WHEN a reader looks for the status words
    # THEN both words are there
    assert "`unresolved`" in text
    assert "`needs review`" in text


def test_manifest_is_valid_and_has_nine_categories_with_a_status():
    # spec: 9.2-a
    # GIVEN the AI workflow manifest
    # WHEN a test parses it
    raw = MANIFEST.read_text()
    manifest = json.loads(raw)

    # THEN there is no template key, 9 categories each have a status, and no key is in it
    assert "template" not in manifest
    assert len(manifest["categories"]) == 9
    assert all(category["status"] for category in manifest["categories"].values())
    assert "sk-" not in raw


def test_manifest_skill_records_point_to_the_skill_folder():
    # spec: 9.2-a
    # GIVEN the AI workflow manifest
    manifest = json.loads(MANIFEST.read_text())

    # WHEN a test reads the configuration records of the skills
    skills = [r for r in manifest["configuration_records"] if r["category"] == "skills"]

    # THEN each saved path is the folder of that skill
    assert skills
    assert all(r["saved_path"] == f"ai-workflow/skills/{r['name']}/" for r in skills)


def test_llm_usage_has_the_instruction_and_the_correction_with_its_commit():
    # spec: 9.3-a
    # GIVEN the LLM usage note
    text = LLM_USAGE.read_text()

    # WHEN a reader opens it
    sections = {h: body for h, body in re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S)}

    # THEN it lists tools and models and generated parts, shows both sections, and has no draft marker
    assert "Tools and models" in sections
    assert "Generated parts" in sections
    assert "Business logic" in sections["Instruction"] or "business logic" in sections["Instruction"]
    assert "772d77b" in sections["Correction and checks"]
    assert "to confirm by the author" not in text
