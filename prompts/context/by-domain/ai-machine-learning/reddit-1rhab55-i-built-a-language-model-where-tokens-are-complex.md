# I built a language model where tokens are complex numbers and "meaning" emerges from wave interference -- no attention, O(n), 178M params, open-sourcing today

Source: https://reddit.com/r/BlackboxAI_/comments/1rhab55/i_built_a_language_model_where_tokens_are_complex/
Subreddit: r/BlackboxAI_ | Score: 22 | Date: 2026-02-28
Engagement: 0.557 | Practical Value: medium

## Extracted Claims

**Claim 1:** Complex-valued token representations with phase-based interference can achieve comparable language modeling performance to transformers while eliminating quadratic attention complexity (O(n) vs O(n²)) and requiring no explicit attention mechanism.
- Evidence: data (confidence: 0.45)
- Details: The model achieves validation PPL of 48.92 after 2 epochs on 10k TinyStories samples (0.5% of full dataset) using 178M parameters. However, no direct comparison to baseline GPT models at same scale/data budget is provided. The O(n) complexity claim relies on phase coherence lookup over 512 concept vectors rather than full sequence attention, but absolute performance parity with transformers remains undemonstrated.

**Claim 2:** Phase rotations via Cayley transform (arithmetic-only, no trigonometric functions) provide a computationally efficient alternative to standard complex multiplication for implementing context-dependent meaning shifts in language models.
- Evidence: tutorial (confidence: 0.72)
- Details: The post demonstrates that rotation operations can be computed as `cos_like = (1-a²)/(1+a²)` and `sin_like = 2a/(1+a²)` using only elementwise arithmetic and matmuls, avoiding expensive sin/cos/exp calls. This is mathematically sound and GPU-friendly, though the practical speedup versus standard implementations is not quantified.

**Claim 3:** Decomposing tokens into magnitude (salience) and phase (semantic identity) naturally separates attention-like functionality without requiring attention layers, where high-magnitude states automatically dominate downstream processing.
- Evidence: opinion (confidence: 0.5)
- Details: The author argues that magnitude implicitly handles token importance while phase handles identity, eliminating the need for explicit attention scoring. This is conceptually interesting but relies on untested assumptions: (1) that magnitude naturally learns to encode salience without explicit supervision, and (2) that this decomposition generalizes across diverse linguistic phenomena where attention weights vary.

## Key Data Points
- 178M parameters
- 10k samples (0.5% of TinyStories)
- Val PPL: 76.47 (epoch 1), 48.92 (epoch 2)
- Train PPL: 200.86→32.75→~26 across epochs
- 512 concept vectors in SemanticPhaseBank
- 1024 learned slots in Phase-Coded Memory
- 8-token causal window in ContextPhaseBank
- 40 minutes training on A6000 GPU

**Novelty:** Cutting-edge: using complex-valued representations and wave interference principles for language modeling is unconventional and not standard practice, though complex-valued neural networks and phase-based representations exist in other domains.

## Counterarguments
- No comments available to extract disagreements or technical critiques.
- Missing ablation studies comparing against (1) standard transformer baselines at same scale/data, (2) other O(n) architectures (S4, Mamba, etc.), and (3) the complex representation itself versus real-valued equivalents.
- Training on only 10k samples is not sufficient to demonstrate generalization or competitive capability; overfitting risk is high despite claims of 'needing data now.'
- Generation sample quality is truncated ('For context: A 22M-param GPT-2 tra...'), preventing evaluation of coherence and semantic quality.

---

(Just ping me if its unsuited here.. I'll remove the post to keep the place clean)

I've been working on a fundamentally different LLM architecture. No attention layers. No FFN blocks. Instead, every token lives in complex phase space, and language processing happens through wave-like interference between specialized "phase banks."

Open-sourced here: [https://github.com/gowrav-vishwakarma/qllm2](https://github.com/gowrav-vishwakarma/qllm2)

# The core idea: language as wave interference

In a transformer, a token is a real-valued vector that gets refined through attention + FFN layers. In this model, a token is a **complex number** \-- it has a magnitude (how "important/activated" it is) and a phase angle (what "kind of meaning" it carries). These two properties are naturally separated and jointly processed.

This isn't just a gimmick. It changes how every operation works:

* **Embeddings**: Each token gets a `[real, imag]` vector. The model learns that semantically similar tokens align in phase, while different meanings sit at different angles.
* **Transformations are rotations**: When context modifies a token's meaning (like "bank" shifting meaning based on surrounding words), that's a phase rotation -- a complex multiply. Rotations compose naturally, are always invertible (no information loss), and reduce to GEMM.
* **Similarity is coherence**: Instead of dot product, we use phase coherence: `Re(a * conj(b)) / (|a| * |b|)`. This measures both directional alignment AND magnitude relationship.
* **Multiple banks interfere**: A "semantic bank" and "context bank" process each token independently, then combine via learned interference (constructive where they agree, destructive where they conflict). A tiny router decides per-token how much weight each bank gets. Think MoE but at the representation level.

# What the phase system actually gives us

**1. Natural magnitude/phase decomposition = implicit attention** High-magnitude phase states dominate downstream process

[Truncated]