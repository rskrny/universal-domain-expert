# I'm Tommy, I built ReviewMeta - a site that detects "fake" reviews on Amazon. AMA!

Source: https://reddit.com/r/IAmA/comments/dsh6ou/im_tommy_i_built_reviewmeta_a_site_that_detects/
Subreddit: r/IAmA | Score: 19786 | Date: 2019-11-06
Engagement: 1.0 | Practical Value: high

## Extracted Claims

**Claim 1:** Automated analysis of Amazon reviews can identify fake reviews by detecting suspicious patterns such as unverified purchases, free product disclosures paired with 5-star ratings, and statistical anomalies across thousands of reviews.
- Evidence: data (confidence: 0.85)
- Details: Tommy manually analyzed 580 reviews for a single product and identified dozens of suspicious patterns. He then built ReviewMeta to automate this analysis across 18 million Amazon reviews. The tool's credibility is supported by NPR Planet Money coverage and the fact that Amazon changed its TOS regarding incentivized reviews within 3 weeks of ReviewMeta's 2016 launch.

**Claim 2:** Incentivized reviews (products received for free in exchange for reviews) represent a significant source of fake/biased reviews on Amazon, even when reviewers explicitly disclose the free product.
- Evidence: anecdote (confidence: 0.8)
- Details: The original observation that triggered ReviewMeta's creation was noticing multiple reviewers who admitted receiving free products but still left 5-star ratings. This pattern was significant enough to be highlighted as a core motivation for the tool and suggests systematic bias in incentivized review programs.

## Key Data Points
- 580 reviews analyzed manually on single product
- 18 million Amazon reviews analyzed by ReviewMeta
- 2015: inception year (manual analysis)
- 2016: ReviewMeta launch
- 3 weeks: time until Amazon changed TOS after ReviewMeta's viral video

**Novelty:** Emerging practice: while fake review detection was nascent in 2015-2016, ReviewMeta represents an early and formalized approach to automating fraud detection at scale on Amazon.

## Counterarguments
- Top comment from u/DeltaNu1142 questions the differentiation between ReviewMeta and FakeSpot, suggesting competing tools already existed and may serve similar purposes.

---

Hello Reddit, I'm Tommy Noonan. In 2015, I spent an entire day reading *ALL 580 reviews for a product on Amazon*. To my surprise, many reviewers admitted they had not used the product, or they got one for free, **but still left 5 stars**. I noticed dozens of other extremely suspicious patterns after spending the day analyzing the data.

The gears in my head started turning and I realized I could write a computer program to scrape all the reviews and perform a deep analysis in seconds rather than spending all day doing it manually. I could then point it at ANY product on Amazon and generate the same report. *This is when the idea for ReviewMeta was conceived*.

I launched ReviewMeta in 2016 - you may remember our video hitting the front page of /r/all \- the site got the Reddit Hug-o-Death: [https://www.reddit.com/r/videos/comments/53i2wo/i\_analyzed\_18000000\_amazon\_reviews\_and\_prove\_the/](https://www.reddit.com/r/videos/comments/53i2wo/i_analyzed_18000000_amazon_reviews_and_prove_the/) (oh, and 3 weeks after the video, Amazon changed their TOS and banned incentivized reviews)

Or you may have listened to NPR's Planet Money podcast titled "The Fake Review Hunter" (that's me!) [https://www.npr.org/sections/money/2018/06/27/623990036/episode-850-the-fake-rev](https://www.npr.org/sections/money/2018/06/27/623990036/episode-850-the-fake-rev)

Proof: [https://twitter.com/ReviewMeta/status/1189230751780352000](https://twitter.com/ReviewMeta/status/1189230751780352000)

You can use ReviewMeta by copying and pasting any Amazon product URL into the search bar at [ReviewMeta.com](https://ReviewMeta.com).  *(Example report:* [*https://reviewmeta.com/amazon/B07ZF9WLQT*](https://reviewmeta.com/amazon/B07ZF9WLQT)*)*

I'll be answering your questions about fake reviews detection, review hijacking and other scams from 9:30am to noon (Eastern Time), but will likely stick around and answer some more Q's if they are still trickling in.

AMA!

Edit: Answering questions as fast as 

[Truncated]

## Top Comments

**u/DeltaNu1142** (1345 pts):
> Hello Tommy: how does ReviewMeta differentiate itself from FakeSpot? I use that site regularly for Amazon purchases and it serves me well.

I subscribe to Planet Money, but I haven’t heard your podcast yet. If I had, I might have already checked out your site. Thanks and good luck.
