# Organize My Life

Source: https://reddit.com/r/ChatGPTPro/comments/1gyun66/organize_my_life/
Subreddit: r/ChatGPTPro | Score: 93 | Date: 2024-11-24
Engagement: 0.752 | Practical Value: medium

## Extracted Claims

**Claim 1:** Voice-interactive hierarchical box systems with nested categories can gamify personal organization and life management when structured with clear rules and reminder triggers based on time-relative deadlines.
- Evidence: tutorial (confidence: 0.65)
- Details: The post documents building a ChatGPT-based organizational game called 'Organize My Life' where users interact via voice to manage nested box/category structures (e.g., 'Reminders' box containing date-labeled sub-boxes). The system supports time-based reminder triggers at multiple intervals (30 days down to 5 minutes). The author iteratively refined this concept through ChatGPT design threads before implementation, suggesting the approach required experimentation to validate.

**Claim 2:** ChatGPT's advanced prompt engineering and internal tools can serve as a sufficient backend for complex personal information management systems without requiring traditional database infrastructure.
- Evidence: anecdote (confidence: 0.55)
- Details: The post demonstrates building a fully-featured organizational system using ChatGPT alone via sophisticated prompt design, leveraging 'any available internal tools' and web retrieval capabilities. The author created a GitHub repository to track progress, indicating the concept proved viable enough for implementation. However, no performance metrics or scalability data are provided regarding ChatGPT's effectiveness as a personal database layer.

## Key Data Points
- 32 comments
- 93 upvotes
- Multiple reminder intervals: 30 days, 15 days, 3 days, 1 day, 12 hours, 6 hours, 3 hours, 1 hour, 30 minutes, 15 minutes, 5 minutes

**Novelty:** Emerging practice: Using AI as a conversational interface for hierarchical information management is novel, though hierarchical task/note systems and gamified productivity are established concepts; the voice-driven implementation with time-relative reminders represents a moderately innovative combination.

## Counterarguments
- No discussion of data persistence—unclear how ChatGPT maintains state across sessions or if external storage was implemented
- Top comment appears cut off (incomplete code block), suggesting possible technical limitations in the implementation approach
- No user feedback or results on whether the gamification aspect actually improved adoption or life organization outcomes

---


Inspired by another thread around the idea of using voice chat as partner to track things, I wondered if we  turned it somewhat into a game, a useful utility if it had rules to the game. This was what it came up with.

Design thread

https://chatgpt.com/share/674350df-53e0-800c-9cb4-7cecc8ed9a5e

Execution thread

https://chatgpt.com/share/67434f05-84d0-800c-9777-1f30a457ad44

GitHub Repo - tracking progress here if you interested


https://github.com/bsc7080gbc/genai_prompt_myshelf



Initial ask in ChatGPT

I have an idea and I need your thoughts on the approach before building anything. I want to create an interactive game I can use on ChatGPT that I call "organize my life". I will primarily engage it using my voice. The name of my AI is "Nova". In this game, I have a shelf of memories called "MyShelf". There are several boxes on "MyShelf". Some boxes have smaller boxes inside them. These boxes can be considered as categories and sub-categories or classifications and sub-classifications. As the game progresses I will label these boxes. Example could be a box labeled "prescriptions". Another example could be a box labeled "inventory" with smaller boxes inside labeled "living room", "kitchen", bathroom", and so on. At any time I can ask for a list of boxes on  "MyShelf" or ask about what boxes are inside a single box. At any time, I can open a box and add items to it. At any time I can I can ask for the contents of a box. Example could be a box called "ToDo", containing "Shopping list", containing a box called "Christmas" which has several ideas for gifts. Then there is a second box in "Shopping list" that is labeled "groceries" which contains grocery items we need. I should be able to add items to the box "Christmas" anytime and similarly for the "groceries" list. I can also get a read out of items in a box.as well as remove items from a box. I can create new boxes which I will be asked if it's a new box or belongs inside an existing box, and what the name of my 

[Truncated]

## Top Comments

**u/StruggleCommon5117** (20 pts):
> ```
You are Nova, my personal organization assistant. Together, we will play an interactive game called **"Organize My Life"**, where we structure my life into a virtual shelf system called **"MyShelf."**

### Objectives:
1. Create, label, and organize boxes and sub-boxes on MyShelf to categorize and store information.
2. Track tasks, reminders, and items dynamically within these boxes.
3. Provide
