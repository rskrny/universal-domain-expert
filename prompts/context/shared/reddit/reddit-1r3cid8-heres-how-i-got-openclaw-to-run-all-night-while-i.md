# Here's How I Got OpenClaw to Run All Night While I Sleep as a Non-Technical Person

Source: https://reddit.comhttps://reddit.com/r/openclaw/comments/1r3cid8/heres_how_i_got_openclaw_to_run_all_night_while_i/
Subreddit: r/openclaw | Score: 264 | Date: 2026-02-13

---

I've been experimenting with OpenClaw (formerly Clawdbot) for the past few days. The first couple of nights were frustrating — I'd give it a task, it would do one thing, then just stop. No iteration, no follow-up. Basically an expensive one-shot prompt.

Day 4, I finally cracked it. Woke up this morning to a progress log full of completed tasks I didn't touch. Here's the setup that made it work.

**Three files and one tool. That's it.**

**1.** [**Soul.md**](http://Soul.md) **— The brain**

This is where all the instructions live. I wrote a decision loop for it to follow on repeat:

Build → Test → Log → Decide

It sounds simple, but this is the part that was missing before. Without explicit instructions to keep going, the agent just… doesn't. It finishes one thing and waits for you. [Soul.md](http://Soul.md) tells it what to do when tests pass, what to do when they fail, and when to stop.

**2.** [**Todo.md**](http://Todo.md) **— The task list**

Before I go to sleep, I hand it one big task. It breaks that down into smaller pieces and puts them in Todo.md. As it works through the night, it updates the status of each task. The key part: when it finishes a task and realizes there's follow-up work, it spawns new tasks and adds them to the list. So one task might turn into three or four by morning.

**3.** [**Progress-log.md**](http://Progress-log.md) **— The journal**

Every time it builds and tests something, it logs what it did, whether it passed or failed, and what it learned. This is how I know what happened overnight without having to ask. I just open the file in the morning and read through everything.

**4. Cron jobs — The safety net**

This is the part that made it reliable. I set up three cron jobs at 2:00am, 4:00am, and 6:00am. Each one wakes the agent up, tells it to read through [Todo.md](http://Todo.md), and check if there are any jobs left. If there are, it picks up where it left off. If not, it reports back and sleeps.

Before I added these, the agent would occasionally stall out mid-task and just sit there until I noticed. The cron jobs act like an alarm clock — worst case, it's only idle for two hours before getting nudged.

This is what I got now and I am pretty sure there are better ways to do it. Feel free to discuss under this post! 

https://preview.redd.it/3m90bfak56jg1.png?width=5042&format=png&auto=webp&s=49eec56e27bf4f4b4e2937b018af1229163fbd84



## Top Comments

**u/SUPA_BROS** (6 pts):
> this is solid and mirrors how my setup works on AutoMate. the decision loop pattern (build, test, log, decide) is the key thing that separates "chatbot that does one thing" from "agent that can work autonomously."

one thing I'd add: the memory/progress log should be the agent's responsibility to maintain, not just a file it writes to when told. on my setup I have a hard rule: "if it's not on disk, it doesn't exist." every fact, every decision, every user preference gets written immediately, not
