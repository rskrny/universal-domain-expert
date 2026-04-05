/**
 * Brain Feed Webhook Handler
 *
 * Receives Lark DMs from the Brain Feed bot, extracts content from links,
 * summarizes with Claude, and writes knowledge chunks to D1.
 *
 * Flow:
 * 1. Lark sends webhook event when user DMs the bot
 * 2. Worker parses message text and extracts URLs
 * 3. For URLs: fetch page, extract text, summarize with Claude
 * 4. For plain text: store directly as knowledge chunk
 * 5. Write to D1 brainfeed-knowledge database
 * 6. Reply to user confirming ingestion
 */

interface Env {
  DB: D1Database
  LARK_APP_ID: string
  LARK_APP_SECRET: string
  LARK_VERIFICATION_TOKEN: string
  LARK_CHAT_ID: string
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

async function replyToMessage(env: Env, messageId: string, text: string) {
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

// --- URL Detection & Content Extraction ---

function extractUrls(text: string): string[] {
  const urlRegex = /https?:\/\/[^\s<>"{}|\\^`\[\]]+/gi
  return text.match(urlRegex) || []
}

async function fetchPageContent(url: string): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "BrainFeed/1.0 (Knowledge Ingestion Bot)",
        Accept: "text/html,application/xhtml+xml,text/plain",
      },
      redirect: "follow",
    })
    if (!res.ok) return `[Failed to fetch: ${res.status}]`

    const contentType = res.headers.get("content-type") || ""
    const text = await res.text()

    if (contentType.includes("text/html")) {
      // Strip HTML tags, scripts, styles. Keep text content.
      return text
        .replace(/<script[\s\S]*?<\/script>/gi, "")
        .replace(/<style[\s\S]*?<\/style>/gi, "")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 15000)
    }

    return text.slice(0, 15000)
  } catch (e: any) {
    return `[Fetch error: ${e.message}]`
  }
}

// --- Claude Summarization ---

async function summarizeWithClaude(
  env: Env,
  content: string,
  url: string
): Promise<{ title: string; summary: string; domain: string; tags: string[] }> {
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 500,
        messages: [
          {
            role: "user",
            content: `Analyze this web page content and return a JSON object with these fields:
- title: a clear, descriptive title (max 80 chars)
- summary: a 2-3 sentence summary of the key insights
- domain: the most relevant knowledge domain (e.g., "ai-machine-learning", "business-consulting", "software-dev")
- tags: array of 3-5 relevant tags

URL: ${url}

Content (first 8000 chars):
${content.slice(0, 8000)}

Return ONLY valid JSON, no markdown.`,
          },
        ],
      }),
    })

    const data: any = await res.json()
    const text = data.content?.[0]?.text || ""

    try {
      return JSON.parse(text)
    } catch {
      return {
        title: url.split("/").pop()?.slice(0, 80) || "Untitled",
        summary: text.slice(0, 300),
        domain: "general",
        tags: [],
      }
    }
  } catch (e: any) {
    return {
      title: url,
      summary: `Failed to summarize: ${e.message}`,
      domain: "general",
      tags: [],
    }
  }
}

// --- Knowledge Chunk Storage ---

async function storeChunk(
  db: D1Database,
  chunk: {
    source_url?: string
    source_type: string
    title: string
    content: string
    summary: string
    domain: string
    tags: string[]
  }
): Promise<number> {
  const result = await db
    .prepare(
      `INSERT INTO knowledge_chunks (source_url, source_type, title, content, summary, domain, tags, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, 'ready')`
    )
    .bind(
      chunk.source_url || null,
      chunk.source_type,
      chunk.title,
      chunk.content,
      chunk.summary,
      chunk.domain,
      JSON.stringify(chunk.tags)
    )
    .run()

  return result.meta.last_row_id
}

async function logIngestion(
  db: D1Database,
  messageId: string,
  senderId: string,
  rawText: string,
  processed: boolean,
  error?: string
) {
  await db
    .prepare(
      `INSERT INTO ingestion_log (message_id, sender_id, raw_text, processed, error)
       VALUES (?, ?, ?, ?, ?)`
    )
    .bind(messageId, senderId, rawText, processed ? 1 : 0, error || null)
    .run()
}

// --- Webhook Handler ---

async function handleWebhook(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const body: any = await request.json()

  // Lark verification challenge
  if (body.challenge) {
    return new Response(JSON.stringify({ challenge: body.challenge }), {
      headers: { "Content-Type": "application/json" },
    })
  }

  // Token verification
  const token = body.header?.token || body.token
  if (env.LARK_VERIFICATION_TOKEN && token !== env.LARK_VERIFICATION_TOKEN) {
    return new Response("Invalid token", { status: 403 })
  }

  // Only handle incoming messages
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

  const messageId = message.message_id
  const senderId = body.event?.sender?.sender_id?.open_id || "unknown"

  // Process asynchronously so Lark doesn't timeout
  ctx.waitUntil(processMessage(env, userText, messageId, senderId))

  return new Response("OK", { status: 200 })
}

async function processMessage(
  env: Env,
  userText: string,
  messageId: string,
  senderId: string
) {
  try {
    // Acknowledge receipt
    await replyToMessage(env, messageId, "Got it. Processing...")

    const urls = extractUrls(userText)
    const results: string[] = []

    if (urls.length > 0) {
      // Process each URL
      for (const url of urls.slice(0, 3)) {
        const pageContent = await fetchPageContent(url)
        const analysis = await summarizeWithClaude(env, pageContent, url)

        const chunkId = await storeChunk(env.DB, {
          source_url: url,
          source_type: "link",
          title: analysis.title,
          content: pageContent.slice(0, 10000),
          summary: analysis.summary,
          domain: analysis.domain,
          tags: analysis.tags,
        })

        results.push(`Indexed: "${analysis.title}" [${analysis.domain}] (id:${chunkId})`)
      }

      // Also store any non-URL text as context
      const plainText = userText.replace(/https?:\/\/[^\s]+/g, "").trim()
      if (plainText.length > 10) {
        await storeChunk(env.DB, {
          source_type: "note",
          title: plainText.slice(0, 80),
          content: plainText,
          summary: plainText.slice(0, 200),
          domain: "general",
          tags: ["brain-feed", "note"],
        })
        results.push(`Note saved: "${plainText.slice(0, 50)}..."`)
      }
    } else {
      // Pure text input. Store as knowledge note.
      const chunkId = await storeChunk(env.DB, {
        source_type: "note",
        title: userText.slice(0, 80),
        content: userText,
        summary: userText.slice(0, 200),
        domain: "general",
        tags: ["brain-feed", "note"],
      })
      results.push(`Note saved (id:${chunkId}): "${userText.slice(0, 50)}..."`)
    }

    await logIngestion(env.DB, messageId, senderId, userText, true)
    await replyToMessage(env, messageId, results.join("\n"))
  } catch (e: any) {
    await logIngestion(env.DB, messageId, senderId, userText, false, e.message)
    await replyToMessage(env, messageId, `Error processing: ${e.message}`)
  }
}

// --- API Endpoints ---

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url)

    // Health check
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "brainfeed-webhook",
          version: env.WORKER_VERSION || "1.0.0",
        }),
        { headers: { "Content-Type": "application/json" } }
      )
    }

    // Lark webhook endpoint
    if (url.pathname === "/webhook" && request.method === "POST") {
      return handleWebhook(request, env, ctx)
    }

    // REST API: list recent chunks
    if (url.pathname === "/api/chunks" && request.method === "GET") {
      const limit = parseInt(url.searchParams.get("limit") || "20")
      const rows = await env.DB.prepare(
        "SELECT id, source_url, source_type, title, summary, domain, tags, created_at FROM knowledge_chunks ORDER BY id DESC LIMIT ?"
      )
        .bind(Math.min(limit, 100))
        .all()

      return new Response(JSON.stringify(rows.results), {
        headers: { "Content-Type": "application/json" },
      })
    }

    // REST API: get pending chunks for sync
    if (url.pathname === "/api/chunks/pending" && request.method === "GET") {
      const rows = await env.DB.prepare(
        "SELECT * FROM knowledge_chunks WHERE synced_at IS NULL ORDER BY id ASC LIMIT 50"
      ).all()

      return new Response(JSON.stringify(rows.results), {
        headers: { "Content-Type": "application/json" },
      })
    }

    // REST API: mark chunks as synced
    if (url.pathname === "/api/chunks/synced" && request.method === "POST") {
      const authHeader = request.headers.get("Authorization")
      if (authHeader !== `Bearer ${env.AUTH_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 })
      }

      const { ids }: { ids: number[] } = await request.json()
      if (ids && ids.length > 0) {
        const placeholders = ids.map(() => "?").join(",")
        await env.DB.prepare(
          `UPDATE knowledge_chunks SET synced_at = CURRENT_TIMESTAMP WHERE id IN (${placeholders})`
        )
          .bind(...ids)
          .run()
      }

      return new Response(JSON.stringify({ synced: ids?.length || 0 }), {
        headers: { "Content-Type": "application/json" },
      })
    }

    // REST API: stats
    if (url.pathname === "/api/stats" && request.method === "GET") {
      const total = await env.DB.prepare("SELECT COUNT(*) as count FROM knowledge_chunks").first()
      const pending = await env.DB.prepare(
        "SELECT COUNT(*) as count FROM knowledge_chunks WHERE synced_at IS NULL"
      ).first()
      const byDomain = await env.DB.prepare(
        "SELECT domain, COUNT(*) as count FROM knowledge_chunks GROUP BY domain ORDER BY count DESC"
      ).all()

      return new Response(
        JSON.stringify({
          total_chunks: total?.count || 0,
          pending_sync: pending?.count || 0,
          by_domain: byDomain.results,
        }),
        { headers: { "Content-Type": "application/json" } }
      )
    }

    // Send a message to the Brain Feed group chat
    // Supports: text, interactive (cards), post (rich text), file, image
    if (url.pathname === "/send" && request.method === "POST") {
      const authHeader = request.headers.get("Authorization")
      if (authHeader !== `Bearer ${env.AUTH_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 })
      }

      const body: any = await request.json()
      const chatId = body.chat_id || env.LARK_CHAT_ID
      const format = body.format || "text" // text, card, post, file, image

      if (format === "card") {
        // Interactive card message
        // body.title, body.sections (array of {header, content} objects)
        // body.color: "blue"|"green"|"red"|"orange"|"purple"
        const title = body.title || "Brain Feed"
        const sections = body.sections || []
        const headerColor = body.color || "blue"

        const elements: any[] = []
        for (const section of sections) {
          if (section.header) {
            elements.push({
              tag: "markdown",
              content: `**${section.header}**`,
            })
          }
          if (section.content) {
            elements.push({
              tag: "markdown",
              content: section.content,
            })
          }
          if (section.divider) {
            elements.push({ tag: "hr" })
          }
        }

        const card = {
          config: { wide_screen_mode: true },
          header: {
            title: { tag: "plain_text", content: title },
            template: headerColor,
          },
          elements,
        }

        try {
          const token = await getLarkToken(env)
          const res = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json; charset=utf-8",
              },
              body: JSON.stringify({
                receive_id: chatId,
                msg_type: "interactive",
                content: JSON.stringify(card),
              }),
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
      } else if (format === "post") {
        // Rich text post message (supports bold, links, etc.)
        // body.title (string), body.content (array of arrays of tag objects)
        // Each inner array is a paragraph. Tag objects: {tag:"text",text:"..."}, {tag:"a",text:"...",href:"..."}, {tag:"b",text:"..."}
        const title = body.title || ""
        const contentLines = body.content || []

        const post = {
          en_us: {
            title,
            content: contentLines,
          },
        }

        try {
          const token = await getLarkToken(env)
          const res = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json; charset=utf-8",
              },
              body: JSON.stringify({
                receive_id: chatId,
                msg_type: "post",
                content: JSON.stringify(post),
              }),
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
      } else if (format === "file") {
        // File message (opus, mp4, pdf, doc, xls, ppt, stream)
        // body.file_content (base64), body.file_name, body.file_type
        const fileContent = body.file_content
        const fileName = body.file_name
        const fileType = body.file_type // opus, mp4, pdf, doc, xls, ppt, stream
        if (!fileContent || !fileName || !fileType) {
          return new Response(
            JSON.stringify({ error: "file_content, file_name, and file_type are required" }),
            { status: 400, headers: { "Content-Type": "application/json" } }
          )
        }

        try {
          const token = await getLarkToken(env)

          // Decode base64 to binary
          const binaryStr = atob(fileContent)
          const bytes = new Uint8Array(binaryStr.length)
          for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i)
          }

          // Upload file to Lark
          const formData = new FormData()
          formData.append("file_type", fileType)
          formData.append("file_name", fileName)
          formData.append("file", new Blob([bytes]), fileName)

          const uploadRes = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/files",
            {
              method: "POST",
              headers: { Authorization: `Bearer ${token}` },
              body: formData,
            }
          )
          const uploadData: any = await uploadRes.json()
          if (uploadData.code !== 0) {
            return new Response(
              JSON.stringify({ error: `File upload failed: ${uploadData.msg}`, data: uploadData }),
              { status: 500, headers: { "Content-Type": "application/json" } }
            )
          }

          const fileKey = uploadData.data?.file_key
          if (!fileKey) {
            return new Response(
              JSON.stringify({ error: "No file_key returned from upload", data: uploadData }),
              { status: 500, headers: { "Content-Type": "application/json" } }
            )
          }

          // Send file message
          const res = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json; charset=utf-8",
              },
              body: JSON.stringify({
                receive_id: chatId,
                msg_type: "file",
                content: JSON.stringify({ file_key: fileKey }),
              }),
            }
          )
          const data: any = await res.json()
          return new Response(JSON.stringify({ success: data.code === 0, file_key: fileKey, data }), {
            headers: { "Content-Type": "application/json" },
          })
        } catch (e: any) {
          return new Response(JSON.stringify({ error: e.message }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        }
      } else if (format === "image") {
        // Image message
        // body.image_content (base64), body.file_name (optional)
        const imageContent = body.image_content
        if (!imageContent) {
          return new Response(
            JSON.stringify({ error: "image_content is required" }),
            { status: 400, headers: { "Content-Type": "application/json" } }
          )
        }

        const imageName = body.file_name || "image.png"

        try {
          const token = await getLarkToken(env)

          // Decode base64 to binary
          const binaryStr = atob(imageContent)
          const bytes = new Uint8Array(binaryStr.length)
          for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i)
          }

          // Upload image to Lark
          const formData = new FormData()
          formData.append("image_type", "message")
          formData.append("image", new Blob([bytes]), imageName)

          const uploadRes = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/images",
            {
              method: "POST",
              headers: { Authorization: `Bearer ${token}` },
              body: formData,
            }
          )
          const uploadData: any = await uploadRes.json()
          if (uploadData.code !== 0) {
            return new Response(
              JSON.stringify({ error: `Image upload failed: ${uploadData.msg}`, data: uploadData }),
              { status: 500, headers: { "Content-Type": "application/json" } }
            )
          }

          const imageKey = uploadData.data?.image_key
          if (!imageKey) {
            return new Response(
              JSON.stringify({ error: "No image_key returned from upload", data: uploadData }),
              { status: 500, headers: { "Content-Type": "application/json" } }
            )
          }

          // Send image message
          const res = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json; charset=utf-8",
              },
              body: JSON.stringify({
                receive_id: chatId,
                msg_type: "image",
                content: JSON.stringify({ image_key: imageKey }),
              }),
            }
          )
          const data: any = await res.json()
          return new Response(JSON.stringify({ success: data.code === 0, image_key: imageKey, data }), {
            headers: { "Content-Type": "application/json" },
          })
        } catch (e: any) {
          return new Response(JSON.stringify({ error: e.message }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        }
      } else {
        // Plain text message
        const text = body.text || ""
        if (!text) {
          return new Response(JSON.stringify({ error: "text is required" }), {
            status: 400,
            headers: { "Content-Type": "application/json" },
          })
        }

        try {
          const token = await getLarkToken(env)
          const res = await fetch(
            "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json; charset=utf-8",
              },
              body: JSON.stringify({
                receive_id: chatId,
                msg_type: "text",
                content: JSON.stringify({ text }),
              }),
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
    }

    // List chats the bot is in (for finding the correct chat_id)
    if (url.pathname === "/api/chats" && request.method === "GET") {
      const authHeader = request.headers.get("Authorization")
      if (authHeader !== `Bearer ${env.AUTH_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 })
      }

      try {
        const token = await getLarkToken(env)
        const res = await fetch(
          "https://open.larksuite.com/open-apis/im/v1/chats?page_size=50",
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        )
        const data: any = await res.json()
        return new Response(JSON.stringify(data), {
          headers: { "Content-Type": "application/json" },
        })
      } catch (e: any) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        })
      }
    }

    // Recall/delete a message (for retracting accidental sends)
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
}
