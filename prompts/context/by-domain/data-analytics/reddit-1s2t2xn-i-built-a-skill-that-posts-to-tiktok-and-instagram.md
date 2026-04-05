# I built a skill that posts to TikTok and Instagram daily and learns from its own analytics

Source: https://reddit.comhttps://reddit.com/r/clawdbot/comments/1s2t2xn/i_built_a_skill_that_posts_to_tiktok_and/
Subreddit: r/clawdbot | Score: 21 | Date: 2026-03-24

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
