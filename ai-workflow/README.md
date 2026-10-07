# AI workflow used during this exercise

The machine-readable record is `manifest.json`. This file explains it. The author confirms the points marked "to confirm by the author".

## Tools and models

Development time:

| Tool | Use | Details |
| ---- | --- | ------- |
| Claude Code (CLI) | Wrote the backend, tests, Frontend (Tailwind CSS 4 and daisyUI 5) and drafts of the documents, in small tickets | Model Claude Sonnet 5.5, as in the commit attribution. CLI version and settings: not-exportable (not recorded) |

Inside the app:

| Part | Value |
| ---- | ----- |
| Provider and API | OpenAI, Responses API, through PydanticAI 2.54.0 |
| Model | `gpt-6-luna` (`MODEL_NAME`) |
| Settings | `temperature` 0, `max_tokens` 1000, `openai_reasoning_effort` `medium`, `retries` 0, timeout 60 s |
| Calls | The draft call and the support check call, both typed |

The settings are in `backend/src/qws/config.py`. Each model call is saved in the Database with its prompt, raw reply, model and settings. Real replies are in `replay/responses.json`.

Plugins and extensions: `not-used`. MCP and tool settings: `not-used`. Hooks: none set up. To confirm by the author.

## Configuration files

| Category | Status | Where |
| -------- | ------ | ----- |
| Skills | `used` | `ai-workflow/skills/<name>/` for each record in `manifest.json` |
| Agent instructions and subagents | `used`, kept outside the repository | `AGENTS.md`, `tasks/` (specs and tickets), `.notes/` (design notes) |
| Prompts and rules | `used` | `backend/src/qws/core/rules.py`, `data/domain.md`, `data/reference-cases.json` |
| Scripts | `used` | `Makefile`, `backend/src/qws/checks.py`, `backend/src/qws/services/recorder.py` |
| Environment names | `used` | `.env.example` (names only) |

Skills: nine user-level skills shaped the work: `grilling`, `spec-blueprint`, `to-tickets`, `do-work-ticket`, `bdd-tests`, `code-review`, `prototype`, `qa-notes` and `daisyui` (the Part 6 Frontend). The record of each skill points to `ai-workflow/skills/<name>/`. The author copies and trims these folders before hand-in; the repository has no copy yet. The list comes from the commit history and the files in `tasks/`. To confirm by the author.

Agent instructions and specs: kept outside the repository. The author decides what to publish, so `.gitignore` lists `AGENTS.md`, `tasks/` and `.notes/`. `AGENTS.md` has two links to documentation for the agent. A coordinator session handed each ticket to a subagent that ran the `do-work-ticket` skill.

Redactions: none. No credential, token or private URL is in this folder. The `.env` file is not in the repository.

## One workflow example

See `docs/llm-usage.md`. It has one instruction and one correction. Both are drafts from the git history, marked "to confirm by the author".

## Reproduce or replay

1. `cd backend && uv sync`, then `cd ../frontend && pnpm install`.
2. `make start` runs the app on `http://localhost:8000` in replay mode. It needs no key.
3. `make checks` runs the five checks and Case 6 in replay mode and writes `docs/check-results.md`.
4. Real calls need `OPENAI_API_KEY`. Set it in `.env` (see `.env.example`), then run `make record` to save new replies, or start with `MODEL_MODE=real`.

The skills are user-level. To restore them, copy the folders of `ai-workflow/skills/` to `~/.claude/skills/`. No hook is used.

## Decisions and limitations

The default Claude Code setup with a set of small skills suited the task. The work went in thin slices: a spec, tickets, one commit for each ticket, then a review. The skill list and the tool settings are not exported by a tool, so they are recorded by hand and can have gaps.
