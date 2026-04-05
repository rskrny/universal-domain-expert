# Neural Net Credentials Reference

All secrets are stored in `.env`. This file lists what each credential is for.

## Dashboard Auth
- **DASHBOARD_TOKEN**: Set in `.env` to enable auth when accessed via Cloudflare Tunnel
- Generated token (ready to use): `1Ox8k8GVMx9nZbdkAGJKgCuJqV7iDH_w`
- To enable: add `DASHBOARD_TOKEN=1Ox8k8GVMx9nZbdkAGJKgCuJqV7iDH_w` to `.env`
- When empty: auth is disabled (local development mode)
- Access: visit `/auth` and enter the token. Cookie lasts 30 days.

## Brain Feed Worker (brainfeed-webhook.rskrny.workers.dev)
- D1 database: `brainfeed-knowledge` (id: f4711fcc-1d88-43a5-9e64-393207dcb964)
- Secrets set via `wrangler secret put`: LARK_APP_ID, LARK_APP_SECRET, ANTHROPIC_API_KEY, AUTH_TOKEN
- Webhook URL: `https://brainfeed-webhook.rskrny.workers.dev/webhook`

## Flip Side Worker (flipside-lark-bridge.rskrny.workers.dev)
- D1 database: `flipside-briefings` (id: 961c5503-b1fc-4047-8a20-6885eb70265b)
- Briefing POST endpoint: `https://flipside-lark-bridge.rskrny.workers.dev/briefing`

## Cloudflare Tunnel
- cloudflared binary: `C:\Users\rskrn\Downloads\cloudflared.exe`
- Version: 2026.3.0
- Quick tunnel: `cloudflared.exe tunnel --url http://localhost:8502`
  (URL changes each restart. For permanent URL, create named tunnel.)
- To create named tunnel: `cloudflared.exe tunnel create neural-net`

## Lark Brain Feed Bot
- App ID: cli_a94474233238de18
- Org: ShopMyRoom
- Version: 1.1.0 (Released)
- Developer Console: https://open.larksuite.com/app/cli_a94474233238de18

## Scheduled Tasks
- Flip Side daily briefing: 6:57 AM GMT+8 (RemoteTrigger on claude.ai)
- Reddit daily digest: 8:23 AM local (Claude Code scheduled-tasks MCP)

## API Keys (in .env)
- ANTHROPIC_API_KEY: Claude API
- REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET: Reddit PRAW
- REDDIT_USERNAME / REDDIT_PASSWORD: Reddit (u/slamjacket)
- BRAINFEED_APP_ID / BRAINFEED_APP_SECRET: Lark Brain Feed bot
