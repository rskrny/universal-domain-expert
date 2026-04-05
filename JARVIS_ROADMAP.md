# Jarvis Roadmap

> Tracking the evolution from reactive domain expert to proactive autonomous assistant.
> Updated: April 6, 2026 (Session 018)

---

## The Three-Layer Model

Jarvis is defined by three capabilities, built in order. Each layer depends on
the one below it. No shortcuts.

```
Layer 3: ACTION (execute on Ryan's behalf)
   |  Send messages, draft proposals, post content,
   |  file tickets, schedule meetings, manage tasks
   |
Layer 2: COGNITION (reason across all inputs)      <-- BUILDING NOW
   |  Cross-project prioritization, resource conflict
   |  detection, proactive recommendations, action planning
   |
Layer 1: PERCEPTION (observe the world)
      Reddit scanning, Brain Feed ingestion, routing log,
      memory files, deadline detection, system health
```

---

## Layer 1: Perception (80% complete)

What exists:
- [x] Reddit scanner with quality scoring (117 allowed subs, 60 denied)
- [x] Reddit-to-project matcher with two-tier keywords (10 projects)
- [x] Brain Feed Lark bot (knowledge ingestion via DM)
- [x] Deadline scanner (14-day window, urgency categorized)
- [x] Routing log (145+ queries, domain + tier + confidence)
- [x] System health metrics (chunk count, routing stats)
- [x] Memory system (36 files, 10 project files)
- [x] State tracking with delta computation between runs

What is missing:
- [ ] Email read access (even read-only would transform briefings)
- [ ] Calendar awareness (know today's meetings and free blocks)
- [ ] Lark message monitoring (detect replies and mentions)
- [ ] Git activity across project repos (detect stale codebases)
- [ ] Cross-project file watcher (detect when project files change)

---

## Layer 2: Cognition (30% complete)

### Built (Session 018)

- [x] **Project Scanner** (`scripts/orchestrator/project_scanner.py`)
  Parses all project memory files into structured ProjectState objects.
  Detects: status, staleness, blockers, waiting items, next actions,
  deadlines, revenue signals.

- [x] **Action Planner** (`scripts/orchestrator/planner.py`)
  Reasons across all perception inputs. Scores actions by:
  time pressure, revenue impact, blocked state, staleness, opportunity cost.
  Outputs ranked ActionItem list with priority, forcing function, effort estimate.

- [x] **Action Tracker** (`scripts/orchestrator/action_tracker.py`)
  Records recommendations and tracks follow-through. Computes act rate
  by category. Creates the feedback loop for the planner to learn
  which recommendations get acted on.

- [x] **Briefing Integration**
  Orchestrator output appears at the top of both local markdown and
  Lark card briefings. "Today's Focus" section with top 3 actions.

### Planned

- [ ] **Cross-project resource detector**
  Flag when committed hours across projects exceed available bandwidth.
  Requires: effort estimates per project per week.

- [ ] **Communication pattern tracker**
  Detect unanswered threads. "You haven't replied to Marianne in 3 days."
  Requires: email/Lark read access from Layer 1.

- [ ] **Priority weight learning**
  Use action_tracker act rates to auto-adjust priority weights.
  Categories that get acted on more should get higher base scores.

- [ ] **Proactive session opener**
  At session start, the orchestrator presents today's plan without
  being asked. Not "what do you want to work on?" but "here's what
  needs your attention."

- [ ] **Project dependency graph**
  Model which projects block or feed into others.
  Example: Goldie procurement unlocks Goldie development work.

---

## Layer 3: Action (10% complete)

### Built

- [x] LinkedIn social posting (text + image)
- [x] Lark card delivery (briefing to Brain Feed chat)

### Planned

- [ ] **Draft communications**
  Generate email/message drafts for review, not auto-send.
  "Marianne hasn't replied in 3 days. Draft follow-up?"

- [ ] **Autonomous task management**
  Create and update tasks from conversation context.
  Track what was discussed, what was decided, what needs doing.

- [ ] **Scheduled report delivery**
  Weekly project health report. Monthly revenue summary.
  Delivered via Lark card or email.

- [ ] **Multi-channel alerting**
  Push notifications for urgent items (deadline today, reply received).
  Requires: always-on background process.

- [ ] **Project scaffolding**
  "New client signed. Create project folder, memory file, domain context,
  proposal template, and kickoff checklist."

---

## Milestone Targets

### M1: Proactive Briefing (DONE)
The system tells you what to do today without being asked.
Orchestrator + briefing integration.

### M2: Session Intelligence
The orchestrator runs automatically at session start and presents
today's plan as the first thing you see. No bootstrap needed.
**Target: Session 019-020**

### M3: Communication Awareness
Email read access. The system knows who wrote to you and surfaces
unanswered threads alongside project priorities.
**Target: When email integration is feasible**

### M4: Draft-and-Review
The system drafts responses to routine communications and presents
them for approval. Not auto-send. Human in the loop.
**Target: After M3**

### M5: Always-On
Background process that monitors inputs between Claude Code sessions.
Push notifications for urgent items. Mobile-accessible dashboard.
**Target: Stretch goal**

---

## Metrics

Track these to measure progress toward Jarvis:

| Metric | Current | Target |
|--------|---------|--------|
| Perception sources | 4 (Reddit, Brain Feed, memory, routing log) | 8+ |
| Action tracker act rate | 0% (just started) | >50% |
| Projects with structured state | 10 | All active |
| Proactive recommendations per day | 8 | 5-10 (quality over quantity) |
| Time from event to awareness | Daily batch | <1 hour |
| Autonomous actions per week | 0 | 5-10 (with approval) |

---

## Principles

1. **Build perception before cognition. Build cognition before action.**
   Don't try to auto-send emails before you can reliably detect what
   needs a reply.

2. **Human in the loop for all actions.**
   Draft, review, approve. Never auto-send. Never auto-delete.
   Trust is earned through accuracy, not seized through automation.

3. **Lightweight and local.**
   HP OMEN with 4GB free RAM. No heavy ML. No parallel processes.
   Numpy-only inference. Static HTML dashboards. Sequential pipelines.

4. **Feedback loops everywhere.**
   The action tracker measures what gets acted on. The retrieval system
   measures what gets searched. The routing log measures what gets asked.
   Every subsystem generates signal for improving the next one.

5. **Structural organization over clever hacks.**
   Three layers, clear module boundaries, documented architecture.
   Every new component belongs in exactly one layer.
