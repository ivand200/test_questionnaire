---
name: spec-blueprint
description: Create one spec.md with requirements, examples, and a design blueprint an engineer can review in 2–3 minutes.
disable-model-invocation: true
---

# Spec blueprint

This skill takes the current conversation context and codebase understanding and produces
`tasks/<task-name>/spec.md`. Do NOT interview the user; just synthesize what you already know.

Use ASD-STE100 with simple words. Keep EARS keywords and glossary terms as they are.

Write a **short** spec (Introduction and Requirements) for a bug fix or one behaviour with no
design change; otherwise a **full** spec.

## Steps

1. **Explore.** Read the relevant code, verify, not guess, the domain glossary, and ADRs in the area. Use the
   glossary's vocabulary and respect the ADRs. For a bug, reproduce it as a failing
   `/bdd-tests` test.
2. **Requirements.** Fill the Requirements from the template. Done when every acceptance
   criterion has examples that follow the template's Examples rules.
3. **Blueprint** (full spec only). Write the Design per [BLUEPRINT.md](BLUEPRINT.md). It holds
   what crosses a module interface; what hides behind one belongs to implementation. Before
   creating or changing a module, interface, or seam, call the Skill tool with
   `codebase-design` and use its vocabulary (plus the Skill tool with `python-object-design`
   for Python). When an open uncertainty could change the design, compare alternatives with
   its `DESIGN-IT-TWICE.md`, check an external fact with `/research`, or test an assumption
   with `/prototype`. Done when every example ID has an owner, module interfaces are in
   plain words, and the Design is at most 150 lines.
4. **Critical examples.** Copy every ✅ example into the last section of the template. Done when
   every ✅ ID in the tables appears there once, and no other ID does.
5. **Reply.** List open questions (outcomes nobody can state yet), then the `new` and
   `overturned` decisions.

<spec-template>

`````markdown
# Spec: <feature name>

## Requirements

### Introduction

<One short paragraph describing the user problem, scope, and desired outcome.>

Out of scope: <one line: exclusions raised in the conversation or likely to be assumed. Omit when none.>

Root cause: <one line, confirmed by the red repro. Bug only.>

### Glossary

- **<Term>**: <One precise domain definition.>
- **<System_Name>**: <The system or component named in EARS clauses.>

### Requirements

<Repeat the requirement block as needed. Preserve stable numbering: criterion 3 under Requirement 2 is referenced as 2.3, and its examples as 2.3-a, 2.3-b. Describe observable behavior and measurable constraints here; put implementation choices in Design. Technology and file names belong here only when they are product constraints. Cover relevant success paths, boundaries, failures, permissions, empty states, and concurrency.>

✅ = critical example: if it failed in production it would cause real harm.

#### Requirement 1: <Human-readable capability>

**User story:** As a <role>, I want <capability>, so that <benefit>.

##### Acceptance criteria

<Every requirement needs at least one criterion. Select the applicable EARS forms below; use only the forms the behavior needs.>

1. WHEN <event>, THE <System_Name> SHALL <observable response>.
2. IF <failure condition>, THEN THE <System_Name> SHALL <error response>.
3. WHILE <state>, THE <System_Name> SHALL <state-dependent behavior>.
4. THE <System_Name> SHALL <always-required behavior or measurable constraint>.

##### Examples

<1–3 examples per acceptance criterion, each teaching something the others don't; more means the rule, or a story with over 5 rules, should split. Input variations are test parameters, not rows. Given holds concrete values; Then states exact observable outcomes. Mark ✅ the 3–7 rows in the whole spec whose failure in production would cause real harm: each critical story's main happy path, boundaries, errors with impact, security, data integrity, bug reproductions. Add a Kind column (Expected | Unchanged) for a bug.>

| ID    | Rule | Given              | When    | Then            | ✅  |
| ----- | ---- | ------------------ | ------- | --------------- | --- |
| 1.1-a | 1.1  | <concrete context> | <event> | <exact outcome> | ✅  |
| 1.1-b | 1.1  | <concrete context> | <event> | <exact outcome> |     |

## Design

<The blueprint, per BLUEPRINT.md. Full spec only.>

## Critical examples

<Copy of every ✅ example, grouped by requirement. Write it last. The Examples tables stay the
source: copy rows word for word and never edit this section by hand. For each requirement with a ✅
row, give its name and user story once, then each criterion that has a ✅ row, then those rows.>

#### Requirement 1: <Human-readable capability>

**User story:** As a <role>, I want <capability>, so that <benefit>.

1.1 WHEN <event>, THE <System_Name> SHALL <observable response>.

| ID    | Rule | Given              | When    | Then            | ✅  |
| ----- | ---- | ------------------ | ------- | --------------- | --- |
| 1.1-a | 1.1  | <concrete context> | <event> | <exact outcome> | ✅  |
`````
</spec-template>
