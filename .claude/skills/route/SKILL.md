---
name: route
description: "Route requests through the domain expert pipeline for maximum quality. TRIGGER when: any request classified as Tier 2 or Tier 3 that requires analysis, strategy, code architecture, multi-step deliverables, research, writing, recommendations, or multi-domain expertise. Also trigger when the user explicitly asks for deep work, a full engagement, or invokes /route. DO NOT TRIGGER when: quick Tier 1 factual questions, git operations, file moves, system maintenance, or meta-questions about the routing system itself."
user_invocable: true
---

# Domain Expert Routing Pipeline

This skill enforces the full domain expert routing protocol defined in
`prompts/ROUTER.md` and `prompts/AGENTS.md`. Every substantive request
passes through this pipeline. No shortcuts. No skipped steps.

## When This Skill Activates

Invoke this skill for any request that requires domain expertise. The only
exceptions are pure meta-questions about the system itself (e.g., "how does
routing work?") or trivial conversational exchanges.

## Execution Protocol

Follow these steps in exact order. Do not skip any step.

### Step 0: Check Session State

Read `state/HANDOFF.md` in the project root. If it contains real content
(anything beyond the empty template), you are resuming a prior session.

- Acknowledge what you are picking up.
- Ask if anything has changed before continuing.
- Follow the protocol in `state/HANDOFF-PROTOCOL.md`.

If `HANDOFF.md` is empty or contains only the template, proceed fresh.

### Step 1: Classify the Request

Read the user's request and classify it on four dimensions. Reference the
Domain Registry table in `prompts/ROUTER.md` for trigger patterns.

**1a. Domain Identification**

Match the request to one or more domain files in `prompts/domains/`.

- Identify a **primary domain** that owns the core deliverable.
- Identify any **supporting domains** that provide supplementary input.
- If no domain file exists for the topic, stop and create one immediately
  using `prompts/TEMPLATE.md`. Register it in `prompts/ROUTER.md`. Run
  `python -m retrieval index` and `python -m retrieval viz` after creation.
  Then resume routing.

**1b. Complexity Tier**

Classify into one of three tiers:

| Tier | Signal | Pipeline Depth |
|------|--------|----------------|
| Tier 1 | Simple factual question, definition, explanation | Stages 1-2 implicit, answer directly |
| Tier 2 | Analysis, recommendation, single deliverable | Stages 1-4 explicit, light QA (5-6) |
| Tier 3 | Complex multi-part project, strategic decision, deep research | All 8 stages with full rigor |

Rules:
- If torn between Tier 1 and Tier 2, choose Tier 2.
- If torn between Tier 2 and Tier 3, ask the user what depth they want.
- Classify based on actual complexity, not surface length of the request.

**1c. Context Needs**

Determine what additional context to load from `prompts/context/`:

- Shared frameworks (`context/shared/`) only if the domain file references them.
- Domain-specific material (`context/by-domain/`) only for Tier 2-3.
- If the retrieval system is available, use `python -m retrieval context "query"`
  or the MCP `get_context` tool to find relevant chunks.

**1d. Produce the Routing Decision**

Format:
```
ROUTING DECISION:
  Domain:     [primary domain file]
  Supporting: [additional domain files, or "none"]
  Tier:       [1 / 2 / 3]
  Context:    [list of context files to load, or "none"]
  Pipeline:   [which stages to execute explicitly]
```

**1e. Log the Routing Decision (Training Data)**

After producing the routing decision, log it for neural router training.
If the MCP `log_routing` tool is available, call it with:
- query: the user's original request
- domain: the primary domain assigned
- confidence: your confidence in the classification (0.0 to 1.0)

This accumulates training data. After 50 logged routing decisions, the neural
router can be trained to handle classification automatically. You do not need
to ask the user before logging. This is a silent, automatic step.

### Step 2: Load Memory Context

Check memory files in the project memory directory for anything relevant to
this request. The memory directory is at:
`C:\Users\rskrn\.claude\projects\C--Users-rskrn-Desktop-universal-domain-expert---Copy\memory\`

Scan `MEMORY.md` for entries that match the request topic. Common relevant
memories include:

- **User profile** (Ryan Kearney, multi-project founder in China, 6 active projects)
- **Hardware limits** (HP OMEN 16GB RAM, only ~4GB free, no parallel heavy processes)
- **Coding practices** (handle None explicitly, test at prod scale, check container dims)
- **GPU performance** (no continuous D3 force sim, prefer static layouts, Canvas over SVG)
- **Project-specific state** (FinModel AI, Neural Net Dashboard, Flip Side, etc.)
- **Proxy issues** (Clash Verge breaks networking, use trust_env=False)
- **Lark routing** (never use FlipBot MCP for Ryan, use Brain Feed worker /send)

Load the specific memory files referenced in MEMORY.md if they contain details
that would change how you approach the request. Do not load all memories for
every request. Load only what is relevant.

### Step 3: Load Domain Files

Read the primary domain file from `prompts/domains/{domain}.md`.

For supporting domains, load only the sections relevant to the request.
Do not load the entire supporting domain file.

For Tier 2-3 requests, also load `prompts/AGENTS.md` for the full pipeline
stage definitions.

### Step 4: Execute the Pipeline

Execute the stages appropriate to the tier classification.

**Tier 1 Execution:**
- Stages 1-2 run implicitly (you identify the challenge and pick an approach
  in your head, you do not write it out).
- Answer directly using domain expertise from the loaded domain file.
- Keep the response concise. Tier 1 output is 100-500 tokens.

**Tier 2 Execution:**
- **Stage 1 (Define):** Write a brief Challenge Brief. One sentence for
  CHALLENGE, one for SCOPE, one for SUCCESS CRITERIA. Skip the full template.
- **Stage 2 (Design):** Select an approach using domain frameworks. State
  which framework guided the choice. One paragraph.
- **Stage 3 (Structure):** List deliverables if more than one. Skip if single.
- **Stage 4 (Create):** Build the deliverable following domain quality standards
  and writing style rules.
- **Stage 5-6 (QA/Validate):** Run a light self-review. Check for logical gaps,
  unsupported claims, and writing style violations. Fix before delivering.
- **Stage 7-8 (Deliver):** Deliver in chat with a brief executive summary.

**Tier 3 Execution:**
- Execute ALL 8 stages with full rigor as defined in `prompts/AGENTS.md`.
- Produce structured output blocks at each stage gate.
- Use the full Challenge Brief, Approach Design, and Work Breakdown templates.
- Run the complete QA checklist from Stage 5.
- Run domain-specific validation from Stage 6.
- Produce a Delivery Plan in Stage 7.
- Save state to `state/HANDOFF.md` at major milestones.
- For multi-domain requests, apply each domain's frameworks to their respective
  parts and check for contradictions between domain perspectives.

### Step 5: Writing Style Verification

Before delivering ANY output, run this verification pass. This is mandatory
for all tiers. Reference `prompts/context/shared/writing-style.md`.

**Hard Rejections (rewrite the sentence from scratch if found):**

1. **Semicolons.** Search the entire output for semicolons. Replace every one
   with a period and two separate sentences.

2. **Em dashes.** Search for the character `—` (U+2014). Restructure any
   sentence that uses one. Use commas or split into separate sentences.

3. **"Not X, but Y" contrast patterns.** Search for "not...but" and
   "not just...rather" constructions. Rewrite to state what something IS.
   Skip what it isn't.

**AI Slop Detection (delete and rewrite if found):**

Scan for these banned phrases and patterns:

- Filler openers: "It's important to note", "It's worth mentioning",
  "In today's [adjective] world", "When it comes to", "In order to"
- Empty transitions: "Furthermore", "Moreover", "Additionally",
  "That being said", "Having said that"
- Performative depth: "This is a nuanced topic", "There are many factors",
  "The landscape is evolving"
- Pseudo-precision: "leverage" (say "use"), "utilize" (say "use"),
  "robust" (describe the property), "comprehensive" (describe coverage),
  "actionable insights" (give the insights), "best practices" (say the practice)
- Hedging: "It might be worth considering", "One could argue",
  "Perhaps it would be beneficial"
- Filler closers: "In conclusion", "To summarize", "Moving forward",
  "All things considered"

**Positive Standards:**
- Short sentences. Most under 25 words.
- Lead each paragraph with its main point.
- Concrete language over abstract. Numbers over adjectives.
- Active voice over passive.
- One idea per paragraph.

If any violation is found, fix it before delivering. Do not deliver and then
note the violations. Fix first.

### Step 6: Domain Gap Detection

After completing the request, check: did a domain file exist for every topic
that came up? If any topic lacked domain coverage:

- For Tier 2-3 requests: create the missing domain file now using
  `prompts/TEMPLATE.md`. Register it in `prompts/ROUTER.md`. Run
  `python -m retrieval index` to update the search index.
- For Tier 1 requests: note the gap and offer to create the domain file.

### Step 7: State Persistence

For Tier 3 engagements or any multi-session work:

- Save state to `state/HANDOFF.md` at natural breakpoints.
- Do not wait for the user to ask. Save proactively.
- Follow the protocol in `state/HANDOFF-PROTOCOL.md`.

For Tier 2 engagements: save state only if the user requests it.

For Tier 1: no state persistence needed.

## Quality Ratchet

After completing any Tier 2 or Tier 3 engagement, ask yourself:

- Did the domain file have the frameworks I needed?
- Was there a knowledge gap I had to work around?
- Should a new context chunk be added to `prompts/context/by-domain/`?

If yes to any, update the domain file or add context. The system gets better
with every use.

## Error Handling

**Ambiguous request:** Do not guess the domain or tier. Ask one clarifying
question that resolves the ambiguity. Keep the question specific and closed-ended.

**Missing domain file:** Create it before proceeding. Load `prompts/TEMPLATE.md`,
write the domain file, register it, reindex. Then continue.

**Multi-domain conflict:** When domain perspectives contradict each other,
surface the contradiction to the user. Present both perspectives with their
reasoning. Let the user decide which takes priority.

**Pipeline stage failure:** If a stage fails twice on the same issue, escalate
to the user with: what was attempted, why it failed (root cause), and 2-3
proposed alternatives ranked by recommendation strength.

## Token Budget Awareness

Do not load everything for every request. Follow these guidelines:

| Tier | What Gets Loaded |
|------|-----------------|
| Tier 1 | Router classification only. Maybe domain file for accuracy. |
| Tier 2 | Router + primary domain file + relevant memory entries. |
| Tier 3 | Router + domain file(s) + context chunks + memory + AGENTS.md. |

The principle: minimum viable context. Load the minimum needed to answer well.
More context does not mean better answers. It means slower responses and
wasted tokens.
