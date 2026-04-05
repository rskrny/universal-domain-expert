---
name: sync-brainfeed
description: Sync knowledge chunks from Brain Feed D1 to the local retrieval index
user_invocable: true
---

# Brain Feed Sync

Pulls pending knowledge chunks from the Brain Feed Cloudflare D1 database
and integrates them into the local retrieval index.

## Prerequisites

- Brain Feed webhook worker must be deployed (brainfeed.hanahaulers.com)
- AUTH_TOKEN must be available in `.env` as BRAINFEED_AUTH_TOKEN
- Local retrieval index must be built

## Execution Steps

1. **Fetch pending chunks.** Call the Brain Feed API:
   ```
   GET https://brainfeed.hanahaulers.com/api/chunks/pending
   ```
   This returns chunks that haven't been synced to the local index yet.

2. **Convert to local format.** For each chunk:
   - Write as a markdown file in `prompts/context/by-domain/{domain}/brainfeed_{id}.md`
   - Include frontmatter with source URL, tags, and creation date
   - If domain is "general", place in `prompts/context/shared/brainfeed/`

3. **Mark as synced.** Call:
   ```
   POST https://brainfeed.hanahaulers.com/api/chunks/synced
   Authorization: Bearer {AUTH_TOKEN}
   Body: {"ids": [1, 2, 3]}
   ```

4. **Reindex.** Run `python -m retrieval index` to pick up the new files.

5. **Report.** Show how many chunks were synced, by domain.

## Notes

- Run this at the start of each session to pull in anything sent via Lark DMs
- The worker URL uses the custom domain (not workers.dev) for China access
- Chunks are idempotent. Running sync multiple times is safe.
