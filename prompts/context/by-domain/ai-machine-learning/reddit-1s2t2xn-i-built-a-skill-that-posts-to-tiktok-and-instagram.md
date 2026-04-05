# I built a skill that posts to TikTok and Instagram daily and learns from its own analytics

Source: https://reddit.com/r/clawdbot/comments/1s2t2xn/i_built_a_skill_that_posts_to_tiktok_and/
Subreddit: r/clawdbot | Score: 21 | Date: 2026-03-24
Engagement: 0.596 | Practical Value: medium

## Extracted Claims

**Claim 1:** An AI system can identify optimal posting patterns and content hooks through iterative analytics feedback, demonstrating measurable performance improvements over 2 weeks without manual intervention.
- Evidence: data (confidence: 0.65)
- Details: The author reports 11 posts over 2 weeks with zero manual intervention. The system identified that SHOCK hooks outperform CURIOSITY and CONTRADICTION in their niche, posting at 9:00 UTC yields 2.14x more views (952 vs 445) than 17:00 UTC, and top performer achieved 1.17% engagement vs 0.35% average. However, these conclusions are based on 11 samples from a single account in an unspecified niche, limiting generalizability.

**Claim 2:** Automated carousel content generation combined with real-time analytics creates a closed-loop optimization system that progressively improves post performance.
- Evidence: tutorial (confidence: 0.7)
- Details: The system analyzes websites/products, generates carousel slides via Gemini 3.1 Flash, posts via Upload-Post API, pulls analytics, and incorporates learnings into subsequent posts. The author explicitly frames this as moving beyond 'generate and pray' to a feedback loop approach. Implementation details are available on GitHub but the post lacks technical specifics on the learning algorithm.

## Key Data Points
- 11 posts over 2 weeks
- 952 views at 9:00 UTC optimal time
- 445 views at 17:00 UTC
- 0.35% average engagement
- 1.17% top engagement rate
- 2.14x view difference between optimal and suboptimal posting time

**Novelty:** Emerging practice—automated content generation is common, but integrating real-time analytics feedback loops for continuous optimization of hook types and posting times represents a moderately novel application of feedback systems to social media.

## Counterarguments
- u/Jhorra criticizes the approach as 'AI slop,' suggesting the automated content may lack quality or originality, though this is opinion-based rather than evidence-based criticism.
- Potential concern: small sample size (11 posts) may not be statistically significant for pattern identification; niche-specific results may not generalize.

---

Been running this for 2 weeks now. 11 posts, zero manual intervention.

What it does:

• Analyzes any website/product

• Generates carousel slides with Gemini 3.1 Flash

• Posts to TikTok + Instagram via Upload-Post API (free tier)

• Pulls analytics and learns what works

The learning part is what makes it interesting:



After 11 posts, it already knows:



• Which hook types perform best (SHOCK > CURIOSITY > CONTRADICTION for my niche)

• Best posting time (9:00 UTC = 952 avg views vs 17:00 UTC = 445)

• Which words/emojis correlate with higher engagement

Each new post uses these learnings. It's not "generate and pray" — it's a feedback loop.



Results so far:



• Top hook: "¡No dejes que tu cuenta desaparezca!" — 952 views

• Avg engagement: 0.35%

• Best performer had 1.17% engagement



Not viral numbers, but the system is 2 weeks old and improving automatically.

[https://github.com/mutonby/viraloop](https://github.com/mutonby/viraloop)



Happy to answer questions about the implementation.

## Top Comments

**u/Jhorra** (15 pts):
> So your one of the people filling socials with AI slop.
