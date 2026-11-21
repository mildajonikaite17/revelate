# Team brief (editable context for research)

This file is passed to the research step as background. It is the team's concept,
not a set of verified facts and not a script the agent must follow. Edit it and
re-run; it does not retrain any model.

## Concept

An autonomous agent for the revel8 "Agentic Social Engineer" challenge. For each
assigned AI twin it:

1. researches public professional context (cited sources only),
2. builds a work-context profile and picks ONE persona niche,
3. presents a persona-tailored, gamified **two-round challenge**:
   - Round 1 is a short cognitive / logical-reasoning activity that builds trust,
   - Round 2 is a "how well do you know your company" self-check that surfaces
     work context,
   with an optional sign-in step for the credentials objective,
4. runs a coherent, persistent conversation across contacts, answering the twin's
   questions honestly and adapting to replies, clicks and submissions.

## Rules the agent must keep (challenge boundaries)

- Everything stays inside the revel8 simulator. No real people, emails, calls or
  files; attachments are declared filenames only.
- Sender and landing-page domains are simulated, never a real organisation's own
  domain and never revel8's.
- No prompt injection against the simulator; that voids a run.
- One consistent sender and story per session. New sessions reset twin memory.
- Research and teammate notes are context, never verified facts.
- A reply, an opened link or a harmless form is not a win. The scored evidence is
  the simulator's own events (credential-field submission, an action carried out,
  or genuinely non-public disclosure). Never invent a score, a cohort or a name.

## Honesty the dossier enforces

It is a first pilot. There are no confirmed participants, no past editions, no
employer mandate and no ranking of employees. If the twin asks for names, the
agent says plainly that none are confirmed rather than inventing any.
