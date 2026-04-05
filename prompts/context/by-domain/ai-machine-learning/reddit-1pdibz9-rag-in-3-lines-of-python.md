# RAG in 3 lines of Python

Source: https://reddit.com/r/Rag/comments/1pdibz9/rag_in_3_lines_of_python/
Subreddit: r/Rag | Score: 147 | Date: 2025-12-03
Engagement: 0.732 | Practical Value: high

## Extracted Claims

**Claim 1:** RAG systems can be implemented with minimal boilerplate by abstracting vector stores, embeddings, and chunking logic into a single library interface
- Evidence: tutorial (confidence: 0.8)
- Details: Piragi demonstrates that RAG setup can be reduced to three lines of code (instantiation with sources and a single query method) instead of wiring components separately. The library handles PDF, Word, Excel, Markdown, code, URLs, images, and audio formats automatically with no explicit API key management for local models (Ollama + sentence-transformers).

**Claim 2:** Advanced retrieval techniques (HyDE, hybrid BM25+vector search, cross-encoder reranking) can be enabled via configuration flags rather than manual implementation
- Evidence: tutorial (confidence: 0.75)
- Details: The post shows that sophisticated retrieval strategies are available as toggleable options in a config dictionary, reducing the implementation burden for practitioners who want better retrieval quality without understanding the underlying mechanisms. This lowers the barrier to applying state-of-the-art techniques.

**Claim 3:** Automatically watching and refreshing document sources in the background without introducing query latency is a design goal for modern RAG systems
- Evidence: opinion (confidence: 0.65)
- Details: The post claims 'auto-updates' with 'zero query latency' as a feature, suggesting the author believes background document synchronization is a useful capability for RAG systems. However, this claim lacks technical validation—no benchmark or implementation detail is provided to confirm zero-latency updates are achievable.

**Novelty:** Emerging practice—RAG abstraction libraries are becoming common, but the specific combination of local-first execution, multi-format support, and advanced retrieval as built-in toggles represents a consolidation of existing techniques rather than novel research.

## Counterarguments
- A top comment questions whether URL source handling supports recursive parsing (e.g., crawling documentation sites), suggesting potential gaps in the claimed 'all formats' capability that the post does not address.

---

Got tired of wiring up vector stores, embedding models, and chunking logic every time I needed RAG. So I built piragi.

    from piragi import Ragi
    
    kb = Ragi(\["./docs", "./code/\*\*/\*.py", "https://api.example.com/docs"\])
    
    answer = kb.ask("How do I deploy this?")

That's the entire setup. No API keys required - runs on Ollama + sentence-transformers locally.

**What it does:**

  \- **All formats** \- PDF, Word, Excel, Markdown, code, URLs, images, audio

  \- **Auto-updates** \- watches sources, refreshes in background, zero query latency

  \- **Citations** \- every answer includes sources

  \- **Advanced retrieval** \- HyDE, hybrid search (BM25 + vector), cross-encoder reranking

  \- **Smart chunking** \- semantic, contextual, hierarchical strategies

  \- **OpenAI compatible** \- swap in GPT/Claude whenever you want

**Quick examples:**

    # Filter by metadata
    answer = kb.filter(file_type="pdf").ask("What's in the contracts?")
    
    #Enable advanced retrieval
    
      kb = Ragi("./docs", config={
       "retrieval": {
          "use_hyde": True,
          "use_hybrid_search": True,
          "use_cross_encoder": True
       }
     })

 

    # Use OpenAI instead  
    kb = Ragi("./docs", config={"llm": {"model": "gpt-4o-mini", "api_key": "sk-..."}})

  **Install:**

      pip install piragi

  PyPI: [https://pypi.org/project/piragi/](https://pypi.org/project/piragi/)

Would love feedback. What's missing? What would make this actually useful for your projects?

## Top Comments

**u/vir_db** (5 pts):
> Using an URL as source, can it recursively parse it (I.E. like https://docs.langchain.com/oss/python/integrations/document\_loaders/recursive\_url) ?
