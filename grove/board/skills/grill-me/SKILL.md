---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# board:grill-me

Interview me relentlessly about every aspect of this plan until
we reach a shared understanding. Walk down each branch of the design
tree resolving dependencies between decisions one by one.

If a question can be answered by exploring the codebase, explore
the codebase instead.

For each question, provide your recommended answer.

## Process

1. **Extract the plan or design** from the user's message or ask them to state it clearly if not given.

2. **Build the decision tree** — identify the top-level decisions, then for each, the sub-decisions that depend on it. Do this mentally before asking the first question.

3. **Work depth-first**: resolve one branch fully before moving to the next. Do not scatter across all branches at once.

4. **For each question:**
   - State what you're probing and why it matters
   - Give your recommended answer with brief reasoning
   - Ask the user to confirm, reject, or refine
   - If they reject, explore why — that's where the real design happens

5. **Explore the codebase** before asking any question that the code can answer. Check schema, scripts, config, docs. Never ask "does X exist?" if you can look.

6. **Track open vs resolved decisions** — keep a running tally visible to the user so they know progress.

7. **Don't soften or hedge** — if a design choice has a clear winner, say so. If two options are genuinely equivalent, say that and let the user choose based on preference.

8. **Terminate** when all branches of the decision tree are resolved and the user confirms shared understanding.

## Output format

After each exchange, show:

```
Resolved: [list of decided items]
Open:     [list of remaining branches]
Next:     [the specific question you're asking]
```
