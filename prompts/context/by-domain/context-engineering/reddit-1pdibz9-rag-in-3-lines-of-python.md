# RAG in 3 lines of Python

Source: https://reddit.comhttps://reddit.com/r/Rag/comments/1pdibz9/rag_in_3_lines_of_python/
Subreddit: r/Rag | Score: 147 | Date: 2025-12-03

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
