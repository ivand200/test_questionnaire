---
name: do-work-agents
description: Implement a tickets file with one sub-agent per ticket, then review the whole change and report.
disable-model-invocation: true
---

# Do Work Agents

Sub-agents write the code; you coordinate. Pass every sub-agent **context pointers** (paths and
hashes) and nothing else.

## 1. Understand

Read the tickets file and its `spec.md`. Done when you can name each ticket and its blockers.

## 2. Implement each ticket

Work the **frontier**: the first unchecked ticket whose blockers are all done. Repeat until every
ticket is checked.

Spawn an implementer:
`Run /do-work-ticket. Tickets: <path>. Spec: <path>. Ticket: <title>.`

Done when the hand-back passes [Hand-backs](#hand-backs) with `DONE <hash>`.

## 3. Review the whole change

Spawn a reviewer: `Run /code-review on <first ticket hash>^..<last ticket hash> with <spec path>
and <tickets path>. Return findings only.`

Done when the reviewer returns its report.

## 4. Report

Show the engineer:

- Each ticket with its commit hash.
- The review report, unchanged.
- Every decision the engineer made, and any new skip, ignore, or relaxed threshold an
  implementer reported.

Then wait for the engineer. When they name findings to fix, spawn a fresh fixer:
`Run /do-work-ticket in fix mode. Tickets: <path>. Spec: <path>. Findings: <the named findings>.`
Check its hand-back, then report the fix commit with each finding as fixed or declined.

## Hand-backs

`BLOCKED <decision needed>`: ask the engineer, then resume the same agent with the answer.

`DONE <hash>`: judge it by git, not by the report:

- `git log` shows the commit.
- `git show --stat <hash>` lists only files the ticket touches. A stray file: ask the engineer,
  because removing it rewrites history.
- After an implementer, the ticket is checked and `Pending` is replaced with the hash.

A refused, "interim" or late hand-back leaves the agent's final text as its report.
