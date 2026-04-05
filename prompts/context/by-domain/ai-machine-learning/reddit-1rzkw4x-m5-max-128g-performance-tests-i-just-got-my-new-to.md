# M5 Max 128G Performance tests. I just got my new toy, and here's what it can do.

Source: https://reddit.com/r/LocalLLaMA/comments/1rzkw4x/m5_max_128g_performance_tests_i_just_got_my_new/
Subreddit: r/LocalLLaMA | Score: 123 | Date: 2026-03-21
Engagement: 0.887 | Practical Value: high

## Extracted Claims

**Claim 1:** Apple M5 Max achieves 73-75% of theoretical maximum memory bandwidth utilization for LLM inference, with token generation speed directly correlating to the ratio of available bandwidth divided by model size.
- Evidence: data (confidence: 0.85)
- Details: The post provides benchmark data showing DeepSeek-R1 8B achieving 72.8 tok/s (75% efficiency), Gemma 3 27B at 21.0 tok/s (72% efficiency), and Qwen 2.5 72B at 7.6 tok/s (75% efficiency) against theoretical maximums calculated from the M5 Max's 614 GB/s memory bandwidth. This demonstrates a consistent, predictable relationship between hardware constraints and inference performance.

**Claim 2:** MLX achieves 92% faster inference than llama.cpp for Qwen 3.5 27B models on Apple Silicon, with the speed difference driven by MLX's native Metal implementation handling the Qwen 3.5 architecture better than llama.cpp.
- Evidence: data (confidence: 0.7)
- Details: Benchmarks show llama.cpp at 16.5 tok/s (Q6_K, 21GB) versus MLX at 31.6 tok/s (4bit, 16GB) for the same model family. However, the top comment raises a valid methodological concern: the comparison uses different quantization formats (Q6_K vs 4bit), making it unclear whether the speedup reflects the engine difference or quantization efficiency difference.

**Claim 3:** DeepSeek-R1 8B is the optimal balance of inference speed and capability for local deployment on M5 Max, achieving 72.8 tok/s while providing reasoning capabilities comparable to much larger models.
- Evidence: data (confidence: 0.75)
- Details: The benchmark data ranks DeepSeek-R1 8B as the fastest model by significant margin (3.4x faster than Gemma 3 27B), and the post notes it provides 'excellent reasoning for size.' However, this is a single benchmark result and lacks comparative reasoning quality metrics to fully validate the capability claim.

## Key Data Points
- 614 GB/s (M5 Max memory bandwidth)
- 72.8 tok/s (DeepSeek-R1 8B)
- 31.6 tok/s (Qwen 3.5 27B MLX)
- 92% faster (MLX vs llama.cpp for Qwen 3.5)
- 73-75% (theoretical bandwidth utilization efficiency)
- 7.6 tok/s (Qwen 2.5 72B largest model)
- 128GB unified memory

**Novelty:** Emerging practice: M5 Max benchmarking data is novel and early, but the systematic approach to understanding memory bandwidth constraints as the primary performance limiter is a valuable generalization not yet widely documented for Apple Silicon.

## Counterarguments
- Top commenter questions fairness of MLX vs llama.cpp comparison due to different quantization formats (4bit vs Q6_K), suggesting the 92% speedup may conflate engine performance with quantization efficiency.
- Post does not specify sources or links for the GGUF and MLX quantized models used, limiting reproducibility.
- Comparison lacks normalized testing across same quantization formats to isolate engine-specific performance differences.

---

I just started into this stuff a couple months ago, so be gentle. I'm and old grey-haired IT guy, so I'm not coming from 0, but this stuff is all new to me. 

What started with a Raspberry PI with a Hailo10H, playing around with openclaw and ollama, turned into me trying ollama on my Macbook M3 Pro 16G, where I immediately saw the potential. The new M5 was announced at just the right time to trigger my OCD, and I got the thing just yesterday. 

I've been using claude code for a while now, having him configure the Pi's, and my plan was to turn the laptop on, install claude code, and have him do all the work. I had been working on a plan with him throughout the Raspberry Pi projects (which turned into 2, plus a Whisplay HAT, piper, whisper), so he knew where we were heading. I copied my claude code workspace to the new laptop so I had all the memories, memory structure, plugins, sub-agent teams in tmux, skills, security/sandboxing, observability dashboard, etc. all fleshed out. I run him like an IT team with a roadmap.

I had his research team build a knowledge-base from all the work you guys talk about here and elsewhere, gathering everything regarding performance and security, and had them put together a project to figure out how to have a highly capable AI assistant for anything, all local. 

First we need to figure out what we can run, so I had him create a project for some benchmarking. 

He knows the plan, and here is his report.  

# Apple M5 Max LLM Benchmark Results

**First published benchmarks for Apple M5 Max local LLM inference.**

# System Specs

|Component|Specification|
|:-|:-|
|**Chip**|Apple M5 Max|
|**CPU**|18-core (12P + 6E)|
|**GPU**|40-core Metal (MTLGPUFamilyApple10, Metal4)|
|**Neural Engine**|16-core|
|**Memory**|128GB unified|
|**Memory Bandwidth**|614 GB/s|
|**GPU Memory Allocated**|122,880 MB (via `sysctl iogpu.wired_limit_mb`)|
|**Storage**|4TB NVMe SSD|
|**OS**|macOS 26.3.1|
|**llama.cpp**|v8420 (ggml 0.9.8, Metal backend)|
|**MLX**|v0.31

[Truncated]

## Top Comments

**u/CATLLM** (100 pts):
> Why did you compare the speed of the MLX 4bit with the Q6 GGUF for Qwen3.5-27b model? Wouldn't a fairer comparison be MLX 4bit vs Q4? And what are your sources for the GGUFs and MLX quants?
