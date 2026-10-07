---
name: do-work-ticket
description: Implement one ticket from a tickets-*.md file, or fix review findings on it. Use when a coordinator hands you a ticket.
---

# Do Work Ticket

Implement one ticket, or fix review findings on it. A separate reviewer does the review.

Input: tickets path, spec path, and optionally `findings` (fix mode).

## 1. Understand

Read the tickets file and its `spec.md`. Take the first unchecked ticket whose blockers are done, or the one named. Done when you can name each checklist item and the spec section it cites.

## 2. Code Explore

Read the code the ticket touches, out to its boundaries.

## 3. Implement

- Backend: `/bdd-tests` at the agreed test seams.
- Frontend: implement directly.

Extend an existing test before adding one. Run typecheck and the affected tests as you go. Implement this ticket only.

## 4. Validate

Run the full typecheck, linters, and test suite. Done when all pass, with every check as strict as before. Report any new skip, ignore, or relaxed threshold.

## 5. Commit and record

One commit for the ticket. Stage by explicit path; never `git add -A` or `commit -a`, and never amend. Check the ticket and its outcomes, and replace `Pending` with the commit hash.

## BLOCKED

You cannot ask the engineer. Stop before committing and report BLOCKED with the decision needed when:

- the work requires changing the spec's Module map, a module's interface, the External interface, the data model, or a Key design decision
- the code is right and the spec is wrong: a deliberate deviation, with your reason
- a check fails for a non-code reason, such as a service that is down

The coordinator asks, then resumes you with the answer.

## Fix mode

Given `findings`: run Code Explore on the flagged code, then fix each finding or decline it in a line with the reason. With no ticket named, this is a whole-change pass: skip picking a ticket. Run Validate. Commit as `review fixes: <ticket title>`, or `review fixes: <spec name>` for a whole-change pass. The ticket record stays as it is.

## Report

Under 150 words:

- `DONE <commit hash>` or `BLOCKED <decision needed>`
- Check result
- Deviations from the spec
- New skip, ignore, or relaxed threshold
- Fix mode: each finding as fixed or declined
