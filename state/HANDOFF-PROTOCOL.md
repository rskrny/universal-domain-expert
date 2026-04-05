# Handoff Protocol — Session Context Transfer

> This file tells the LLM HOW to save and load session state. It is NOT the state
> itself — that lives in `HANDOFF.md` (same directory).
>
> **When to read this file:** When the user asks to save state, update the handoff,
> or when CLAUDE.md directs you to check for session state on startup.

---

## Overview

LLM sessions are stateless. When a session ends, everything is lost. The handoff
system solves this by writing a structured snapshot to `state/HANDOFF.md` that the
next session reads to resume with full context.

**Two operations:**
- **Save** — Write current state to HANDOFF.md (end of session or milestone)
- **Load** — Read HANDOFF.md at session start to resume where we left off

---

## Save Operation

### When to Save

Save is triggered by any of these:
- User explicitly says: "save state", "update handoff", "save context", "save progress"
- User references `state/HANDOFF.md` with intent to update
- End of a Tier 3 engagement (prompt the user: "Want me to save state for next session?")
- Completion of a major milestone in a multi-session project
- User says they're done for now / ending the session

### What to Capture

**ALWAYS include:**
- What we're working on (project/engagement description)
- Current pipeline stage and what's been completed
- Key decisions made and WHY (rationale is critical — without it, the next session re-debates)
- Deliverables produced with file paths and status
- Which domain file(s) are active
- Specific next actions (what to do when resuming)
- Open questions or blockers

**Include when relevant:**
- User preferences or corrections discovered this session
- Important context that isn't obvious from the files alone
- Assumptions that were validated or invalidated
- Stakeholder information the user shared

**NEVER include:**
- Raw chat transcripts or conversation logs
- Full file contents (use file paths — the files are in the repo)
- Internal reasoning or chain-of-thought
- Redundant information already captured in deliverable files
- Temporary or intermediate work products that aren't needed to resume

### How to Structure

Use the template in HANDOFF.md. Keep it tight — under 150 lines. The goal is
maximum context in minimum tokens. Every line should answer: "Would the next
session need this to resume effectively?"

### Write Rules

1. **Overwrite, don't append.** HANDOFF.md always reflects CURRENT state, not history.
   Previous state is gone — that's intentional. If history matters, it's in the deliverables.

2. **Be specific in Resume Instructions.** Not "continue working on the project" but
   "Review the draft market analysis in `deliverables/market-analysis.md`, address
   the three open questions in the Open Items section, then proceed to Stage 5 review."

3. **Timestamp the save.** Include the date so the next session knows how fresh the state is.

4. **Compress decisions.** Each decision = one line. Format: "[Decision]: [Choice] because [reason]"

---

## Load Operation

### When to Load

- **Automatic:** If CLAUDE.md directs you to check `state/HANDOFF.md` on startup
  and the file has content beyond the template placeholder
- **Manual:** User @ references the file or says "pick up where we left off"

### How to Load

1. Read `state/HANDOFF.md`
2. If the file contains only the empty template (no real state), skip — treat as new session
3. If it has real state:
   a. Understand the active engagement and current pipeline stage
   b. Load the specified domain file(s)
   c. Review the Resume Instructions — these are your first actions
   d. Acknowledge to the user: briefly state what you're picking up and where you're resuming
   e. Ask if anything has changed since the last session before diving in

### Load Rules

1. **Don't blindly trust stale state.** If the handoff is more than a week old,
   verify that referenced files still exist and haven't changed significantly.

2. **Don't re-read everything referenced.** The handoff tells you what you need to know.
   Only read referenced files when you actually need their content for the next action.

3. **Don't recite the handoff back.** A brief "Picking up [project] — last session we
   completed [X] and next step is [Y]" is sufficient. Don't read the entire file aloud.

4. **Ask about changes.** Things may have changed between sessions. A quick
   "Anything change since we last worked on this?" prevents acting on stale context.

---

## Multi-Project Support (Future)

The current system uses a single `state/HANDOFF.md`. When multiple concurrent
projects are needed, the system extends naturally:

```
state/
├── HANDOFF.md                    ← Default / most recent project
├── consulting-acme.md            ← Named project handoff
├── course-design-python.md       ← Named project handoff
└── HANDOFF-PROTOCOL.md           ← This file (unchanged)
```

To activate: user @ references the specific project file instead of the default.
The protocol and structure are identical — only the file name changes.

This is not yet implemented. When a user needs it, create project-specific handoff
files following the same template as HANDOFF.md.

---

## Edge Cases

**Session ends without saving:**
Context is lost. This is acceptable for Tier 1-2 work. For Tier 3, the system should
prompt the user to save before they disconnect (if possible).

**Handoff references files that no longer exist:**
The files may have been moved, renamed, or deleted between sessions. Verify file
existence before acting on handoff references. If files are missing, inform the user
and ask how to proceed.

**Handoff conflicts with current file state:**
If the handoff says "market-analysis.md is a draft" but the file has been significantly
modified since the handoff was written, trust the current file state over the handoff.
Update the handoff to reflect reality.

**User wants to abandon the handoff and start fresh:**
Clear HANDOFF.md back to the empty template. No questions asked.
