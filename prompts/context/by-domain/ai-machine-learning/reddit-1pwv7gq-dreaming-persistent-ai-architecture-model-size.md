# Dreaming persistent Ai architecture > model size

Source: https://reddit.com/r/LocalLLM/comments/1pwv7gq/dreaming_persistent_ai_architecture_model_size/
Subreddit: r/LocalLLM | Score: 255 | Date: 2025-12-27
Engagement: 0.815 | Practical Value: medium

## Extracted Claims

**Claim 1:** A multi-model architecture using separate smaller models (14B reasoning, 7B code generation, 4B embeddings) can autonomously generate actionable code improvements by performing asynchronous analysis cycles on codebases during idle time.
- Evidence: tutorial (confidence: 0.6)
- Details: Z.E.T.A. indexes codebases into semantic memory graphs and runs periodic 'dream cycles' that free-associate across code patterns. The system outputs concrete suggestions like buffer pool optimizations with estimated performance gains (~40% allocation overhead reduction). However, this is a single implementation with no independent validation of improvement quality or accuracy rates.

**Claim 2:** Model-agnostic architectural patterns (hierarchical reasoning modules + temporal memory with decay) enable scaling inference workloads across consumer GPUs (5060 Ti with 16GB VRAM) while maintaining tokenizer compatibility within a model family.
- Evidence: data (confidence: 0.7)
- Details: The post provides a scaling table showing model combinations tested on specific hardware tiers (5060 Ti, 4090, A6000, A100/H100). The architecture uses GGUF paths that can be swapped, though the author warns against mixing tokenizers across different model families, indicating practical constraints on modularity.

**Claim 3:** Filtering repetitive outputs using novelty detection prevents model rumination and reduces noise in autonomous suggestion systems.
- Evidence: opinion (confidence: 0.5)
- Details: The post mentions that 'repetitive ideas get discarded automatically' and uses 'lambda-based temporal decay' to prevent rumination. No metrics provided on false positive/negative rates or user validation of what constitutes 'novel' versus redundant suggestions.

## Key Data Points
- 14B model for reasoning
- 7B model for code generation
- 4B model for embeddings
- ~40% allocation overhead reduction from buffer pool optimization example
- 5 minute dream cycle interval
- Tested on RTX 5060 Ti (16GB VRAM)
- Scales to 80GB (A100/H100)

**Novelty:** Emerging practice: autonomous code analysis with LLMs is established, but the specific architecture of chained inference models with async 'dream cycles' and temporal decay for codebase improvement is a novel framing rather than cutting-edge research.

## Counterarguments
- Top comment (u/pepouai) questions intent steering and whether the system relies on design docs or pure optimization—post doesn't explicitly address guardrails against generating invalid suggestions.
- No evidence of user validation: claims about 'architectural insights' and 'bug fixes' are not validated against actual developer feedback or ground truth.
- Single-author project with no independent reproduction or peer review mentioned.
- Architecture assumes NVIDIA/CUDA availability, limiting accessibility.

---

 I built an AI that dreams about your codebase while you sleep

Z.E.T.A. (Zero-shot Evolving Thought Architecture) is a multi-model system that indexes your code, builds a memory graph, and runs autonomous "dream cycles" during idle time. It wakes up with bug fixes, refactors, and feature ideas based on YOUR architecture.

**What it actually does:**

1. You point it at your codebase
2. It extracts every function, struct, and class into a semantic memory graph
3. Every 5 minutes, it enters a dream cycle where it free-associates across your code
4. Novel insights get saved as markdown files you can review

Dream output looks like this:

    code_idea: Buffer Pool Optimization
    
    The process_request function allocates a new buffer on every call.
    Consider a thread-local buffer pool:
    
    typedef struct {
        char buffer[BUFSIZE];
        struct buffer_pool *next;
    } buffer_pool_t;
    
    This reduces allocation overhead in hot paths by ~40%.

Dreams are filtered for novelty. Repetitive ideas get discarded automatically.

**Architecture:**

* 14B model for reasoning and planning
* 7B model for code generation
* 4B model for embeddings and memory retrieval
* HRM (Hierarchical Reasoning Module) decomposes complex queries
* TRM (Temporal Reasoning Memory) handles Git-style thought branching
* Lambda-based temporal decay prevents rumination

**Quick start:**

    docker pull ghcr.io/h-xx-d/zetazero:latest
    ./scripts/setup.sh
    # Edit docker-compose.yml to point at your codebase
    docker-compose up -d
    
    # Check back tomorrow
    ls ~/.zetazero/storage/dreams/pending/

Requires NVIDIA GPU with CUDA 12.x. Tested on a 5060 Ti.

**Scales with your hardware**

The default config runs on a 5060 Ti (14B + 7B + 4B). The architecture is model-agnostic. Just swap the GGUF paths in docker-compose.yml:

|Your GPU|Main Model|Coder Model|Embedding Model|
|:-|:-|:-|:-|
|16GB (5060 Ti, 4080)|Qwen 14B|Qwen Coder 7B|Nomic 4B|
|24GB (4090)|Qwen 32B|Qwen Code

[Truncated]

## Top Comments

**u/pepouai** (6 pts):
> Very cool! How are you steering its intent? Do you have functional design docs which it analyses? Or is it pure optimization based?
