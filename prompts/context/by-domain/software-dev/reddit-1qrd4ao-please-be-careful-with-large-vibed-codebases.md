# Please be careful with large (vibed) codebases.

Source: https://reddit.com/r/vibecoding/comments/1qrd4ao/please_be_careful_with_large_vibed_codebases/
Subreddit: r/vibecoding | Score: 220 | Date: 2026-01-30
Engagement: 0.882 | Practical Value: high

## Extracted Claims

**Claim 1:** AI-generated code has approximately 1.7x higher defect density than human-written code, averaging 55 bugs per 1000 lines compared to 15-50 for human code.
- Evidence: data (confidence: 0.65)
- Details: The post cites research estimates showing human code has 15-50 defects per 1000 lines, while AI-generated code is estimated at 1.7x higher (25.5-85 bugs per 1000 lines). This extrapolates to approximately 5500 bugs in a 100k line codebase. The confidence is moderate because the source of these estimates is not cited and the field of AI code generation is rapidly evolving.

**Claim 2:** Feature interaction complexity grows exponentially (2^n - 1 - n) and untested feature interactions represent a major risk vector in large AI-generated codebases that developers don't fully understand.
- Evidence: opinion (confidence: 0.75)
- Details: The post uses combinatorial mathematics to demonstrate that a 8-feature application has 247 possible feature interactions. The author argues that because AI generation is probabilistic, it 'guesses' at feature interaction behavior, creating undetected bugs. This is a reasonable architectural concern though the actual failure rate from interactions is acknowledged as 'much lower' than theoretical maximum.

**Claim 3:** Developers using vibe coding (AI-generation without code comprehension) on codebases over 100k lines should implement significantly more testing than AI recommends and require human code review, particularly when charging money or building user-dependent systems.
- Evidence: opinion (confidence: 0.85)
- Details: This is the post's primary recommendation, presented as a responsibility principle rather than technical fact. The author explicitly states this is advocacy for matching care level to project scope/impact. The top comment validates this position from another experienced engineer's perspective.

## Key Data Points
- 15-50 defects per 1000 lines (human code)
- 25.5-85 bugs per 1000 lines (AI code)
- 1.7x higher defect density (AI vs human)
- 55 bugs per 1000 lines (averaged estimate)
- 5500 bugs (estimated in 100k line codebase)
- 2^n - 1 - n (feature interaction formula)
- 26 interactions (5 features)
- 57 interactions (6 features)
- 247 interactions (8 features)
- >90% confidence that most vibe-coded projects don't need >100k lines

**Novelty:** This represents emerging best-practice guidance for a novel development paradigm (vibe coding) rather than cutting-edge research or common knowledge.

## Counterarguments
- No commenters directly contradicted the core safety recommendations; the top comment reinforces rather than disputes the post's position.
- The post acknowledges that expert human developers also produce buggy code, which could be interpreted as minimizing the severity of AI-generated defects.
- The defect rate comparison sources are not provided ('a very quick research prompt'), raising questions about methodological rigor.

---

I'm a professional software engineer with decades of experience who has really been enjoying vibe coding lately.  I'm not looking to discourage anyone or gatekeep here, I am truly thrilled by AI's ability to empower more software development. 

That said, if you're a pure vibe coder (you don't read/understand the code you're generating) your codebase is over 100k lines, and you're either charging money or creating something people will depend on then PLEASE either do way more testing than you think you need to and/or try to find someone to do a code review (and yes, by all means, please ask the AI to minimize/optimize the codebase, to generate test plans, to automate as much testing as possible, and to review your code.  I STILL recommend doing more testing than the AI says and/or finding a person to look at the code).

I'm nearly certain, more than 90% of the software people are vibe coding does not need > 100k lines of code and am more confident in saying that your users will never come close to using that much of the product.     
  
Some stats:

A very quick research prompt estimates between 15-50 defects per 1000 lines of human written code.  Right now the AI estimate is 1.7x higher.  So 25.5 - 85 bugs per 1000 lines.  Averaging that out (and chopping the decimal off) we get 55 bugs per 1000 lines of code.  So your 100k code base, on average, has 5500 bugs in it.  Are you finding nearly that many?

The number of ways your features can interact increases exponentially.  It's defined by the formula 2\^n - 1 - n.  So if your app has 5 features there are 26 possible interactions. 6 features 57, 7 features 120, 8 features 247 and so on.  Obviously the amount of significant interactions is much lower (and the probability of interactions breaking something is not nearly that high) but if you're not explicitly defining how the features can interact (and even if you are defining it with instructions we've all had the AI ignore us before) the AI is guessing.  Today's mod

[Truncated]

## Top Comments

**u/ParamedicAble225** (38 pts):
> I’m a veteran software engineer who enjoys vibe coding and loves seeing AI empower more builders.



But if you’re shipping large codebases you don’t understand and people rely on them, you need heavy testing and real reviews. Use AI to help—but go beyond its suggestions.



Lower barriers are great. Care and responsibility should rise with impact.
