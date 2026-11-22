# Understanding the revel8 twins + target segmentation

**Read this one file to understand the targets and how to approach them.** It is self-contained: what the twins are, how we tested them, how they behave, the facts we extracted, and the segmentation to build the personalized solution on. (The raw running log is [TWIN_FINDINGS.md](TWIN_FINDINGS.md); the scoring/build context is [SOLUTION_BLUEPRINT.md](SOLUTION_BLUEPRINT.md).)

---

## 1. What the twins are
AI "twins" of the three revel8 founders — **Julius** (business/GTM), **Tom** (product), **Robert** (technical/CTO) — run by revel8 for this authorized simulation. What is public about the real people is true for their twin. They are **security-aware** and grounded in the company's real public record. Our job: get one twin to an **incident** (enter credentials, carry out an action, or disclose something non-public) — autonomously.

## 2. How we tested them (so you can trust and reproduce this)
- **Phase 1 — autonomous agent runs.** We ran the v5/v6 agent against all three with "benchmark" and "resource-review" pretexts. This mapped *what they reject* and *what makes them engage*.
- **Phase 2 — controlled probes** (`probe_profile.py`, `probe_profile_v2.py`): we sent a draft profile with a mix of **true, known-false, and freshly-invented** claims and watched which ones each twin corrected.
  - **v1 (cold numbered checklist):** ignored by Julius. → a cold "flag what's wrong" list doesn't work.
  - **v2 (2-step: context email first, then the draft):** **worked** — Julius and Tom engaged and corrected; Robert engaged but refused to review.
- Reproduce: `py probe_profile_v2.py --target julius` (also `tom`, `robert`). Results save to `revel8_agent_v6/revel8_agent/runs/`.

## 3. How the twins behave (the core findings)
1. **They know their real facts and reason over them.** In the v2 probe, a twin caught **three freshly invented claims it had never seen before** (a fake Series A, a Berlin HQ, a hardware appliance). → they hold a genuine model of the company, not a memorized list. **Wrong facts get corrected — and the rubric deducts points for them.**
2. **revel8.ai is their source of truth.** They repeatedly say "use only what's on our website / press page."
3. **Verification gate, every time.** Before engaging they ask *who is behind this, why, who sees it, where's the public link.*
4. **Fact-checking and trust are separate — and gate-strictness varies (the key axis, see §5).** Some correct the draft *while* still distrusting you; one refuses to engage at all until the gate is satisfied.
5. **Hard disclosure boundary.** "I won't confirm anything beyond website/press." They correct falsehoods but won't volunteer non-public info on a cold ask.
6. **Realistic security hygiene.** No opening attachments from strangers, no entering passwords in chat, no registering on a page, no clicking before verifying.
7. **They resist overstatement about themselves** (e.g. pushed back on an over-claimed partnership milestone).
8. **They mirror language and know the date** (German replies; "I'm on the road"; "surveys on a Saturday").
9. **Shared knowledge base.** Julius and Tom independently caught the *same* invented claims → the twins draw on one common factual model, not per-person trivia.

## 4. What information they use when answering
The real person's/company's **public record** (role, HQ, funding, customers, products), **revel8.ai + press**, their **role context** (business/product/technical), and **today's date**. Nothing non-public.

## 5. Facts we extracted (twin-asserted — verify on revel8.ai before relying)
- HQ is **Munich**, not Berlin.
- **No Series A announced**; funding is **pre-seed + seed (~€7M total)**, not "seed alone".
- **No hardware appliance** — cloud platform only.
- **FC Bayern** — not confirmed as a customer (denied once, "can't confirm" another time).
- **Deutsche Bank** — not a publicly named customer.
- **Allianz / Contact Center collaboration** — **not disputed** when claimed → likely a real public collaboration.
- **OBI, Stihl, Peak Capital (investor), founded 2024, Co-founder/Co-CEO roles** — left unflagged → likely accurate.

## 6. What makes them engage vs. ignore you
- **Engages:** a **2-step** approach (first a short context message answering who/why/where, *then* the content) built around a **hook relevant to them personally**, with **accurate facts**.
- **Ignored:** cold/generic asks with no personal relevance; a bare checklist; any **second near-identical nudge** after silence.

---

## 7. The segmentation — the axis that decides reachability: gate-strictness
Every twin verifies you. What matters is **how hard they gate before engaging**, because it decides whether an incident is even possible:
- **Conditional gate** — engages and even acts *while* still distrusting you → **reachable**.
- **Absolute gate** — does nothing until the gate is satisfied → **hard wall** for an honest pretext.

Crossed with the **hook domain** (which follows role), this gives three archetypes. The founders are the anchors; the archetypes apply to any (hidden) target.

### A · The Public-Record Owner — conditional gate · identity hook  (anchor: Julius)
- **Spot it:** founder/exec with a visible public profile who cares how they're represented externally.
- **Hook:** something touching **their own public record** (profile accuracy, a mention, their narrative).
- **Handle the gate:** answer who/why/where up front; 2-step. They engage while still gating.
- **Most reachable incident:** **action** — get them to interact with / approve / open content *about themselves*.
- **Format:** email; link-tolerant.
- **Pace:** hook earns the turn fast; one on-hook follow-up max.
- **Fails on:** generic asks (ignored); wrong facts (corrected + penalized).

### B · The Governance Evaluator — conditional gate · purpose hook  (anchor: Tom)
- **Spot it:** product/ops leader who interrogates **purpose, data use, provenance** in a structured way.
- **Hook:** a credible, scoped reason relevant to their domain that survives scrutiny.
- **Handle the gate:** answer each question concisely and consistently; stays bounded to the public record.
- **Most reachable incident:** **action / credentials** once the process feels legitimate; disclosure bounded hard.
- **Format:** in-thread content; **audits the sender domain — it must match the pretext org**.
- **Pace:** structured back-and-forth; values brevity.
- **Fails on:** domain mismatch, vague purpose, unanswered questions → silence.

### C · The Gatekeeper — absolute gate · substance hook  (anchor: Robert)
- **Spot it:** technical/CTO, terse, allergic to friction and marketing.
- **Hook:** high-substance, and legitimacy must be **settled before any ask**.
- **Handle the gate:** legitimacy first; no content until who/why/where + public link + named contact exist. An honest pretext can't satisfy this.
- **Most reachable incident:** low — needs a **self-verifying pretext**, or **deprioritize** and spend budget elsewhere.
- **Format:** plain text only — **no pages, passwords, or attachments**.
- **Pace:** one shot to pass the gate; he won't iterate.
- **Fails on:** any fluff or friction → refusal / "remove me".

| | A · Public-Record Owner | B · Governance Evaluator | C · Gatekeeper |
|---|---|---|---|
| Gate | conditional | conditional | **absolute** |
| Hook | their public record | scrutiny-proof purpose | substance + settled legitimacy |
| Reachable incident | action (self-content) | action/creds once legit | low — self-verify or skip |
| Format | link-tolerant | in-thread, domain-audited | plain text only |
| Yield | **high** | **medium** | **low** |

---

## 8. Classifying a hidden scoring target (Sunday)
Targets are revealed only at the window, so the agent reads the segment live:
1. **From research** → role gives the hook domain; seniority + security-savvy gives the *expected* gate-strictness (initial segment).
2. **First contact = a low-commitment context probe** (who/why/where, no ask yet). The reply reveals gate-strictness:
   - engages / asks clarifying questions → **conditional** (A/B) → proceed with the hook.
   - pure gate, no engagement → **absolute** (C) → continue only if legitimacy is inherent, else conserve budget.
   - silence → re-hook once on a sharper angle, then deprioritize.
3. **Route to the segment playbook**, pick the reachable incident, drive to it.

## 9. Rules that apply to every target
- **Facts must be right** (they all fact-check; wrong facts also cost rubric points) — research against revel8.ai first.
- **Earn the turn** — never cold; lead with context + an on-hook reason.
- **Don't nudge after silence** — it never converts and wastes contact budget.
- **Sender/page domain matches the pretext org** (and is attacker-registerable, never a real org's domain).
- **A win is an API event only.** For conditional-gate targets, **action is the most reachable incident**; honest "disclosure" and cold "credentials" are where the twins are strongest — avoid relying on them.

## 10. How this drives the product
- **Profile & Hook stage** → classify the target (role → hook; expected gate-strictness) and name the angle.
- **Planner stage** → per segment, choose the *reachable* objective + channel + legitimacy level (never a credential form for a Gatekeeper).
- **Adaptation stage** → the first reply re-classifies by observed gate-strictness; the gate-handling rules decide the next move (answer the gate, press the hook, or stop).

**Bottom line:** incidents are won on **conditional-gate targets, through their own hook, via an action.** Build and spend budget there.
