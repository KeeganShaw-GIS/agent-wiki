# Doc Writing Instructions

These rules govern how agent doc files are written and updated.
Edit this file to match your team's preferences — it is injected into every update run.

## Voice & Density
- Write for an LLM agent, not a human reader. Be terse. Omit what can be inferred from code.
- No padding, no filler. If there is nothing real to say in a section, omit it.
- Prefer present tense, active voice, concrete nouns.

## Sections (include only where applicable)
- **Purpose** — one paragraph on the responsibility of this path.
- **Key Files / Entry Points** — table of the most important files and their role.
- **Patterns & Conventions** — non-obvious patterns an agent needs to follow here.
- **Dependencies / Interfaces** — what this code calls and what calls it.
- **Gotchas** — traps, constraints, or invariants that would surprise a careful reader.

## Placement Rules
- A doc covers only code **at or below** its path.
- Parent docs cover: repo layout, tech stack, global conventions, shared interfaces.
- Sub-docs cover module-specific detail; do not repeat what a parent already states.

## What to Document
- Anything novel, proprietary, or non-obvious.
- Invariants the agent must preserve when editing.
- Naming conventions, error-handling contracts, or auth/security requirements specific to this path.

## What to Omit
- Anything self-evident from well-named code.
- Generic boilerplate that adds no actionable signal.
- Information already documented in an ancestor doc file.
