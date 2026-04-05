# What retrievers do you use most in your RAG projects?

Source: https://reddit.com/r/Rag/comments/1rask5l/what_retrievers_do_you_use_most_in_your_rag/
Subreddit: r/Rag | Score: 27 | Date: 2026-02-21
Engagement: 0.654 | Practical Value: medium

## Extracted Claims

**Claim 1:** Hybrid retrieval combining vector search with metadata filtering is a practical standard approach in production RAG systems
- Evidence: anecdote (confidence: 0.6)
- Details: The top comment endorses hybrid retrieval with metadata filtering as the preferred approach, suggesting this is a battle-tested pattern in real projects. However, with only one substantive comment in the thread, this reflects a single practitioner's preference rather than broad consensus. The claim is actionable but based on limited data.

**Claim 2:** RAG practitioners actively evaluate multiple retrieval strategies (vector search, BM25, hybrid) rather than defaulting to a single approach
- Evidence: opinion (confidence: 0.7)
- Details: The post itself frames retrieval choice as an open question worth exploring across different techniques. This suggests the RAG community views retriever selection as a meaningful design decision with trade-offs rather than a solved problem. The question attracted engagement, indicating shared uncertainty among practitioners.

**Novelty:** Hybrid retrieval is an established practice in RAG systems (2024-2025), but the thread indicates ongoing uncertainty about optimal retriever combinations in different contexts.

## Counterarguments
- Post received only 24 comments with one substantive response, limiting confidence in representativeness of practitioner preferences
- No discussion of trade-offs (latency, cost, quality) between retrieval approaches that would inform real deployment decisions

---

Hey everyone,  
I’m curious to know what retrievers you use most in your RAG pipelines. Do you mainly rely on vector search, BM25, hybrid retrieval, or something else?

Would love to hear what works best for you in real projects.

## Top Comments

**u/Academic_Track_2765** (12 pts):
> Great question! Always hybrid with metadata filtering.
