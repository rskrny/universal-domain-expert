# Implemented an extremely accurate AI-based password guesser

Source: https://reddit.com/r/Pentesting/comments/1qnq8mk/implemented_an_extremely_accurate_aibased/
Subreddit: r/Pentesting | Score: 42 | Date: 2026-01-26
Engagement: 0.616 | Practical Value: high

## Extracted Claims

**Claim 1:** LLM-based password guessing fine-tuned on leaked password datasets can correctly guess 31.63% of user passwords within 100 attempts by learning human password creation probability distributions.
- Evidence: data (confidence: 0.7)
- Details: PassLLM uses LoRA-fine-tuned language models trained on millions of leaked passwords from public breaches (ClixSense, 000WebHost, PostMillenial). The framework claims to outperform traditional brute-force and rule-based approaches by modeling how humans actually create passwords. The 31.63% success rate within 100 tries is cited from a USENIX Security 2025 paper (Zou et al.), suggesting peer-reviewed validation exists, though the post doesn't detail comparison baselines.

**Claim 2:** Most internet users create passwords using predictable patterns derived from personal information (59% of American adults) and password reuse (78% of all people), making them vulnerable to intelligence-informed guessing attacks.
- Evidence: data (confidence: 0.85)
- Details: The post cites multiple studies showing prevalence of personal-information-based and reused passwords. These statistics establish the threat model and motivation. The percentages come from cited sources (Spacelift, IET), though without deep verification of original study methodology, they serve as established background rather than novel findings.

**Claim 3:** PassLLM is lightweight enough to run on consumer hardware and supports custom training on organization-specific password datasets, making it adaptable to different platforms and threat contexts.
- Evidence: opinion (confidence: 0.6)
- Details: The post claims the tool is 'lightweight,' 'customizable,' and 'flexible,' allowing users to fine-tune on their own datasets. However, no specific hardware requirements, training time, or computational benchmarks are provided. This is presented as a feature claim rather than demonstrated capability.

## Key Data Points
- 31.63% success rate within 100 guesses
- 59% of American adults use personal information in passwords
- 78% of people reuse old passwords
- 20% of UK public can identify a secure password

**Novelty:** Cutting-edge: applying LLMs with LoRA fine-tuning to password cracking represents a novel intersection of generative AI and pentesting, though the underlying observation that users create predictable passwords is well-established.

## Counterarguments
- No comments directly counter the claims; the single substantive comment (u/Mindless-Study1898) suggests a complementary feature (CeWL integration) rather than disputing the core approach.
- Low comment engagement (10 total comments, top at 8 points) may indicate skepticism or limited perceived novelty in the pentesting community, though absence of criticism isn't confirmation of accuracy.

---

[59% of American adults](https://spacelift.io/blog/password-statistics) use personal information in their online passwords. 78% of all people **reuse their old passwords**. [Studies](https://www.theiet.org/media/press-releases/press-releases-2024/press-releases-2024-april-june/2-may-2024-your-p4-w0rd-isn-t-strong-enough-only-20-of-uk-public-can-identify-a-secure-password) consistently demonstrate how most internet users tend to use their personal information and old passwords when creating new passwords.

In this context, **PassLLM** introduces a framework leveraging LLMs (using lightweight, trainable LoRAs) that are fine-tuned on **millions of leaked passwords and personal information samples** from major public leaks *(e.g. ClixSense, 000WebHost, PostMillenial)*.

Unlike traditional brute-force tools or static rule-based scripts (like "Capitalize Name + Birth Year"), PassLLM learns the underlying probability distribution of how humans actually think when they create passwords. It doesn't only detect patterns and fetches passwords that other algorithms miss, but also individually calculates and sorts them by probability, resulting in ability to correctly guesses up to[ 31.63% of users within 100 tries](https://www.usenix.org/system/files/usenixsecurity25-zou-yunkai.pdf). It easily runs on most consumer hardware, it's lightweight, it's customizable and it's flexible - allowing users to train models on their own password datasets, adapting to different platforms and environments where password patterns are inherently distinct. I appreciate your feedback!

[https://github.com/Tzohar/PassLLM](https://github.com/Tzohar/PassLLM)

Here are some examples (fake PII):

`{"name": "Marcus Thorne", "birth_year": "1976", "username": "mthorne88", "country": "Canada"}`:

    --- TOP CANDIDATES ---
    CONFIDENCE | PASSWORD
    ------------------------------
    0.42%     | 88888888       
    0.32%     | 12345678            
    0.16%     | 1976mthorne     
    0.15%     | 88marcu

[Truncated]

## Top Comments

**u/Mindless-Study1898** (8 pts):
> Interesting. Consider adding the functionality of https://github.com/digininja/CeWL to it!
