# Walkthrough

This file shows how the project was built and how to see it work. The setup steps are in `README.md`.

## Approach

The app was built in six parts. Each part had a short spec, a list of small tickets, one commit for each ticket, and a review pass.

| Part | What it added |
| ---- | ------------- |
| S0 | Repo skeleton |
| P1 | One question (Q3) from load to a drafted answer with a real model call; replay and `make record` |
| P2 | All statuses: draft, unresolved, error; the older policy conflict; Run all; simulated failure for Q9 |
| P3 | Edit, approve, leave open with a note, reuse of an approved answer |
| P4 | Source change: bump a document version, an approved answer goes to `needs review` |
| P5 | Support check: a second model call that adds a warning when the cited text does not support the answer |
| P6 | `make checks`, `make start`, `make reset`, the Inbox screen with a Sources tab, and the documents |

The order inside the work was the graded items first: the flow, the sources, the flags and the reuse records. Packaging came last, so there is no Docker.

## Decisions

- **Code sets every status, the model never does.** The model returns an answer, a verdict and passage IDs. Code checks each ID against the passages that were sent, copies the passage text as the excerpt, and sets the status.
- **Authority comes from `supersedes` only.** A newer date does not replace a document. Passages of replaced documents are not sent to the model, but the reviewer still sees them with a warning.
- **The support check adds a warning only.** It can be wrong, so it never sets a status and never blocks Approve.
- **Model output and approved answers are in different tables.** A model call is saved once and never changed. `needs review` is computed when a question is read, from the source versions saved at approval.
- **Replay by default.** The app and the checks run with no key from `replay/responses.json`, which holds saved real replies. A change of model, settings, prompt or passage changes the hash and needs `make record`.
- **The Frontend only draws.** The Backend sends `allowed_actions`, `owner`, `warning_count`, `call`, dates and the documents. The Frontend has no business rule and no automated test. It is checked by hand in Safari. The screenshots below come from that run.
- **Reference values are written by hand.** `data/reference-cases.json` holds the expected values of C1 to C6, each with a `source` note from the passages and `domain.md`. They are not copied from model output.
- **No Docker.** `make start` builds the Frontend and serves it with the API on one port.

## Check results

`make checks` proves the five checks and Case 6 in replay mode, with no key. The latest table is in [`docs/check-results.md`](check-results.md): six cases, all `PASS`, no failures.

## Screenshots

Taken in Safari on a clean Database, in replay mode with no key: `make reset`, `make start`, `Run all (10)`, reviewer name "Anna".

| # | File | Screen | Case | What it shows |
| - | ---- | ------ | ---- | ------------- |
| 1 | `docs/screenshots/01-q3-draft.png` | Q3 open in the review panel | C1 | A draft with the `SUPPORT-v1:p1` citation highlighted and the chip `Cached replay` |
| 2 | `docs/screenshots/02-q1-conflict.png` | Q1 open in the review panel | C3 | The alert "Older version conflicts", the `EXPORT-v2:p1` card (`current`) and the struck-through `EXPORT-v1:p1` card |
| 3 | `docs/screenshots/03-q1-reuse.png` | Q1 after Approve by "Anna" | C4 | The badge `Approved` with the approver and time. Asking again makes no model call (proved by C4 in `docs/check-results.md`) |
| 4 | `docs/screenshots/04-q1-needs-review.png` | Q1 after `Bump to v3` on `EXPORT-v2` in the Sources tab | C5 | The badge `Needs review`, "approved on v2, now v3" and the alert "Source changed" |
| 5 | `docs/screenshots/05-q10-support-check.png` | Q10 open in the review panel | Support check | The draft "Yes" and the alert "Support check doubts the answer": the cited passage says the opposite. The status stays `Draft` and Approve stays on |

## Known limits

The list is in the "Known limits" section of `README.md`.
