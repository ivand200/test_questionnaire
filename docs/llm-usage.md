# LLM usage note

## Tools and models

| Where | Tool or model | Use |
| ----- | ------------- | --- |
| Development | Claude Code (CLI), model Claude Sonnet 5.5 (as in the commit attribution) | Wrote the code, tests and drafts of the documents, one ticket at a time |
| In the app | OpenAI `gpt-6-luna`, Responses API, PydanticAI 2.54.0 | The draft call and the support check call. Settings: `temperature` 0, `max_tokens` 1000, `openai_reasoning_effort` `medium` |

The model of the app is set in `backend/src/qws/config.py`. The skills used with Claude Code are in `ai-workflow/manifest.json`.

## Generated parts

| Part | Made by | Notes |
| ---- | ------- | ----- |
| Backend (`backend/src/qws`), `schema.sql`, `Makefile` | Claude Code | From the specs of each part. One commit for each ticket |
| Backend tests (`backend/tests`) | Claude Code | Each test has a `spec:` tag and GIVEN/WHEN/THEN comments |
| Frontend (`frontend/src`) and generated API types | Claude Code, `openapi-typescript` | The Inbox screen of Part 6 (shell, queue, review panel, Sources tab) follows the prototype, with Tailwind CSS 4 and daisyUI 5 and the `daisyui` skill. No automated tests. Checked by hand in Safari, including a click-through of the Sources tab and the bump |
| `data/reference-cases.json` | Claude Code | Expected values come from the passages and `domain.md`, not from the output of the app. The author reviews them |
| `data/seed.json`, `data/domain.md`, `data/expected-seed-results.json` | Supplied starter pack | Copied with no change |
| `data/demo.json` (Q9, Q10) | Claude Code | Two added questions: a simulated failure and a simulated wrong draft |
| `replay/responses.json` | The real model, saved by `make record` | 20 entries: 18 are real replies (drafts and support checks) and 2 are simulated (the Q9 failure and the Q10 draft). Never edited by hand |
| README, `docs/walkthrough.md`, `ai-workflow/`, this note | Claude Code | Drafts from the repository and its git history. The author confirms them |

Prompts that the app sends to the model are in `backend/src/qws/core/rules.py`.

## Instruction

One standing instruction shaped the whole build, from the first part to the last:

> All business logic stays in the Backend. The Frontend only draws what the Backend sends and sends clicks. Code sets every status, never the model. Passages go to the model as data, apart from the instructions.

How it shows in the code:

- The Backend sends `allowed_actions`, `owner`, `warning_count`, `call` and the documents, so the screen has nothing to compute (commit `f1f4af8`).
- The model returns only passage IDs. Code checks them against the passages that were sent and copies the text (`check_reply` in `backend/src/qws/core/rules.py`).
- The Frontend tickets of Part 6 follow the same rule: the screen shows `allowed_actions`, `warning_count` and `call` as sent.

## Correction and checks

**Correction.** The review of Part 5 (the support check) found two problems in the code the agent wrote first (commit `772d77b`, "review fixes: P5 support check"):

- The draft reply and the support check reply were each parsed and validated by their own copy of the same `try/except` around `model_validate_json`.
- The `Drafter` port was defined inside `services/draft_service.py`, although it is a shared type and belongs with the other models.

The fix added one helper, `_validated(model_type, reply)`, for both replies, and moved the `Drafter` port to `core/models.py`. It also replaced `Asked.support` with `support_warning`, so the service holds the warning and not a half-parsed reply. Tests were added in `test_rules.py` and `test_recorder.py`. The change touched 7 files.

**Checks that can be repeated:**

- `make checks` runs the five checks and Case 6 in replay mode and writes `docs/check-results.md`.
- `make test` runs `tsc`, `vite build` and `pytest`.
- The Frontend was clicked through by hand in Safari, in replay mode, on a new Database: the Sources tab shows 5 rows, and after Q1 is approved by "Anna", `Bump to v3` on `EXPORT-v2` gives the Toast "EXPORT-v2 is now version 3" and Q1 shows `Needs review`.
- The reference values are written from the passages. They are not copied from a model reply.
- The support check is a second model call. It adds a warning when the cited text does not support the answer. The demo question Q10 shows it.
