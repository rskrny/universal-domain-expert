# What actually worked for me after failing to maintain 12 Al-driven projects

Source: https://reddit.com/r/vibecoding/comments/1prbqbi/what_actually_worked_for_me_after_failing_to/
Subreddit: r/vibecoding | Score: 24 | Date: 2025-12-20
Engagement: 0.598 | Practical Value: high

## Extracted Claims

**Claim 1:** Upfront architectural planning using Claude Opus in plan mode before implementation prevents project abandonment and reduces maintenance burden across multiple projects.
- Evidence: anecdote (confidence: 0.65)
- Details: Author attributes failure to maintain 12 projects to 'bad infrastructure and zero upfront planning.' Now creates detailed workplans covering tech stack, database modeling, architecture patterns, design systems, security, tests, and documentation before writing code. Claims this single change enabled a 4x speed increase and sustainable project maintenance.

**Claim 2:** Using MCPs (Model Context Protocol) with specialized tools like Supabase MCP and Notion MCP achieves 90-95% accuracy for direct database migrations and transforms AI from conversational tool to project execution engine.
- Evidence: anecdote (confidence: 0.6)
- Details: Author reports Supabase MCP enables agents to push migrations with '~90–95% accuracy' without manual intervention. Combined with Notion MCP for task tracking and Vercel MCP for deployment, this creates an automated workflow rather than manual code generation and copy-paste.

**Claim 3:** Mirroring code-first design system structure into Figma enables Cursor to recognize components as structurally identical, reducing translation friction between design and implementation.
- Evidence: anecdote (confidence: 0.55)
- Details: Author states that using Figma MCP works 'extremely well' when the design system is 'originally created in code' and 'the same structure was mirrored into Figma,' allowing 'Cursor basically sees it as the same component with different styling.' This approach reduces design-to-code iteration loops.

## Key Data Points
- 4x speed increase in project delivery
- 90-95% accuracy for Supabase MCP migrations
- 12 failed projects (baseline failure case)
- Claude Opus 4.5 and Sonnet 4.5 model tiers used

**Novelty:** Emerging practice: systematic use of MCPs and upfront architectural planning with LLMs is becoming common in AI-assisted development, but the specific workflow and benchmarks (4x speed increase, 90-95% migration accuracy) represent concrete process optimization beyond generic 'use AI for coding' advice.

## Counterarguments
- Top comment from u/Mitija006 requests elaboration on Figma workflow, suggesting the explanation provided may be unclear or incomplete for practical replication.
- No comments validate the claimed 4x speed improvement or 90-95% MCP accuracy rates, limiting external verification.
- The workflow relies on Claude 3.5 Sonnet, Opus 4.5, and multiple paid MCPs/integrations, making cost-effectiveness unclear despite speed claims.

---

I’ve been “vibe coding” in a very different way lately, and it completely changed how I build products.

Background: I’m a product designer with a computer science degree. I used to spend insane amounts of time on research, moodboards, mocks, prototypes, and endless iteration loops. Keeping multiple projects alive was basically impossible.

Today I’m seeing something like a 4x speed increase, mostly because I stopped treating AI as a “code generator” and started treating it as part of my system.

**Here’s the workflow that actually works for me.**

High-level thinking first (this part matters a lot)

I start every project in ChatGPT (5.2) and stay there until the idea is very clear:

What the product is

What it is not

Core flows

Constraints

Tradeoffs

I keep everything in the same chat so the context locks in my vision. This alone removes a ton of confusion later.

Once the idea is clear, I create a blank project folder and open it in Cursor. Before writing real code, I build a full workplan using plan mode with Claude Opus.

**This is the most important step.**

I learned this the hard way after failing to maintain around 12 projects due to bad infrastructure and zero upfront planning.

The workplan focuses on fundamentals:

Tech stack

Database and data modeling

Architecture and design patterns

Design system strategy

Security basics

Tests

Docs and rules

Docs and rules are not optional. They are not just for humans, they become agent context. This keeps the AI writing consistent code and stops it from reinventing patterns every time.

I also lock a methodology early (FSD, atomic, etc). No mixing later.

**First implementation with maximum context**

When the workplan is solid, I do the initial implementation with Claude Opus 4.5. The large context lets me cover the entire foundation in one shot, which saves time and money later by reducing rewrites.

After that, I push to GitHub, create a dev branch, and set up environments.

Once the base is stable, I st

[Truncated]

## Top Comments

**u/Mitija006** (6 pts):
> I don't understand exactly the workflow with figma. Can you elaborate?
