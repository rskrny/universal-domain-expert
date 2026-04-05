# Your lazy prompting is making ChatGPT dumber (and what to do about it)

Source: https://reddit.com/r/ChatGPTCoding/comments/1mnclnv/your_lazy_prompting_is_making_chatgpt_dumber_and/
Subreddit: r/ChatGPTCoding | Score: 144 | Date: 2025-08-11
Engagement: 0.817 | Practical Value: high

## Extracted Claims

**Claim 1:** Vague retry prompts ('still doesn't work, please fix') demonstrably degrade model performance across benchmarks, not just fail to help.
- Evidence: data (confidence: 0.85)
- Details: The post cites a peer-reviewed paper (arXiv:2310.01798) showing GPT-3.5's common sense test performance actually decreased after lazy prompts like 'recheck your work for errors.' This effect was replicated across multiple models and benchmarks, establishing it as a systematic failure mode rather than anecdotal.

**Claim 2:** Meta-prompting—explicitly instructing an AI to follow a specific thinking process (hypothesis generation, fact-checking, step-by-step reasoning)—outperforms simple retry requests for debugging.
- Evidence: opinion (confidence: 0.7)
- Details: The post proposes three meta-prompting techniques: defining thought processes, forcing multiple hypotheses before code generation, and ensuring the AI summarizes prior attempts. While grounded in cognitive reasoning principles, these are presented as best practices rather than validated through cited benchmarks.

**Claim 3:** Different AI models have different strengths for specific bug categories, making multi-model debate or sequential diagnosis more effective than repeated attempts with a single model.
- Evidence: data (confidence: 0.75)
- Details: Post cites arXiv:2506.03283v1 showing model-specific performance variations and notes that research validates debate between different model instances. Suggests using Claude first, then ChatGPT/Gemini, with structured context transfer and explicit conflict instructions.

## Key Data Points
- 50+ failed attempts mentioned as trigger point
- Two-step workflow proposed
- Multiple model instances tested for debate effectiveness

**Novelty:** Emerging practice: the specific application of meta-prompting and multi-model debate to debugging workflows combines known techniques in a novel systematic approach, though the underlying principles (chain-of-thought reasoning, ensemble methods) are established.

## Counterarguments
- Top commenter (26 pts) argues the proposed workflow is labor-intensive and suggests most steps should be automated by IDEs/tools rather than manual prompting, directly challenging the post's manual debugging approach as inefficient.

---

When the ChatGPT fails to solve a bug for the FIFTIETH \*\*\*\*\*\*\* TIME, it’s tempting to fall back to “still doesn’t work, please fix.”

 DON’T DO THIS.

* It wastes time and money and
* It makes the AI **dumber.**

In fact, the graph above is what lazy prompting does to your AI.

It's a graph (from [this paper](https://arxiv.org/pdf/2310.01798)) of how GPT 3.5 performed on a test of common sense after an initial prompt and then after one or two lazy prompts (“recheck your work for errors.”).

Not only does the lazy prompt not help; **it makes the model worse**. And researchers found this across models and benchmarks.

Okay, so just shouting at the AI is useless. The answer isn't just 'try harder'—it's to apply effort strategically. You need to stop being a lazy prompter and start being a strategic debugger. This means giving the AI new information or, more importantly, a new process for thinking. Here are the two best ways to do that:

# Meta-prompting

Instead of telling the AI what to fix, you tell it how to think about the problem. You're essentially installing a new problem-solving process into its brain for a single turn.

Here’s how:

* **Define the thought process**—Give the AI a series of thinking steps that you want it to follow. 
* **Force hypotheses**—Ask the AI to generate multiple options for the cause of the bug before it generates code. This stops tunnel vision on a single bad answer.
* **Get the facts**—Tell the AI to summarize what we know and what it’s tried so far to solve the bug. Ensures the AI takes all relevant context into account.

# Ask another AI

Different AI models tend to [perform best for different kinds of bugs](https://arxiv.org/html/2506.03283v1). You can use this to your advantage by using a different AI model for debugging. Most of the vibe coding companies use Anthropic’s Claude, so your best bet is ChatGPT, Gemini, or whatever models are currently at the top of [LM Arena](https://lmarena.ai/leaderboard/webdev).

Here are a 

[Truncated]

## Top Comments

**u/fredrik_skne_se** (26 pts):
> That’s a lot of work for a bug.

Step 1 can be automatically included in tools.
Step 2, you can ask the LLM to rephrase/expand it. Example: ”implement auth”

3: the LLM + text selection should be able to generate a phrase.

4 and 5: ask LLM to generate an analysis 

6: ask LLM/+tool to include files
