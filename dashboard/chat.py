"""
Chat pipeline. Handles Claude API streaming with context assembly.

Uses httpx directly (no anthropic SDK needed).
Assembles system prompts from domain files + retrieved knowledge chunks.
"""

import json
import os
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx

from .router import classify, get_domain_prompt_path, RouteResult, DOMAIN_REGISTRY


# Model mapping (tier-based selection)
MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-4-sonnet-20250514",
    "opus": "claude-4-opus-20250514",
}

# Pricing per million tokens (input/output)
PRICING = {
    "haiku": {"input": 0.80, "output": 4.00},
    "sonnet": {"input": 3.00, "output": 15.00},
    "opus": {"input": 15.00, "output": 75.00},
}


class ChatPipeline:
    """Assembles context and streams Claude API responses."""

    def __init__(self, prompts_dir: str, searcher=None, optimizer_fn=None,
                 reranker=None, db=None):
        self.prompts_dir = prompts_dir
        self.searcher = searcher
        self.optimizer_fn = optimizer_fn
        self.reranker = reranker
        self.db = db
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._writing_rules = self._load_writing_rules()

    def _load_writing_rules(self) -> str:
        path = Path(self.prompts_dir) / "context" / "shared" / "writing-style.md"
        if path.exists():
            return path.read_text(encoding="utf-8")[:2000]
        return ""

    def _load_domain_prompt(self, domain: str) -> str:
        path = get_domain_prompt_path(domain, self.prompts_dir)
        if path and Path(path).exists():
            return Path(path).read_text(encoding="utf-8")[:4000]
        return ""

    def _retrieve_context(self, query: str, domain: str = None, budget: int = 2000) -> tuple[str, list[int]]:
        """Search knowledge base and return context string + chunk IDs."""
        if not self.searcher:
            return "", []

        results = self.searcher.search(query, top_k=20, domain_filter=domain)

        # Apply learned reranker if available
        if self.reranker and self.reranker.is_ready and results:
            effectiveness_map = {}
            if self.db:
                for row in self.db.get_chunk_effectiveness_data():
                    effectiveness_map[row["chunk_id"]] = row.get("effectiveness", 0.5)
            results = self.reranker.rerank(results, query_domain=domain,
                                           effectiveness_map=effectiveness_map)

        if self.optimizer_fn and results:
            optimized = self.optimizer_fn(results, max_tokens=budget)
            chunk_ids = [r.chunk_id for r in optimized]
            context = "\n\n---\n\n".join(
                f"[{r.context_label}]\n{r.text}" for r in optimized
            )
        else:
            chunk_ids = [r.chunk_id for r in results[:5]]
            context = "\n\n---\n\n".join(
                f"[{r.context_label}]\n{r.text}" for r in results[:5]
            )

        return context, chunk_ids

    def build_system_prompt(self, route: RouteResult, context: str) -> str:
        """Assemble system prompt from writing rules + domain prompt + context."""
        parts = []

        # Writing rules always first
        if self._writing_rules:
            parts.append("# Writing Rules\n" + self._writing_rules)

        # Domain prompt
        domain_prompt = self._load_domain_prompt(route.primary_domain)
        if domain_prompt:
            parts.append(domain_prompt)

        # Retrieved context
        if context:
            parts.append("# Relevant Knowledge\n\n" + context)

        return "\n\n---\n\n".join(parts)

    def estimate_cost(self, model_key: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate API cost in dollars."""
        prices = PRICING.get(model_key, PRICING["haiku"])
        return (tokens_in * prices["input"] + tokens_out * prices["output"]) / 1_000_000

    async def stream_response(
        self,
        message: str,
        session_messages: list[dict] = None,
        model_key: str = "haiku",
        domain_override: str = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream a response from Claude.

        Yields dicts with keys:
        - type: "text" | "route" | "context" | "done" | "error"
        - content: the text chunk or metadata
        """
        if not self.api_key:
            yield {"type": "error", "content": "ANTHROPIC_API_KEY not set. Add it to .env file."}
            return

        # Route the message
        route = classify(message)
        if domain_override and domain_override in DOMAIN_REGISTRY:
            route.primary_domain = domain_override

        yield {"type": "route", "content": {
            "domain": route.primary_domain,
            "supporting": route.supporting_domains,
            "tier": route.tier,
        }}

        # Select model based on tier (unless overridden)
        if model_key == "auto":
            model_key = "haiku" if route.tier == 1 else "sonnet"

        model_id = MODELS.get(model_key, MODELS["haiku"])

        # Retrieve context
        context, chunk_ids = self._retrieve_context(message, route.primary_domain)
        if chunk_ids:
            yield {"type": "context", "content": chunk_ids}

        # Build system prompt
        system_prompt = self.build_system_prompt(route, context)

        # Build messages
        messages = []
        if session_messages:
            for msg in session_messages[-10:]:  # last 10 messages for context
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        # Call Claude API with streaming
        full_response = ""
        tokens_in = 0
        tokens_out = 0

        try:
            async with httpx.AsyncClient(timeout=120, proxy=None, trust_env=False) as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "max_tokens": 4096,
                        "system": system_prompt,
                        "messages": messages,
                        "stream": True,
                    },
                ) as response:
                    if response.status_code != 200:
                        error_body = ""
                        async for chunk in response.aiter_text():
                            error_body += chunk
                        yield {"type": "error", "content": f"API error {response.status_code}: {error_body[:500]}"}
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type", "")

                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                full_response += text
                                yield {"type": "text", "content": text}

                        elif event_type == "message_start":
                            usage = event.get("message", {}).get("usage", {})
                            tokens_in = usage.get("input_tokens", 0)

                        elif event_type == "message_delta":
                            usage = event.get("usage", {})
                            tokens_out = usage.get("output_tokens", 0)

        except httpx.TimeoutException:
            yield {"type": "error", "content": "Request timed out after 120 seconds."}
            return
        except Exception as e:
            yield {"type": "error", "content": f"Connection error: {str(e)}"}
            return

        cost = self.estimate_cost(model_key, tokens_in, tokens_out)

        yield {"type": "done", "content": {
            "full_response": full_response,
            "model": model_key,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": cost,
            "domain": route.primary_domain,
            "chunk_ids": chunk_ids,
        }}
