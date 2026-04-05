# I bought 200$ claude code so you don't have to :)

Source: https://reddit.comhttps://reddit.com/r/OpenSourceeAI/comments/1rxgwjx/i_bought_200_claude_code_so_you_dont_have_to/
Subreddit: r/OpenSourceeAI | Score: 662 | Date: 2026-03-18

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

But, Starting with the *right context* actually improves answer quality.

Less searching → more reasoning.

Curious if others are seeing this too:

* hitting limits faster than expected?
* sessions feeling like they keep restarting?
* annoyed by repeated repo scanning?

Would love to hear how others are dealing with this.

## Top Comments

**u/MonkEqual** (9 pts):
> Have you made it available publicly? As, I'm having same problem with lots of token wastage on repeated context understanding.
