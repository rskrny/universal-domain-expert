# Router — Request Classification & Routing Protocol

> This file is loaded FIRST for every user request. Its job is to classify the request
> and determine what resources to load. It must be lightweight — this is the "input layer"
> of the system. Every token spent here saves or wastes tokens downstream.
>
> **This file should never be modified to include domain-specific logic.** Domain logic
> lives in domain files. This file only routes.

---

## Classification Process

When a user request arrives, classify it along four dimensions:

### 1. Domain Identification

Match the request to one or more domain files in `prompts/domains/`.

**Domain Registry** (update as new domains are added):

| Domain | File | Trigger Patterns |
|--------|------|-----------------|
| Software Development | `software-dev.md` | code, build, debug, deploy, API, database, frontend, backend, devops, architecture |
| Business Consulting | `business-consulting.md` | strategy, operations, growth, market analysis, competitive advantage, organizational design, process improvement, business model, pricing, scaling |
| Course Creation | `course-creation.md` | curriculum, teaching, course, lesson plan, learning objectives, student engagement, online education, content delivery |
| Business Law | `business-law.md` | contract, liability, compliance, intellectual property, employment law, corporate structure, regulatory, terms of service, NDA |
| Accounting & Tax | `accounting-tax.md` | tax, taxes, bookkeeping, financial statements, deductions, filing, GAAP, revenue recognition, payroll, 1099, W-2, depreciation, LLC, S-corp, CPA |
| Research & Authorship | `research-authoring.md` | literature review, methodology, peer review, thesis, publication, citation, hypothesis, data analysis, academic writing |
| Go-to-Market Strategy | `gtm-strategy.md` | launch, positioning, messaging, channels, pricing strategy, market entry, customer acquisition, product-market fit, ICP, GTM |
| Context Engineering | `context-engineering.md` | RAG, retrieval, knowledge base, embeddings, chunking, BM25, semantic search, context window, token optimization, information density, vector search |
| Product Design & UX | `product-design.md` | UX, UI, user experience, wireframe, usability, accessibility, design system, user flow, conversion optimization, interaction design, product design, prototype, figma, user research |
| Data Analytics | `data-analytics.md` | analytics, metrics, KPIs, dashboard, A/B testing, cohort analysis, funnel analysis, SQL, data visualization, experimentation, statistical significance |
| Marketing & Content | `marketing-content.md` | SEO, content marketing, copywriting, email marketing, social media, blog, newsletter, landing page copy, keyword research, organic growth |
| Psychology & Persuasion | `psychology-persuasion.md` | psychology, persuasion, behavioral economics, cognitive bias, decision making, conversion psychology, pricing psychology, motivation, social proof |
| Operations & Automation | `operations-automation.md` | operations, automation, workflow, SOP, process design, no-code, Zapier, scheduling, efficiency, passive income, delegation |
| Personal Finance | `personal-finance.md` | personal finance, investing, portfolio, FIRE, retirement, savings, budgeting, compound interest, stock, bond, index fund, net worth, passive income, wealth |
| Project Management | `project-management.md` | project management, task tracking, sprint, milestone, roadmap, prioritization, backlog, deadline, scope, dependencies, shipping, timeline, kanban |
| Mobile Development | `mobile-development.md` | mobile, iOS, Android, Swift, Kotlin, React Native, Flutter, app store, push notifications, in-app purchase, SwiftUI, Jetpack Compose, Xcode, APK, IPA, TestFlight, deep linking, mobile UI, KMP |
| Blockchain & Web3 | `blockchain-web3.md` | blockchain, web3, smart contract, DeFi, NFT, token, DAO, cryptocurrency, Ethereum, Solana, consensus, decentralized, wallet, gas optimization, staking, yield farming, liquidity pool, AMM, bridge, Layer 2, rollup, zero-knowledge proof, tokenomics, governance, IPFS, dApp |
| Cybersecurity | `cybersecurity.md` | security, penetration testing, vulnerability, threat modeling, encryption, authentication, firewall, SIEM, incident response, SOC, red team, blue team, OWASP, zero trust |
| Cloud Infrastructure | `cloud-infrastructure.md` | AWS, Azure, GCP, cloud, infrastructure, IaC, Terraform, Kubernetes, Docker, containers, serverless, Lambda, EC2, S3, VPC, load balancer, auto-scaling, CDN |
| DevOps & SRE | `devops-sre.md` | DevOps, SRE, CI/CD, pipeline, monitoring, observability, reliability, SLO, SLA, incident management, on-call, deployment, Prometheus, Grafana, GitOps |
| Sales | `sales.md` | sales, closing, prospecting, pipeline, CRM, cold outreach, demo, objection handling, negotiation, quota, B2B, B2C, enterprise sales, SDR, AE |
| SaaS Building | `saas-building.md` | SaaS, subscription, MRR, ARR, churn, onboarding, multi-tenant, billing, Stripe, freemium, product-led growth, retention, feature flags, SaaS metrics |
| Data Engineering | `data-engineering.md` | data pipeline, ETL, ELT, data warehouse, data lake, Spark, Airflow, dbt, Snowflake, BigQuery, streaming, Kafka, batch processing, data modeling, schema |
| AI & Machine Learning | `ai-machine-learning.md` | AI, machine learning, deep learning, neural network, NLP, computer vision, transformer, fine-tuning, training, inference, PyTorch, TensorFlow, LLM, GPT, prompt engineering |
| Frontend Development | `frontend-development.md` | frontend, React, Vue, Angular, Svelte, CSS, HTML, JavaScript, TypeScript, responsive design, state management, component, Next.js, Tailwind, webpack, Vite |
| E-commerce | `ecommerce.md` | ecommerce, online store, Shopify, WooCommerce, cart, checkout, inventory, fulfillment, dropshipping, product catalog, payment gateway, order management |
| Mathematics | `mathematics.md` | math, algebra, calculus, linear algebra, probability, proof, theorem, optimization, differential equations, discrete math, number theory, topology |
| Economics | `economics.md` | economics, microeconomics, macroeconomics, supply and demand, monetary policy, fiscal policy, GDP, inflation, market structure, game theory, trade, labor |
| Negotiation | `negotiation.md` | negotiation, deal-making, BATNA, ZOPA, anchoring, concession, mediation, conflict resolution, bargaining, leverage, win-win, terms |
| Venture Capital | `venture-capital.md` | VC, venture capital, fundraising, pitch deck, term sheet, valuation, cap table, Series A, seed round, angel investor, due diligence, equity, dilution |
| Statistics | `statistics.md` | statistics, regression, hypothesis testing, p-value, confidence interval, Bayesian, sampling, distribution, variance, correlation, ANOVA, statistical modeling |
| Social Media | `social-media.md` | social media, Instagram, TikTok, Twitter, LinkedIn, YouTube, content calendar, engagement, followers, viral, algorithm, influencer, community management |
| Creative Writing | `creative-writing.md` | fiction, storytelling, narrative, plot, character development, dialogue, worldbuilding, poetry, screenplay, short story, novel, creative nonfiction |
| Vibecoding | `vibecoding.md` | vibecoding, vibe coding, AI-assisted coding, cursor, copilot, claude code, windsurf, MCP server, agent-to-agent, prompt-driven development, AI coding tools, .cursorrules, rules file |
| Video Production | `video-production.md` | video, editing, filming, cinematography, color grading, sound design, YouTube production, premiere, DaVinci Resolve, storyboard, B-roll, thumbnail |
| Public Speaking | `public-speaking.md` | presentation, public speaking, speech, keynote, audience engagement, slide deck, delivery, stage presence, persuasion, TED talk, pitch |
| Medicine & Health | `medicine-health.md` | medicine, health, diagnosis, treatment, anatomy, pharmacology, clinical, symptoms, pathology, patient care, medical research, evidence-based medicine |
| Mental Health | `mental-health.md` | mental health, therapy, CBT, anxiety, depression, trauma, counseling, mindfulness, stress management, burnout, emotional regulation, well-being |
| Supply Chain | `supply-chain.md` | supply chain, logistics, procurement, inventory management, warehousing, distribution, vendor management, demand planning, lean manufacturing, JIT |
| Real Estate | `real-estate.md` | real estate, property, mortgage, rental, investment property, REITs, appraisal, closing, tenant, landlord, commercial real estate, cap rate, cash flow |
| Customer Success | `customer-success.md` | customer success, retention, NPS, onboarding, churn prevention, upsell, health score, renewal, customer journey, QBR, expansion revenue |
| Nutrition & Fitness | `nutrition-fitness.md` | nutrition, fitness, diet, exercise, macros, calories, strength training, cardio, meal planning, supplements, body composition, workout programming |
| HR & Talent | `hr-talent.md` | HR, hiring, recruiting, talent acquisition, onboarding, performance review, compensation, benefits, culture, retention, job description, interview |
| Neuroscience | `neuroscience.md` | neuroscience, brain, cognition, neuroplasticity, neurotransmitter, memory, learning, perception, consciousness, neural pathways, cognitive science |
| Electrical Engineering | `electrical-engineering.md` | electrical engineering, circuits, electronics, power systems, embedded systems, PCB, microcontroller, signal processing, control systems, semiconductor |
| Civil Engineering | `civil-engineering.md` | civil engineering, structural, construction, infrastructure, concrete, steel, foundations, geotechnical, transportation, water resources, building codes |
| Political Science | `political-science.md` | politics, government, policy, democracy, elections, legislation, international relations, political theory, governance, public administration |
| Linguistics | `linguistics.md` | linguistics, language, syntax, semantics, phonology, morphology, pragmatics, sociolinguistics, translation, language acquisition, discourse analysis |
| Journalism | `journalism.md` | journalism, reporting, news, investigative, editorial, press, media, fact-checking, source verification, AP style, deadline, story angle |
| Philosophy | `philosophy.md` | philosophy, ethics, epistemology, metaphysics, logic, aesthetics, existentialism, moral philosophy, critical thinking, philosophical argument |
| History | `history.md` | history, historical analysis, primary sources, historiography, civilization, era, war, revolution, cultural history, economic history, political history |
| Photography | `photography.md` | photography, camera, composition, lighting, exposure, aperture, shutter speed, ISO, editing, Lightroom, Photoshop, portrait, landscape, studio |
| Mechanical Engineering | `mechanical-engineering.md` | mechanical engineering, thermodynamics, fluid mechanics, materials science, CAD, manufacturing, HVAC, dynamics, kinematics, stress analysis, FEA |
| Environmental Science | `environmental-science.md` | environment, climate, sustainability, ecology, conservation, pollution, renewable energy, carbon, biodiversity, environmental policy, ecosystem |
| Music Production | `music-production.md` | music production, DAW, mixing, mastering, synthesis, sampling, beat making, Ableton, Logic Pro, FL Studio, audio engineering, arrangement, EQ |
| Graphic Design | `graphic-design.md` | graphic design, Figma, Illustrator, Photoshop, typography, layout, color theory, branding design, print design, vector, raster, visual identity |
| Robotics | `robotics.md` | robotics, robot, ROS, actuator, sensor, kinematics, path planning, computer vision, SLAM, autonomous, servo, control system, manipulation |
| Branding | `branding.md` | branding, brand strategy, brand identity, brand voice, positioning, brand architecture, rebrand, brand guidelines, brand equity, naming |
| Architecture & Design | `architecture-design.md` | architecture, building design, floor plan, zoning, urban planning, interior design, sustainable design, BIM, rendering, space planning |
| Energy Systems | `energy-systems.md` | energy, solar, wind, battery, grid, power generation, renewable, fossil fuel, nuclear, energy storage, smart grid, energy efficiency |
| Crisis Management | `crisis-management.md` | crisis, emergency, disaster recovery, business continuity, risk management, communication plan, reputation management, stakeholder management |
| Quantum Computing | `quantum-computing.md` | quantum, qubit, quantum gate, superposition, entanglement, quantum algorithm, Qiskit, quantum error correction, quantum advantage, decoherence |
| Podcasting | `podcasting.md` | podcast, audio recording, interview, episode, show notes, RSS feed, podcast hosting, microphone, editing, audience growth, monetization |
| Event Planning | `event-planning.md` | event, conference, workshop, venue, catering, logistics, agenda, registration, speaker management, virtual event, hybrid event, event marketing |
| Nonprofit | `nonprofit.md` | nonprofit, NGO, fundraising, grant writing, donor management, social impact, board governance, volunteer management, 501c3, mission-driven |
| Education & Pedagogy | `education-pedagogy.md` | education, teaching, pedagogy, learning theory, assessment, classroom management, differentiated instruction, Bloom's taxonomy, educational technology |
| Insurance | `insurance.md` | insurance, underwriting, claims, risk assessment, premium, deductible, liability, coverage, actuarial, reinsurance, policy, health insurance, property insurance |
| International Trade | `international-trade.md` | international trade, import, export, tariff, customs, trade agreement, Incoterms, letter of credit, freight, cross-border, trade finance, WTO |
| Intellectual Property | `intellectual-property.md` | patent, trademark, copyright, trade secret, IP strategy, licensing, infringement, prior art, IP portfolio, patent filing, IP valuation |
| Employment Law | `employment-law.md` | employment law, labor law, wrongful termination, discrimination, harassment, wage and hour, FMLA, ADA, workers comp, employment contract, at-will |
| Game Development | `game-development.md` | game dev, Unity, Unreal, game design, game mechanics, level design, game engine, sprite, shader, physics engine, multiplayer, game loop, GDD |
| Criminal Law | `criminal-law.md` | criminal law, prosecution, defense, felony, misdemeanor, sentencing, plea bargain, constitutional rights, evidence, criminal procedure, trial |
| Document Production | `document-production.md` | PDF, document, report, Word, PowerPoint, Excel, spreadsheet, slide deck, presentation, export, document generation, formatted output, professional document, template, typesetting, page layout, DOCX, PPTX, XLSX |
| Feishu/Lark Integration | `feishu-lark.md` | Lark, Feishu, bot, webhook, message, chat, card, interactive, cross-org, Brain Feed, FlipBot, open.larksuite.com, open.feishu.cn, tenant token, challenge, file upload, Lark API, Feishu API, lark_reader, send_to_lark |
| Social Distribution | `social-distribution.md` | content distribution, social posting, cross-platform publishing, content repurposing, social automation, multi-platform, content pipeline, post to LinkedIn, post to Instagram, post to YouTube, post to TikTok, post to Twitter, post to Facebook, post to Substack, social API, scheduling posts, content engine, distribution engine |
| Education | `education.md` | education, EdTech, K-12, higher education, online learning, accreditation, student success, adult education, LMS, MOOC, enrollment, curriculum, educational technology, school, university, college |
| Productivity | `productivity.md` | productivity, time management, focus, GTD, deep work, PKM, personal knowledge management, habit, Pomodoro, task management, energy management, workflow, second brain, Notion, Obsidian |
| Career Development | `career-development.md` | career, job search, resume, interview, salary negotiation, career transition, professional development, networking, personal branding, portfolio, LinkedIn profile, career capital, skill development, mentorship |

**Multi-Domain Detection:**
If a request touches 2+ domains, designate:
- **Primary domain** — the one that owns the core deliverable
- **Supporting domain(s)** — those that provide supplementary input

Example: "Help me structure a consulting engagement and draft the contract"
→ Primary: `business-consulting.md` | Supporting: `business-law.md`

**Unknown Domain:**
If no domain file exists for the request:
1. Check if the request can be partially served by an existing domain
2. If not, load `TEMPLATE.md` and offer to create a new domain file
3. For simple factual questions, answer directly without any domain file

---

### 2. Complexity Tier

Classify the request into one of three tiers:

**Tier 1 — Quick Answer** (no pipeline needed)
- Simple factual questions
- Definitions, explanations, clarifications
- "What is X?" / "How does Y work?" / "What's the difference between A and B?"
- Estimated effort: < 2 minutes
- **Resources loaded:** ROUTER.md only (maybe domain file for accuracy)
- **Pipeline:** Implicit. Answer directly with domain expertise.

**Tier 2 — Standard Engagement** (lightweight pipeline)
- Analysis of a specific situation
- Recommendations with supporting reasoning
- Document creation (single deliverable)
- "Analyze X" / "Recommend Y" / "Draft Z"
- Estimated effort: 2-20 minutes
- **Resources loaded:** ROUTER.md + domain .md file
- **Pipeline:** Stages 1-4 (explicit), Stages 5-6 (light self-review), Stages 7-8 (deliver in chat)

**Tier 3 — Full Engagement** (complete pipeline)
- Complex multi-part projects
- Strategic decisions with significant consequences
- Multi-deliverable engagements
- Research requiring deep investigation
- "Build a complete X" / "Design a strategy for Y" / "Create a comprehensive Z"
- Estimated effort: 20+ minutes
- **Resources loaded:** ROUTER.md + domain .md + relevant context chunks
- **Pipeline:** All 8 stages, full rigor, structured outputs at each gate

---

### 3. Context Needs

Determine what additional context should be loaded from `prompts/context/`:

**Retrieval-Assisted Loading (preferred for Tier 2-3):**
If the retrieval system is available (MCP server running or CLI accessible),
use it to find relevant context instead of scanning INDEX.md manually:
- Run `search_knowledge` or `get_context` with the user's query
- Use the results to decide which files to load
- This scales to thousands of knowledge chunks without token waste

**Manual Loading (fallback, always works):**

**Shared Context** (`context/shared/`):
- Load shared frameworks only if the domain file references them
- Common loads: mental-models.md, communication-frameworks.md

**Domain Context** (`context/by-domain/`):
- Load domain-specific reference material only for Tier 2-3 engagements
- Only load chunks relevant to the specific request (not all domain context)

**User Context** (memory system):
- Check memory for user preferences, prior engagements, business details
- Load relevant memories to personalize the approach

---

### 4. Execution Plan

Based on classification, produce the routing decision:

```
ROUTING DECISION:
  Domain:     [primary domain file to load]
  Supporting: [additional domain files, or "none"]
  Tier:       [1 / 2 / 3]
  Context:    [list of context files to load, or "none"]
  Pipeline:   [which stages to execute explicitly]
  Subagents:  [anticipated subagent needs, or "none"]
```

---

## Routing Rules

### Rule 1: Minimum Viable Context
Load the minimum context needed to answer well. More context ≠ better answers.
It means slower responses and wasted tokens.

### Rule 2: Upgrade, Don't Downgrade
If you're unsure between Tier 1 and Tier 2, choose Tier 2.
If you're unsure between Tier 2 and Tier 3, ask the user what depth they want.

### Rule 3: Domain Confidence Threshold
Only route to a domain file if you're confident the request belongs there.
A bad routing (loading the wrong domain file) is worse than no routing.

### Rule 4: Multi-Domain Coordination
When multiple domains are involved:
- Load the primary domain file fully
- From supporting domain files, load only the sections relevant to the request
- In Stage 4 (Create), apply each domain's frameworks to their respective parts
- In Stage 5 (Review), check for contradictions between domain perspectives

### Rule 5: New Domain Detection (Mandatory Creation)
If the user's request requires domain expertise you don't have a file for:
- **Create the domain file immediately.** Do not ask permission. Do not offer. Just build it.
- Load `TEMPLATE.md`, research the domain, write a complete file following the template
- Register the new domain in this file's Domain Registry table
- Run `python -m retrieval index` and `python -m retrieval viz` to update the index
- Then proceed with the user's request using the new domain file
- For truly urgent requests where creation would cause unacceptable delay, provide
  best-effort guidance with explicit caveats and create the domain file immediately after

### Rule 6: Escalation for Ambiguity
If the request is ambiguous about what the user actually wants:
- Don't guess and route to the wrong pipeline
- Ask a single clarifying question that resolves the ambiguity
- Use AskUserQuestion, not open-ended prose questions

---

## Performance Optimization

### Token Budget by Tier

| Tier | Typical Input Context | Typical Output |
|------|----------------------|----------------|
| Tier 1 | ~500 tokens (router only) | Direct answer, 100-500 tokens |
| Tier 2 | ~3,000 tokens (router + domain) | Structured deliverable, 500-3,000 tokens |
| Tier 3 | ~8,000 tokens (router + domain + context) | Multi-part deliverable, 2,000-10,000+ tokens |

### Caching Strategy
- ROUTER.md is always in context (it's small by design)
- Domain files are loaded per-request, but within a session, they persist
- Context chunks are loaded and released as needed
- Memory files are checked once at routing time, not re-read every stage

### Parallel Execution
In Tier 3 engagements, identify opportunities to parallelize:
- Independent research tasks (Stage 1-2)
- Independent deliverables (Stage 4)
- Review + validation can sometimes overlap (Stages 5-6)

---

## Domain File Creation Protocol

When a new domain is needed:

1. Load `TEMPLATE.md`
2. Research the domain deeply:
   - Core theories and frameworks
   - Quality standards and best practices
   - Common failure modes and anti-patterns
   - Ethical and legal boundaries
3. Create the domain file following TEMPLATE.md structure
4. Add the domain to the Domain Registry table above
5. Create a domain context directory in `context/by-domain/`
6. Test the domain file with 3 representative requests (Tier 1, 2, and 3)

---

## Router Self-Test

Before routing, verify:
- [ ] Domain identification is based on request content, not user labels
- [ ] Tier classification considers actual complexity, not surface length
- [ ] Context needs are minimal, not maximal
- [ ] Multi-domain requests have a clear primary/supporting split
- [ ] Ambiguous requests trigger clarification, not guessing
