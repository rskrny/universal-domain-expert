# Open-source AI system on a $500 GPU outperforms Claude Sonnet on coding benchmarks

Source: https://reddit.comhttps://reddit.com/r/artificial/comments/1s2yg3y/opensource_ai_system_on_a_500_gpu_outperforms/
Subreddit: r/artificial | Score: 287 | Date: 2026-03-25

---

What if building more and more datacenters was not the only option? If we are able to get similar levels of performance for top models at a consumer level from smarter systems, then its only a matter of time before the world comes to the realization that AI is a lot less expensive and a whole lot more obtainable.

Open source projects like ATLAS are on the frontier of this possibility- where a 22 year old college student from Virginia Tech built and ran a 14B parameter AI model on a single $500 Consumer GPU and scored higher than Claude Sonnet 4.5 on coding benchmarks (74.6% vs 71.4% on LiveCodeBench, 599 problems).

No cloud, no API costs, no fine-tuning. Just a consumer graphics card and smart infrastructure around a small model. 

And the cost? Only around $0.004/task in electricity.

The base model used in ATLAS only scores about 55%. The pipeline adds nearly 20 percentage points by generating multiple solution approaches, testing them, and selecting the best one. Proving that smarter infrastructure and systems design is the future of the industry.

Repo: [https://github.com/itigges22/ATLAS](https://github.com/itigges22/ATLAS)

## Top Comments

**u/braindancer3** (25 pts):
> So if I hook the pipeline up to Sonnet, I'll get 91%?
