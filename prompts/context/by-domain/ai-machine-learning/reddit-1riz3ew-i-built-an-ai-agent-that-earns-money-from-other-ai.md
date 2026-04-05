# I built an AI agent that earns money from other AI agents while I sleep

Source: https://reddit.com/r/mcp/comments/1riz3ew/i_built_an_ai_agent_that_earns_money_from_other/
Subreddit: r/mcp | Score: 285 | Date: 2026-03-02
Engagement: 0.783 | Practical Value: medium

## Extracted Claims

**Claim 1:** AI agents can discover and transact with specialized microservices through machine-readable protocols (MCP, OpenAPI, A2A) without human intervention, enabling autonomous agent-to-agent commerce at scale.
- Evidence: tutorial (confidence: 0.7)
- Details: The post demonstrates a working proof-of-concept data transformation service discoverable via MCP directories, Google A2A agent cards, and OpenAPI specs. Payment flows automatically through x402 protocol using USDC on Base blockchain. However, this is a single implementation and adoption remains early-stage; the claim about ecosystem viability is partially unproven.

**Claim 2:** Micro-transaction pricing ($0.001-0.005 per API call) can become viable revenue at scale (1M requests/day = $1,000/day) when deployed on serverless infrastructure with zero idle costs.
- Evidence: opinion (confidence: 0.6)
- Details: The post projects revenue based on volume math rather than demonstrated traction. Deployment on Fly.io with scale-to-zero is technically sound, but the actual request volume to generate stated revenue is hypothetical. No data on current usage is provided.

**Claim 3:** MCP protocol adoption for agent discovery and Google A2A are sufficiently mature to support automated agent-to-agent service discovery without human configuration.
- Evidence: opinion (confidence: 0.5)
- Details: The post assumes agents can autonomously browse MCP directories and OpenAPI specs. Top comment directly questions this assumption: 'How do agents browse smithery, mcp.so etc? How do agents know they have to go to this marketplace?' This indicates the ecosystem discovery mechanism is not yet clearly defined or automated.

## Key Data Points
- 43+ format pair conversions supported
- 100 free requests per agent threshold
- $0.001-0.005 per conversion
- $1,000/day projected revenue at 1M requests/day
- sub-50ms conversion latency

**Novelty:** Cutting-edge: autonomous agent-to-agent commerce with micropayments via blockchain is experimental infrastructure still lacking clear ecosystem discovery mechanisms and real-world adoption signals.

## Counterarguments
- Top comment exposes unclear agent discovery mechanism: agents do not yet autonomously browse MCP marketplaces; human configuration may still be required.
- No evidence of actual agent customers using the service or real transaction volume data provided.
- x402 payment protocol and Google A2A are described as 'brand new,' suggesting infrastructure immaturity and adoption risk.

---

I've been thinking a lot about the agent-to-agent economy, the idea that AI agents won't just serve humans, they'll hire each other. So I built a proof of concept: a data transformation agent that other AI agents can discover, use, and pay automatically. No website. No UI. No human in the loop.

What it does

It converts data between 43+ format pairs: JSON, CSV, XML, YAML, TOML, HTML, Markdown, PDF, Excel, DOCX, and more. It also reshapes nested JSON structures using dot-notation path mapping. Simple utility work that every agent dealing with data needs constantly.

How agents find it

There's no landing page. Agents discover it through machine-to-machine protocols:

MCP (Model Context Protocol) — so Claude, Cursor, Windsurf, and any MCP-compatible agent can find and call it

Google A2A — serves an agent card at /.well-known/agent-card.json

OpenAPI — any agent that reads OpenAPI specs can integrate

It's listed on Smithery, mcp.so, and other MCP directories. Agents browse these the way humans browse app stores.

How it gets paid

First 100 requests per agent are free. After that, it uses x402, an open payment protocol where the agent pays in USDC stablecoin on Base. The flow is fully automated:

Agent sends a request

Server returns HTTP 402 with payment requirements

Agent's wallet signs and sends $0.001-0.005 per conversion

Server verifies on-chain, serves the response

USDC lands in my wallet

No Stripe. No invoices. No payment forms. Machine pays machine.

The tech stack

FastAPI + orjson + polars for speed (sub-50ms for text conversions)

Deployed on Fly.io (scales to zero when idle, costs nothing when nobody's using it)

The thesis

I think we're heading toward a world where millions of specialized agents offer micro-services to each other. The agent that converts formats. The agent that validates data. The agent that runs code in a sandbox. Each one is simple, fast, and cheap. The money is in volume: $0.001 × 1 million requests/day = $1,000/day.

We're not 

[Truncated]

## Top Comments

**u/nimloman** (6 pts):
> This is cool. How do agents browse smithery, mcp.so etc? How do agents know they have to go to this marketplace for other agents? What is an example of agents that use your agent?

Would love to understand more about how the ecosystem works. I have created a few agents and mcps, and the agents use A2A protocol.
