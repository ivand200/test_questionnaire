---
name: grilling
description: Use when the user wants to grill or stress-test a plan or design before building.
---

Interview me relentlessly about every aspect of this plan. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one, until every branch is resolved. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

- Offer few concrete options. `Option A`, `Option B`, etc...
- Give brief tradeoff per option.
- Use ASD-STE100 with simple words.
- Use schemas/monospace, end-to-end diagrams to clarify question

Each question should be formatted like so:

```
❓ **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Finding facts is your job. When a question needs a fact from the environment (filesystem, tools, codebase, etc.), dispatch a sub-agent to find it, and keep asking the questions that don't depend on it — only the questions downstream of the exploration wait for its report. The decisions are the user's: put each to them and wait.
