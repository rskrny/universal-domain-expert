---
name: quality-ratchet
description: Post-engagement quality audit that logs gaps and improves domain files
user_invocable: true
---

# Quality Ratchet

Run after completing any Tier 2 or Tier 3 engagement to capture what worked,
what was missing, and what should be improved for next time.

## Execution Steps

1. **Audit the engagement.** Review what just happened:
   - Which domain file(s) were loaded?
   - Were the frameworks sufficient for the task?
   - Did you have to improvise knowledge that should have been in the domain file?
   - Were there retrieval gaps (relevant chunks missing)?

2. **Score the gaps.** For each issue found:
   - Missing framework: Add it to the domain file
   - Missing context: Create a new chunk in `prompts/context/by-domain/{domain}/`
   - Weak retrieval: Log feedback via `python -m retrieval feedback add --chunk-id X --query "Y" --rating -1`
   - Cross-domain gap: Update adjacent domain references

3. **Update domain files.** If frameworks were missing or insufficient:
   - Add the framework to the relevant domain file
   - Include the real-world application and when to use it
   - Add failure modes and anti-patterns

4. **Log positive feedback.** For chunks that were helpful:
   - `python -m retrieval feedback add --chunk-id X --query "Y" --rating 1`
   - This trains the feedback scoring system over time

5. **Check difficulty log.** Run `python -m retrieval gaps domains` to see
   which domains are struggling. Flag domains with avg difficulty > 0.7.

6. **Reindex if changed.** If any files were modified:
   - `python -m retrieval index`

## Output

Report:
- Gaps found (with severity)
- Changes made (files modified, chunks added)
- Feedback logged (positive and negative)
- Domain difficulty trends
