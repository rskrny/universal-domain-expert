# I built an AI agent that earns money from other AI agents while I sleep

Source: https://reddit.comhttps://reddit.com/r/mcp/comments/1riz3ew/i_built_an_ai_agent_that_earns_money_from_other/
Subreddit: r/mcp | Score: 285 | Date: 2026-03-02

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

We're not there yet. MCP adoption is still early. x402 is brand new. But the infrastructure is ready, and I wanted to be one of the first agents in the network.

Try it

Add this to your MCP client config (Claude Desktop, Cursor, etc.):

{

  "mcpServers": {

"data-transform-agent": {

"url": "https://transform-agent.fly.dev/mcp"

}

  }

}

Or hit the REST API directly:

curl -X POST https://transform-agent.fly.dev/auth/provision \\

  \-H "Content-Type: application/json" -d '{}'

Source code is open: github.com/dashev88/transform-agent

Happy to answer questions about the architecture, the payment flow, or the A2A economy thesis.

## Top Comments

**u/nimloman** (6 pts):
> This is cool. How do agents browse smithery, mcp.so etc? How do agents know they have to go to this marketplace for other agents? What is an example of agents that use your agent?

Would love to understand more about how the ecosystem works. I have created a few agents and mcps, and the agents use A2A protocol.
