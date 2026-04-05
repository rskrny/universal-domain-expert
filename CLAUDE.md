# Universal Domain Expert System

> For architecture, directory structure, CLI commands, and setup: read `ARCHITECTURE.md`.

---

## ROUTING PROTOCOL -- MANDATORY FOR EVERY REQUEST

**Execute before doing anything else. No exceptions. No shortcuts. No answering
from general knowledge when domain files exist.**

Before responding to ANY substantive user request, follow these steps in order:

### Step 1: Classify
Match the request to a domain using `prompts/ROUTER.md` (the domain registry).
Determine complexity:
- **Tier 1:** Quick factual question, definition, or single-concept explanation
- **Tier 2:** Analysis, recommendation, single deliverable, code task
- **Tier 3:** Complex multi-part project, strategic decision, deep research

If torn between tiers, choose the higher one. For Tier 3, invoke the `/route`
skill which runs the full 8-stage pipeline from `prompts/AGENTS.md`.

### Step 2: Load the Domain File
Read `prompts/domains/{domain}.md` for the matched domain. Apply its frameworks,
quality gates, and anti-patterns to your response. Name which framework guided
your approach.

No domain file exists? Create one using `prompts/TEMPLATE.md` before proceeding.
Register it in `prompts/ROUTER.md`.

### Step 3: Retrieve Knowledge (Tier 2 and above)
Search the retrieval index for relevant context chunks:
- MCP tool: `search_knowledge` or `get_context`
- CLI fallback: `python -m retrieval context "query" --budget 2000`

Skipping this step means ignoring 11,000+ searchable knowledge chunks.

### Step 4: Apply Domain Frameworks and Verify Writing
Structure your response using the domain file's frameworks. Before delivering,
verify: no semicolons, no em dashes, no "not X but Y" contrast, no AI filler.

### Step 5: Log Routing (Silent)
If the MCP `log_routing` tool is available, log: query, domain, confidence.
Do not mention this step to the user.

### Bypass Conditions
Skip routing ONLY for: git commits/pushes, file rename/move operations,
system maintenance commands, meta-questions about this system itself,
greetings, or when the user explicitly says "quick" or "just do X."

---

## @route Enforcement (Hook-Driven Routing)

The `scripts/route_hook.py` runs on every prompt via UserPromptSubmit hook.

**`@route` prefix present:** The hook classifies the request by domain and tier,
then injects a `ROUTING DECISION` block into context. Treat it as a hard requirement:

1. Read the specified domain file from `prompts/domains/`
2. For Tier 2+, run `python -m retrieval context "query" --budget 2000`
3. Apply the domain's frameworks to structure your response
4. Verify writing style before delivering
5. If a supporting domain is listed, also load that domain file

**No `@route` prefix:** Respond in fast casual mode. No domain files. No retrieval
search. Just answer directly from your knowledge and memory files.

**The user controls this.** `@route` means full expert pipeline. No prefix means
fast answer.

**Token Compression (Tier 1):** The hook injects a compressed ~160 token domain
summary for Tier 1 queries. No file read needed. For Tier 2+, the full domain
file is still loaded.

---

## Writing Rules (Non-Negotiable)

All written output follows `prompts/context/shared/writing-style.md`. Three hard rejections:
1. **Semicolons.** Never. Two sentences instead.
2. **Em dashes.** Never. Restructure the sentence.
3. **"Not X, but Y" contrast.** Never. Say what something IS. Skip what it isn't.

Anything that reads like AI-generated filler gets rewritten. No banned phrases, no
hedging, no performative depth. Short sentences. Concrete language. Say it like a
human who values the reader's time.

---

## Session Start (Run Once Per Session)

**Do these two things at the start of every new conversation:**

1. **Run the session bootstrap.** Execute `python scripts/bootstrap.py --quick`
   to generate `state/SESSION_CONTEXT.md`. Then read that file. If the script
   fails or the file already exists from this session, just read it directly.

2. **Check for session state.** Read `state/HANDOFF.md`. If it has real content
   (not the empty template), you have a prior session to resume. Acknowledge
   what you're picking up. Follow `state/HANDOFF-PROTOCOL.md`.

3. **Check daily briefing.** If `state/daily_briefing.md` was generated today,
   read it for context instead of running bootstrap.

**The flow for every request after session start:**
1. Routing Protocol: classify domain + tier
2. Load domain file from `prompts/domains/{domain}.md`
3. Retrieve context from `retrieval/` system (Tier 2+)
4. Execute via `prompts/AGENTS.md` pipeline (scaled by tier)
5. Verify writing style, log routing decision

---

## Self-Maintenance Protocol (Continuous)

**These behaviors are mandatory. Do them proactively without being asked.**

### 1. Domain Gap Detection (Every Request)
Before answering any substantive request, check: does a domain file exist?
- If no domain file exists, **create one before proceeding** using `prompts/TEMPLATE.md`.
  Register it in `prompts/ROUTER.md`.
- If Tier 1, note the gap and offer to create the domain after answering.

### 2. Knowledge Base Updates (After Any Domain Change)
After creating or modifying any file in `prompts/domains/` or `prompts/context/`:
1. Run `python -m retrieval index` to update the search index
2. Run `python -m retrieval viz` to regenerate the knowledge graph
3. Verify the new domain appears in `python -m retrieval stats`

### 3. Cross-Domain Linking (Ongoing)
When creating a new domain, update its "Adjacent domains" section to reference
existing domains. Also update existing domains to reference the new one.

### 4. Quality Ratchet (Every Deliverable)
After completing any Tier 2 or Tier 3 engagement, ask:
- Did the domain file have the frameworks I needed?
- Was there a knowledge gap I had to work around?
- Should a new context chunk be added to `prompts/context/by-domain/`?

If yes, update the domain file or add context.

### 5. State Persistence (Major Milestones)
For any Tier 3 engagement or multi-session work, proactively save state to
`state/HANDOFF.md` at natural breakpoints. Do not wait for the user to ask.

---

## Session Continuity

**Saving state:** When the user says "save state", "update handoff", or "save progress",
write current session context to `state/HANDOFF.md` following the protocol in
`state/HANDOFF-PROTOCOL.md`. For Tier 3 engagements, prompt the user to save at
major milestones.

**Resuming:** At session start, if `state/HANDOFF.md` has real content, briefly
acknowledge what you're resuming and ask if anything has changed before diving in.
