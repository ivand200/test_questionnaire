# LLM usage note

Status: draft. The agent wrote it from the git history. The author must confirm the instruction and the correction. Those two sections are marked "to confirm by the author".

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
| Frontend (`frontend/src`) and generated API types | Claude Code, `openapi-typescript` | The Frontend has no automated tests. It is checked by hand |
| `data/reference-cases.json` | Claude Code | Expected values come from the passages and `domain.md`, not from the output of the app. The author reviews them |
| `data/seed.json`, `data/domain.md`, `data/expected-seed-results.json` | Supplied starter pack | Copied with no change |
| `data/demo.json` (Q9, Q10) | Claude Code | Two added questions: a simulated failure and a simulated wrong draft |
| `replay/responses.json` | The real model, saved by `make record` | 20 entries: 18 are real replies (drafts and support checks) and 2 are simulated (the Q9 failure and the Q10 draft). Never edited by hand |
| README, `ai-workflow/`, this note | Claude Code | Drafts from the repository and its git history. The author confirms them |

Prompts that the app sends to the model are in `backend/src/qws/core/rules.py`.

## Instruction

Status: to confirm by the author. Draft, from the history (parts S0 to P6):

> All business logic stays in the Backend. The Frontend only draws what the Backend sends and sends clicks. Code sets every status, never the model. Passages go to the model as data, apart from the instructions.

Evidence: the Backend sends `allowed_actions`, `owner`, `warning_count`, `call` and the documents (commit `f1f4af8`). The model returns only passage IDs, and code copies the text (`check_reply` in `backend/src/qws/core/rules.py`). The author replaces this with the real instruction and a short prompt excerpt.

## Correction and checks

Status: to confirm by the author. Draft, from the history:

- Correction candidate 1, commit `906389d` (review fixes, P2): the diff shows that `demo_path` defaulted to `None`, so only some entry points loaded the Demo file. The fix made the Demo file the default for the app and the Recorder, and removed duplicate test code.
- Correction candidate 2, commit `772d77b` (review fixes, P5): the diff shows the judge and draft replies parsed by separate code. The fix added one `_validated` helper in `draft_service.py` and moved the `Drafter` port to `core/models.py`.
- Correction candidate 3, commit `55dcf66` (S0): the test client dependency changed to `httpx2`.

Checks that the author can repeat:

- `make checks` runs the five checks and Case 6 in replay mode and writes `docs/check-results.md`.
- `make test` runs `tsc`, `vite build` and `pytest`.
- The reference values are written from the passages. They are not copied from a model reply.
- The support check is a second model call. It adds a warning when the cited text does not support the answer. The demo question Q10 shows it.
