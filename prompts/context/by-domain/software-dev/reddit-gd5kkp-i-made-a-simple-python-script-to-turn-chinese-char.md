# I made a simple Python script to turn Chinese characters into Anki cards

Source: https://reddit.com/r/ChineseLanguage/comments/gd5kkp/i_made_a_simple_python_script_to_turn_chinese/
Subreddit: r/ChineseLanguage | Score: 26 | Date: 2020-05-04
Engagement: 0.426 | Practical Value: high

## Extracted Claims

**Claim 1:** An offline Python script using CC-CEDICT can automate Anki card generation for Chinese characters, displaying characters on one side and pinyin + English translations on the other.
- Evidence: tutorial (confidence: 0.85)
- Details: The author created an open-source tool that leverages the CC-CEDICT dictionary database to streamline the conversion of Chinese vocabulary into Anki flashcards. The script runs offline, eliminating dependency on external APIs. The card format (character → pinyin + translation) is designed to support spaced repetition learning for Chinese language acquisition.

**Claim 2:** There is a notable gap in accessible tooling for converting Chinese vocabulary into Anki cards, despite the popularity of both Anki for language learning and the Zhongwen browser extension.
- Evidence: opinion (confidence: 0.7)
- Details: The author explicitly states frustration with 'the apparent lack of tooling' in this specific domain. This motivated them to create their own solution inspired by the Zhongwen extension's functionality. The observation suggests that existing solutions either don't exist, have poor discoverability, or don't meet learner needs effectively.

**Novelty:** Emerging practice—automating flashcard creation for Chinese is a recognized need, but this represents a practical tool implementation rather than a novel concept.

---

Hey all,

I've been frustrated with the apparent lack of tooling for creating Anki cards when it comes to Chinese. I really like the [Zhongwen](https://github.com/cschiller/zhongwen) extension in the browser, and I wanted something to make it easy to turn words I didn't know into Anki cards.

Using [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict), I wrote a Python script that runs offline to turn your words into Anki cards with the character on one side and the pinyin + English translation on the other side.

The code is all open source [on GitHub](https://github.com/owenshen24/chinese-auto-anki).

It's pretty simple, and I hope it can be adaptable to the learning needs of others!