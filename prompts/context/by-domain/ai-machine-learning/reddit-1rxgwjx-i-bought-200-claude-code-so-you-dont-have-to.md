# I bought 200$ claude code so you don't have to :)

Source: https://reddit.com/r/OpenSourceeAI/comments/1rxgwjx/i_bought_200_claude_code_so_you_dont_have_to/
Subreddit: r/OpenSourceeAI | Score: 662 | Date: 2026-03-18
Engagement: 0.879 | Practical Value: high

## Extracted Claims

**Claim 1:** Most token consumption in Claude Code sessions comes from context reconstruction (re-reading files and re-exploring dependencies) rather than reasoning, and pre-loading a dependency graph of code reduces token usage by 45% on average and up to 80-85% on complex tasks.
- Evidence: data (confidence: 0.7)
- Details: The author benchmarked three approaches (normal Claude, MCP/tool-based graph, pre-injected context) and observed that typical simple queries like 'Why is auth flow depending on this file?' consumed 20k-30k tokens due to repeated file re-reads and dependency following. The pre-injected context approach (GrapeRoot) showed consistent savings across multiple task types, though these are single-user benchmarks without independent verification.

**Claim 2:** Starting Claude Code sessions with pre-loaded, contextually relevant code files improves answer quality and reduces turn count, because less time is spent on context discovery and more on reasoning.
- Evidence: anecdote (confidence: 0.65)
- Details: The author notes this as a surprising finding: better answers came not just from cost savings, but from the structural change itself. 'Less searching → more reasoning.' This observation came from personal usage rather than controlled experiments, and aligns with intuitive reasoning about cognitive load, but lacks quantitative validation.

**Claim 3:** Claude's claude.md instruction file provides limited relief for repeated context re-reading problems because instructions reset across repository switches and don't prevent redundant file access patterns.
- Evidence: anecdote (confidence: 0.75)
- Details: The author spent a full day optimizing claude.md instructions and found they 'helped… but still re-reads a lot' and are 'not reusable across projects.' This directly motivated building GrapeRoot as a persistent, project-agnostic solution rather than instruction-based.

## Key Data Points
- 20k-30k tokens for simple auth flow questions
- 45% cheaper on average
- 80-85% fewer tokens on complex tasks
- $200 spent on Claude Code (from title)
- 110 comments on post

**Novelty:** Emerging practice: the observation that context reconstruction dominates token usage in code-understanding tasks is not widely discussed, but the solution (structured graph-based context pre-loading) represents an incremental optimization of existing MCP patterns rather than a novel architecture.

## Counterarguments
- No independent verification of benchmarks; results are single-user case studies without controlled methodology or reproduction by others.
- Comment from u/MonkEqual asks if tool is 'available publicly,' implying uncertainty about accessibility despite post claiming it's 'free to use.'
- No discussion of setup overhead or complexity costs—GrapeRoot requires code graph initialization and integration, which may offset token savings for small projects or one-off tasks.
- Comparison lacks detail on whether normal Claude and MCP versions used identical prompts and task definitions.

---

# I open-sourced what I built:

Free Tool: [https://grape-root.vercel.app](https://grape-root.vercel.app)  
Github Repo: [https://github.com/kunal12203/Codex-CLI-Compact](https://github.com/kunal12203/Codex-CLI-Compact)  
Discord(debugging/feedback): [https://discord.gg/xe7Hr5Dx](https://discord.gg/xe7Hr5Dx)

I’ve been using Claude Code heavily for the past few months and kept hitting the usage limit way faster than expected.

At first I thought: “okay, maybe my prompts are too big”

But then I started digging into token usage.

# What I noticed

Even for simple questions like: “Why is auth flow depending on this file?”

Claude would:

* grep across the repo
* open multiple files
* follow dependencies
* re-read the same files again next turn

That single flow was costing **\~20k–30k tokens**.

And the worst part: Every follow-up → it does the same thing again.

# I tried fixing it with [claude.md](http://claude.md/)

Spent a full day tuning instructions.

It helped… but:

* still re-reads a lot
* not reusable across projects
* resets when switching repos

So it didn’t fix the root problem.

# The actual issue:

Most token usage isn’t reasoning. It’s **context reconstruction**.  
Claude keeps rediscovering the same code every turn.

So I built an free to use MCP tool GrapeRoot

Basically a layer between your repo and Claude.

Instead of letting Claude explore every time, it:

* builds a graph of your code (functions, imports, relationships)
* tracks what’s already been read
* pre-loads only relevant files into the prompt
* avoids re-reading the same stuff again

# Results (my benchmarks)

Compared:

* normal Claude
* MCP/tool-based graph (my earlier version)
* pre-injected context (current)

What I saw:

* **\~45% cheaper on average**
* **up to 80–85% fewer tokens** on complex tasks
* **fewer turns** (less back-and-forth searching)
* better answers on harder problems

# Interesting part

I expected cost savings.

But, Starting with the *right context* actually improv

[Truncated]

## Top Comments

**u/MonkEqual** (9 pts):
> Have you made it available publicly? As, I'm having same problem with lots of token wastage on repeated context understanding.
