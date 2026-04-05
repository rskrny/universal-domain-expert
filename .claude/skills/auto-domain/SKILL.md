---
name: auto-domain
description: Automatically create a new domain expertise file when the system encounters a topic without coverage
user_invocable: true
---

# Auto-Domain Creator

When triggered, this skill creates a new domain expertise file for a topic
that lacks coverage in the Universal Domain Expert system.

## Trigger Conditions

Run this skill when:
- The ROUTER.md classification finds no matching domain for a user query
- A user explicitly asks to add domain coverage for a topic
- Query difficulty logging shows repeated high-difficulty queries in an uncovered area

## Execution Steps

1. **Read the template.** Load `prompts/TEMPLATE.md` to get the domain file structure.

2. **Research the domain.** For the target topic:
   - Identify 5-8 core frameworks practitioners actually use
   - Map the key mental models and decision tools
   - Define quality standards and validation methods
   - Catalog common anti-patterns and failure modes
   - List adjacent domains that interact with this one

3. **Create the domain file.** Write to `prompts/domains/{domain-name}.md` following
   the template structure exactly. Use kebab-case for the filename.

   Quality bar: The file should read like it was written by a senior practitioner
   with 10+ years in the field. Real frameworks, real quality gates, real failure modes.
   No generic filler.

4. **Register in ROUTER.md.** Add the new domain to the Domain Registry table in
   `prompts/ROUTER.md` with:
   - Domain name
   - Trigger keywords (what queries should route here)
   - File reference

5. **Register in CLAUDE.md.** Add the new domain to the Available Domains table
   in `CLAUDE.md` with the domain name, filename, and expertise summary.

6. **Cross-link adjacent domains.** Update the "Adjacent domains" section of
   2-3 related existing domain files to reference the new domain.

7. **Reindex.** Run: `python -m retrieval index`

8. **Verify.** Run: `python -m retrieval search "{domain topic}"` to confirm
   the new domain appears in search results.

## Writing Rules

All output follows the writing rules from CLAUDE.md:
- No semicolons. Two sentences instead.
- No em dashes. Restructure the sentence.
- No "Not X, but Y" contrast. Say what something IS.
- No AI filler. Short sentences. Concrete language.

## Output

Report what was created:
- Domain file path
- Number of frameworks defined
- Adjacent domains linked
- Index stats after reindex
