# How to write 400k lines of production-ready code with coding agents

Source: https://reddit.com/r/codex/comments/1q7nbzz/how_to_write_400k_lines_of_productionready_code/
Subreddit: r/codex | Score: 237 | Date: 2026-01-08
Engagement: 0.828 | Practical Value: high

## Extracted Claims

**Claim 1:** Spending 2-3x more time on detailed planning and specification before implementation with AI agents yields better outcomes than interleaved planning-and-coding, because agent execution speed amplifies the cost of planning mistakes.
- Evidence: anecdote (confidence: 0.72)
- Details: The author and CTO shipped 400k lines of production code in 2.5 months by front-loading 1-2 hours of PRD and spec planning before implementation. They argue that manual coding interleaves thinking and typing, but agents execute wrong plans 'at superhuman speed,' making upfront planning the bottleneck. The counterintuitive insight is that compression of typing time should shift effort to planning validation.

**Claim 2:** Cross-model review of implementation plans before coding (using different model architectures like Claude Opus and GPT-5.2) uncovers architectural and error-handling gaps that single-model planning misses.
- Evidence: opinion (confidence: 0.65)
- Details: The author explicitly recommends having different models (Claude Code Opus 4.5, GPT 5.2, Gemini) evaluate plans independently, claiming 'they catch different things' and 'disagreements are where the gold is.' This treats cross-model disagreement as a feature for uncovering hidden requirements rather than finding consensus.

**Claim 3:** Continuous verification loops during agent implementation (running tests after each step, not at the end) is essential for production-ready code quality at scale.
- Evidence: tutorial (confidence: 0.68)
- Details: The author describes instructing agents to run verification scripts after each significant change rather than waiting for manual review at the end. They emphasize this prevents compounding errors and note that ~1/3 to 1/2 of their 400k lines are tests (unit and integration), indicating heavy reliance on continuous validation during implementation.

## Key Data Points
- 400k lines of production code
- 2.5 months timeline
- 1-2 hours planning phase
- 2-3x more planning time recommended
- 1/3 to 1/2 of codebase are tests
- 20% net productivity gain cited for naive usage
- GPT 5.2-xhigh model version

**Novelty:** Emerging practice: the specific pattern of front-loading plan validation with multiple models before agent implementation is not yet mainstream but represents a deliberate shift in how developers are adapting to high-speed code generation.

## Counterarguments
- Top commenter suggests self-review with fresh context windows is 'almost as strong' as cross-model review, implying multiple models may not be necessary if context isolation is handled properly.
- Post acknowledges that naive agent usage yields only ~20% productivity gain or 'sometimes even negative,' suggesting the methodology's claimed benefits are highly dependent on disciplined execution and may not generalize to all developers.

---

Wanted to share how I use Codex and Claude Code to ship quickly.

They open Cursor or Claude Code, type a vague prompt, watch the agent generate something, then spend the next hour fixing hallucinations and debugging code that almost works.

Net productivity gain: maybe 20%. Sometimes even negative.

My CTO and I shipped 400k lines of production code for in 2.5 months. Not prototypes. Production infrastructure that's running in front of customers right now.

The key is in how you use the tools. Although models or harnesses themselves are important, you need to use multiple tools to be effective.

Note that although 400k lines sounds high, we estimate about 1/3-1/2 are tests, both unit and integration. This is how we keep our codebase from breaking and production-quality at all times.

Here's our actual process.

# The Core Insight: Planning and Verification Is the Bottleneck

I typically spend 1-2 hours on writing out a PRD, creating a spec plan, and iterating on it before writing one line of code. The hard work is done in this phase.

When you're coding manually, planning and implementation are interleaved. You think, you type, you realize your approach won't work, you refactor, you think again.

With agents, the implementation is fast. Absurdly fast.

Which means all the time you used to spend typing now gets compressed into the planning phase. If your plan is wrong, the agent will confidently execute that wrong plan at superhuman speed.

The counterintuitive move: spend 2-3x more time planning than you think you need. The agent will make up the time on the other side.

# Step 1: Generate a Spec Plan (Don't Skip This)

I start with Codex CLI with  GPT 5.2-xhigh. Ask it to create a detailed plan for your overall objective.

My prompt:  
"<copy paste PRD>. Explore the codebase and create a spec-kit style implementation plan. Write it down to <feature\_name\_plan>.md.

Before creating this plan, ask me any clarifying questions about requirements, constraints, or edge

[Truncated]

## Top Comments

**u/scrameggs** (19 pts):
> I agree about step 3: cross model review. Additionally, I've had almost as strong results having a sota model audit its own work. The key is to ensure it has a fresh context window and doesn't recognize the code as its own work product.
