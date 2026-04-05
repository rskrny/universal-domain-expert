/**
 * Flip Side Lark Bridge v2.1
 *
 * Handles: webhook, MCP, REST, cron, and now direct briefing submission.
 * The /briefing endpoint lets the daily trigger POST content directly
 * without needing the Cloudflare MCP connector.
 */

interface Env {
  DB: D1Database
  LARK_APP_ID: string
  LARK_APP_SECRET: string
  LARK_CHAT_ID: string
  LARK_VERIFICATION_TOKEN: string
  MINIMAX_API_KEY: string
  ANTHROPIC_API_KEY: string
  AUTH_TOKEN: string
}

// --- Lark Auth ---

async function getLarkToken(env: Env): Promise<string> {
  const res = await fetch(
    "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        app_id: env.LARK_APP_ID,
        app_secret: env.LARK_APP_SECRET,
      }),
    }
  )
  const data: any = await res.json()
  if (data.code !== 0) throw new Error(`Lark auth failed: ${data.msg}`)
  return data.tenant_access_token
}

async function sendLarkMessage(
  env: Env,
  text: string,
  msgType = "text",
  chatId?: string
): Promise<{ success: boolean; message: string }> {
  const token = await getLarkToken(env)
  const targetChat = chatId || env.LARK_CHAT_ID

  let content: string
  if (msgType === "interactive") {
    content = JSON.stringify({
      config: { wide_screen_mode: true },
      header: {
        title: { tag: "plain_text", content: "The Flip Side Daily Briefing" },
        template: "blue",
      },
      elements: [
        {
          tag: "markdown",
          content: text.replace(/\\n/g, "\n").slice(0, 30000),
        },
      ],
    })
  } else {
    content = JSON.stringify({ text: text.replace(/\\n/g, "\n") })
  }

  const res = await fetch(
    "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        receive_id: targetChat,
        msg_type: msgType === "interactive" ? "interactive" : "text",
        content,
      }),
    }
  )
  const result: any = await res.json()
  if (result.code !== 0) {
    return { success: false, message: `Lark API error: ${result.msg}` }
  }
  return { success: true, message: "Message sent" }
}

async function replyToLarkMessage(env: Env, messageId: string, text: string) {
  const token = await getLarkToken(env)
  await fetch(
    `https://open.larksuite.com/open-apis/im/v1/messages/${messageId}/reply`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        msg_type: "text",
        content: JSON.stringify({ text }),
      }),
    }
  )
}

// --- Message Classification ---

function classifyMessage(text: string): {
  intent: string
  tier: string
  lang: string
} {
  const lower = text.toLowerCase().trim()
  const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length
  const lang =
    chineseChars / Math.max(text.length, 1) > 0.3 ? "cn" : "en"

  const patterns: Record<string, RegExp[]> = {
    STATUS: [/\bstatus\b/, /\bprogress\b/, /\bupdate\b/, /\bwhere are we\b/],
    BRIEFING: [/\bbriefing\b/, /\bbrief\b/, /\btrending\b/, /\bnews\b/],
    TEAM: [/\bteam\b/, /\bwho\b/, /\bjinfeng\b/, /\bchris\b/, /\beditor\b/],
    DECISION: [/\bdecision\b/, /\bpending\b/, /\bapprove\b/],
    SEARCH: [/\bfind\b/, /\bsearch\b/],
    HELP: [/\bhelp\b/, /\bwhat can you\b/],
  }

  let bestIntent = "GENERAL"
  let bestScore = 0
  for (const [intent, regexes] of Object.entries(patterns)) {
    let score = 0
    for (const rx of regexes) {
      if (rx.test(lower)) score++
    }
    if (score > bestScore) {
      bestScore = score
      bestIntent = intent
    }
  }

  const localIntents = ["STATUS", "TEAM", "DECISION", "HELP", "BRIEFING"]
  const tier = localIntents.includes(bestIntent) ? "local" : "minimax"
  return { intent: bestIntent, tier, lang }
}

// --- Local Responses ---

function getLocalResponse(intent: string, lang: string): string {
  const responses: Record<string, Record<string, string>> = {
    STATUS: {
      en: `Project Status:\n\n• EP-001: In editing. 4 decisions pending.\n• EP-002: Recorded. Ready for editing.\n• Intelligence Bot: Active. Daily briefings at 6:57 AM CST.\n• Editor transition: Jinfeng taking over all editing.\n\nSay "briefing" for today's trending topics.`,
      cn: "\u9879\u76EE\u72B6\u6001\uFF1A\n\n\u2022 EP-001\uFF1A\u526A\u8F91\u4E2D\u30024\u4E2A\u5F85\u5B9A\u51B3\u7B56\u3002\n\u2022 EP-002\uFF1A\u5DF2\u5F55\u5236\uFF0C\u7B49\u5F85\u526A\u8F91\u3002\n\u2022 \u60C5\u62A5\u673A\u5668\u4EBA\uFF1A\u5DF2\u6FC0\u6D3B\u3002",
    },
    TEAM: {
      en: "Team:\n\n• Chris Sun — Host/Boss\n• Annabelle Zhao — VP\n• Ryan Kearney — Overseas Ops\n• Yang Jinfeng — Editor ⚠️ Leaving ~June 2026\n• Zhang Lei — Video editor (EP-001 only)",
      cn: "Team:\n\n\u2022 Chris Sun\n\u2022 Annabelle Zhao \u2014 VP\n\u2022 Ryan Kearney\n\u2022 Yang Jinfeng \u2014 Editor",
    },
    HELP: {
      en: `I can help with:\n\n• "status" — Project state\n• "briefing" — Today's trending topics\n• "team" — Team roster\n• "decisions" — Open decisions\n• Or ask anything.`,
      cn: "Available commands: status, briefing, team, decisions",
    },
  }
  return (
    responses[intent]?.[lang] ||
    responses[intent]?.["en"] ||
    `Try "help" to see what I can do.`
  )
}

// --- AI Backends ---

async function getLatestBriefing(env: Env): Promise<string> {
  try {
    const row: any = await env.DB.prepare(
      "SELECT date, content FROM briefings ORDER BY id DESC LIMIT 1"
    ).first()
    if (!row) return "No briefings yet. The daily bot runs at 6:57 AM CST."
    return `Latest briefing (${row.date}):\n\n${row.content.slice(0, 3500)}`
  } catch {
    return "Couldn't load the latest briefing."
  }
}

async function callMiniMax(
  env: Env,
  userMessage: string,
  lang: string
): Promise<string> {
  const systemPrompt =
    lang === "cn"
      ? "You are The Flip Side podcast AI assistant. Reply in Chinese, concise."
      : "You are the AI assistant for The Flip Side podcast. Be concise and helpful."
  try {
    const res = await fetch(
      "https://api.minimaxi.com/v1/text/chatcompletion_v2",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.MINIMAX_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "MiniMax-Text-01",
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userMessage },
          ],
          max_tokens: 1000,
          temperature: 0.7,
        }),
      }
    )
    const data: any = await res.json()
    return (
      data.choices?.[0]?.message?.content ||
      `MiniMax error: ${data.base_resp?.status_msg || "Unknown"}`
    )
  } catch (e: any) {
    return `MiniMax call failed: ${e.message}`
  }
}

async function callClaude(env: Env, userMessage: string): Promise<string> {
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6-20250514",
        max_tokens: 2000,
        system:
          "You are the AI assistant for The Flip Side podcast. Be concise and insightful.",
        messages: [{ role: "user", content: userMessage }],
      }),
    })
    const data: any = await res.json()
    return data.content?.[0]?.text || `Claude error: ${data.error?.message}`
  } catch (e: any) {
    return `Claude call failed: ${e.message}`
  }
}

// --- Webhook Handler ---

async function handleWebhook(
  request: Request,
  env: Env,
  ctx: ExecutionContext
): Promise<Response> {
  const body: any = await request.json()

  if (body.challenge) {
    return new Response(JSON.stringify({ challenge: body.challenge }), {
      headers: { "Content-Type": "application/json" },
    })
  }

  const token = body.header?.token || body.token
  if (env.LARK_VERIFICATION_TOKEN && token !== env.LARK_VERIFICATION_TOKEN) {
    return new Response("Invalid token", { status: 403 })
  }

  const eventType = body.header?.event_type || body.type
  if (eventType !== "im.message.receive_v1") {
    return new Response("OK", { status: 200 })
  }

  const message = body.event?.message
  if (!message || message.message_type !== "text") {
    return new Response("OK", { status: 200 })
  }

  let userText: string
  try {
    const parsed = JSON.parse(message.content)
    userText = parsed.text.replace(/@_user_\w+/g, "").trim()
  } catch {
    return new Response("OK", { status: 200 })
  }

  if (!userText) return new Response("OK", { status: 200 })

  const chatId = message.chat_id
  const messageId = message.message_id

  ctx.waitUntil(processAndReply(env, userText, chatId, messageId))
  return new Response("OK", { status: 200 })
}

async function processAndReply(
  env: Env,
  userText: string,
  chatId: string,
  messageId: string
) {
  const { intent, tier, lang } = classifyMessage(userText)
  await replyToLarkMessage(
    env,
    messageId,
    lang === "cn" ? "Processing..." : "Got it, working on it..."
  )

  let response: string
  if (intent === "BRIEFING") {
    response = await getLatestBriefing(env)
  } else if (tier === "local") {
    response = getLocalResponse(intent, lang)
  } else {
    const needsClaude =
      /\b(research|analyze|strategy|plan|episode idea|deep dive|compare)\b/i.test(
        userText
      )
    if (needsClaude && env.ANTHROPIC_API_KEY) {
      response = await callClaude(env, userText)
    } else if (env.MINIMAX_API_KEY) {
      response = await callMiniMax(env, userText, lang)
    } else {
      response = "I need an LLM API key to answer general questions."
    }
  }

  await sendLarkMessage(env, response, "text", chatId)
}

// --- Cron: Deliver undelivered briefings ---

async function processUndeliveredBriefings(env: Env) {
  const rows = await env.DB.prepare(
    "SELECT id, content FROM briefings WHERE delivered = 0 ORDER BY id ASC"
  ).all()

  if (!rows.results || rows.results.length === 0) return

  for (const row of rows.results) {
    const { id, content } = row as { id: number; content: string }
    try {
      const result = await sendLarkMessage(env, content, "interactive")
      if (result.success) {
        await env.DB.prepare(
          "UPDATE briefings SET delivered = 1 WHERE id = ?"
        )
          .bind(id)
          .run()
        console.log(`Briefing ${id} delivered`)
      } else {
        console.error(`Briefing ${id} failed: ${result.message}`)
      }
    } catch (e: any) {
      console.error(`Briefing ${id} error: ${e.message}`)
    }
  }
}

// --- MCP Handler ---

function jsonRpcResponse(id: any, result: any) {
  return { jsonrpc: "2.0", id, result }
}

function jsonRpcError(id: any, code: number, message: string) {
  return { jsonrpc: "2.0", id, error: { code, message } }
}

async function handleMcpRequest(req: any, env: Env) {
  switch (req.method) {
    case "initialize":
      return jsonRpcResponse(req.id, {
        protocolVersion: "2024-11-05",
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "flipside-lark-bridge", version: "2.1.0" },
      })
    case "notifications/initialized":
      return null
    case "tools/list":
      return jsonRpcResponse(req.id, {
        tools: [
          {
            name: "send_lark_message",
            description:
              "Send a message to The Flip Side team Lark group chat.",
            inputSchema: {
              type: "object",
              properties: {
                text: { type: "string", description: "Message content." },
                format: {
                  type: "string",
                  enum: ["text", "card"],
                  description: "Default: card.",
                },
              },
              required: ["text"],
            },
          },
        ],
      })
    case "tools/call": {
      const params = req.params
      if (params.name !== "send_lark_message") {
        return jsonRpcError(req.id, -32602, `Unknown tool: ${params.name}`)
      }
      const msgType =
        (params.arguments.format || "card") === "card" ? "interactive" : "text"
      try {
        const result = await sendLarkMessage(env, params.arguments.text, msgType)
        return jsonRpcResponse(req.id, {
          content: [{ type: "text", text: result.message }],
          isError: !result.success,
        })
      } catch (e: any) {
        return jsonRpcResponse(req.id, {
          content: [{ type: "text", text: `Error: ${e.message}` }],
          isError: true,
        })
      }
    }
    default:
      return jsonRpcError(req.id, -32601, `Method not found: ${req.method}`)
  }
}

// --- Main Export ---

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url)

    // Health check
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "flipside-lark-bridge",
          version: "2.1.0",
          capabilities: ["webhook", "mcp", "rest", "cron", "briefing"],
        }),
        { headers: { "Content-Type": "application/json" } }
      )
    }

    // Webhook
    if (url.pathname === "/webhook" && request.method === "POST") {
      return handleWebhook(request, env, ctx)
    }

    // MCP
    if (url.pathname === "/mcp" && request.method === "POST") {
      const body = await request.json()
      const result = await handleMcpRequest(body, env)
      if (result === null) return new Response(null, { status: 202 })
      return new Response(JSON.stringify(result), {
        headers: { "Content-Type": "application/json" },
      })
    }

    // REST: Send message (authenticated)
    if (url.pathname === "/send" && request.method === "POST") {
      const authHeader = request.headers.get("Authorization")
      if (authHeader !== `Bearer ${env.AUTH_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 })
      }
      const { text, format }: { text: string; format?: string } =
        await request.json()
      if (!text) {
        return new Response(JSON.stringify({ error: "Missing 'text'" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        })
      }
      try {
        const result = await sendLarkMessage(
          env,
          text,
          format === "text" ? "text" : "interactive"
        )
        return new Response(JSON.stringify(result), {
          headers: { "Content-Type": "application/json" },
        })
      } catch (e: any) {
        return new Response(
          JSON.stringify({ success: false, message: e.message }),
          { status: 500, headers: { "Content-Type": "application/json" } }
        )
      }
    }

    // NEW: Direct briefing submission endpoint
    // The daily trigger POSTs here. No Cloudflare connector needed.
    if (url.pathname === "/briefing" && request.method === "POST") {
      try {
        const { content, date }: { content: string; date?: string } =
          await request.json()

        if (!content) {
          return new Response(
            JSON.stringify({ error: "Missing 'content'" }),
            { status: 400, headers: { "Content-Type": "application/json" } }
          )
        }

        const briefingDate =
          date || new Date().toISOString().split("T")[0]

        // Write to D1
        const dbResult = await env.DB.prepare(
          "INSERT INTO briefings (date, content, delivered) VALUES (?, ?, 0)"
        )
          .bind(briefingDate, content)
          .run()

        // Immediately send to Lark as a card
        const larkResult = await sendLarkMessage(env, content, "interactive")

        // Mark as delivered if Lark send succeeded
        if (larkResult.success && dbResult.meta.last_row_id) {
          await env.DB.prepare(
            "UPDATE briefings SET delivered = 1 WHERE id = ?"
          )
            .bind(dbResult.meta.last_row_id)
            .run()
        }

        return new Response(
          JSON.stringify({
            success: true,
            briefing_id: dbResult.meta.last_row_id,
            d1_written: true,
            lark_sent: larkResult.success,
            date: briefingDate,
          }),
          { headers: { "Content-Type": "application/json" } }
        )
      } catch (e: any) {
        return new Response(
          JSON.stringify({ success: false, error: e.message }),
          { status: 500, headers: { "Content-Type": "application/json" } }
        )
      }
    }

    // Get latest briefing
    if (url.pathname === "/briefing" && request.method === "GET") {
      try {
        const row: any = await env.DB.prepare(
          "SELECT id, date, content, delivered, created_at FROM briefings ORDER BY id DESC LIMIT 1"
        ).first()
        return new Response(JSON.stringify(row || { error: "No briefings" }), {
          headers: { "Content-Type": "application/json" },
        })
      } catch (e: any) {
        return new Response(
          JSON.stringify({ error: e.message }),
          { status: 500, headers: { "Content-Type": "application/json" } }
        )
      }
    }

    // Recall/delete a message
    if (url.pathname === "/api/recall" && request.method === "POST") {
      const authHeader = request.headers.get("Authorization")
      if (authHeader !== `Bearer ${env.AUTH_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 })
      }

      const body: any = await request.json()
      const messageId = body.message_id
      if (!messageId) {
        return new Response(JSON.stringify({ error: "message_id required" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        })
      }

      try {
        const token = await getLarkToken(env)
        const res = await fetch(
          `https://open.larksuite.com/open-apis/im/v1/messages/${messageId}`,
          {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
          }
        )
        const data: any = await res.json()
        return new Response(JSON.stringify({ success: data.code === 0, data }), {
          headers: { "Content-Type": "application/json" },
        })
      } catch (e: any) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        })
      }
    }

    return new Response("Not found", { status: 404 })
  },

  // Cron handler
  async scheduled(
    _event: ScheduledEvent,
    env: Env,
    _ctx: ExecutionContext
  ) {
    await processUndeliveredBriefings(env)
  },
}
