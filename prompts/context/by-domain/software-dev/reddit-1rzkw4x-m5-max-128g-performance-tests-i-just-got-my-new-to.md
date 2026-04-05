# M5 Max 128G Performance tests. I just got my new toy, and here's what it can do.

Source: https://reddit.comhttps://reddit.com/r/LocalLLaMA/comments/1rzkw4x/m5_max_128g_performance_tests_i_just_got_my_new/
Subreddit: r/LocalLLaMA | Score: 123 | Date: 2026-03-21

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
|**MLX**|v0.31.1 + mlx-lm v0.31.1|

# Results Summary

|Rank|Model|Params|Quant|Engine|Size|Avg tok/s|Notes|
|:-|:-|:-|:-|:-|:-|:-|:-|
|1|DeepSeek-R1 8B|8B|Q6\_K|llama.cpp|6.3GB|**72.8**|Fastest — excellent reasoning for size|
|2|Qwen 3.5 27B|27B|4bit|MLX|16GB|**31.6**|MLX is 92% faster than llama.cpp for this model|
|3|Gemma 3 27B|27B|Q6\_K|llama.cpp|21GB|**21.0**|Consistent, good all-rounder|
|4|Qwen 3.5 27B|27B|Q6\_K|llama.cpp|21GB|**16.5**|Same model, slower on llama.cpp|
|5|Qwen 2.5 72B|72B|Q6\_K|llama.cpp|60GB|**7.6**|Largest model, still usable|

# Detailed Results by Prompt Type

# llama.cpp Engine

|Model|Simple|Reasoning|Creative|Coding|Knowledge|Avg|
|:-|:-|:-|:-|:-|:-|:-|
|DeepSeek-R1 8B Q6\_K|72.7|73.2|73.2|72.7|72.2|**72.8**|
|Gemma 3 27B Q6\_K|19.8|21.7|19.6|22.0|21.7|**21.0**|
|Qwen 3.5 27B Q6\_K|20.3|17.8|14.7|14.7|14.8|**16.5**|
|Qwen 2.5 72B Q6\_K|6.9|8.5|7.9|7.6|7.3|**7.6**|

# MLX Engine

|Model|Simple|Reasoning|Creative|Coding|Knowledge|Avg|
|:-|:-|:-|:-|:-|:-|:-|
|Qwen 3.5 27B

[Truncated. See original post for full content.]

## Top Comments

**u/CATLLM** (100 pts):
> Why did you compare the speed of the MLX 4bit with the Q6 GGUF for Qwen3.5-27b model? Wouldn't a fairer comparison be MLX 4bit vs Q4? And what are your sources for the GGUFs and MLX quants?
