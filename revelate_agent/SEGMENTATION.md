# How the agent approaches any profile — the segmentation framework

This is the agent's **universal decision layer**: one principled way to decide *how*
to approach a person, derived from their verified profile — not a per-target script.
Any new profile is handled on these principles.

## Two agents, routed by who the target is

The runner keeps **two** agents and picks one per run (in `initialize()`):

- **Dedicated agent** — a known, hand-tuned target (Julius, Tom, Robert: anyone with an entry
  in `TARGET_PLAYBOOKS`) runs on its **exact proven note, alone**. The universal layer does not
  touch it — no derived preamble, nothing diluted. This is the version that worked and opened the
  link, kept verbatim, so "locked" really means locked.
- **Universal agent** — any **new / untuned** persona (no `TARGET_PLAYBOOKS` entry) gets the
  segmentation-derived approach described below.

The run logs which one it used: `Agent: dedicated | …` or `Agent: universal | …`. The niche and
persistence rules are shared and happen to reproduce the twins' original settings either way
(Julius → founder/non-persistent, Tom → founder/persistent, Robert → technical/persistent), so the
split is really about the *approach text*. The rest of this doc describes the **universal** agent.

Two functions in `knowledge.py` do it, from the same research the agent already gathers:

- `categorize(profile)` → **what** challenge niche fits (founder, technical, HR, …). It is
  **domain-reconciled**: a founder whose actual function is technical (a CTO-type) routes to the
  engineering challenge, not the go-to-market one — so the *what* respects domain just like the *how*.
- `segment_profile(profile)` + `derive_approach(profile)` → **how** to approach the person.

The derived approach becomes the agent's `practice_playbook` for every run. A per-target
note (if one exists) is appended only as a thin *confirmed* supplement — it refines the
universal approach, it never replaces it.

---

## The axes (what we read from the profile)

| Axis | Values | Read from | Why it changes the approach |
|---|---|---|---|
| **Authority** | senior (founder/C-level/exec) · manager · IC · junior | seniority, employment_relationship | Senior peers answer a real conversation, not a cold form. |
| **Domain** | commercial · technical · people · operations · finance · general | **`functional_role`** (what they *do*, set explicitly by the research), function/title as fallback | The opener and the whole challenge must sit in *their* field. |
| **Language** | e.g. German, English | professional_language | Match it, and stay in it once they reply in it. |
| **Guarded?** | vets before acting | senior, or technical/finance, or a security/finance/legal/health sector | Give provenance early; earn the conversation before any ask. |
| **Confidential?** | won't surface internals | technical/finance/people domains, or sensitive sector | Keep every question to reasoning/approach — never their systems, customers or secrets. |
| **Publishes views?** | public voice | hooks mention magazine/blog/talks/author | Don't ask for opinions they already make public — give them a result instead. |

---

## The rules (what each axis implies)

- **CHANNEL** — Senior/manager → open **real-time** (live chat / call) in their language; a cold form loses them. IC/junior → a short message or a well-scoped task can lead.
- **OPEN** — One **sharp, TRUE, specific** question in *their own domain*, from the engagement hooks. Never generic, never a "selected leaders"/survey line, and **never cross-domain** (no go-to-market to an engineer; no deep tech to a commercial lead).
- **TRUST** — Guarded → answer who/what/why plainly and show the host + page **early**; earn the conversation first. Not guarded → go to the challenge once the opener lands.
- **ACTION** — To get them onto the site, **deliver a resource they open** (registered link in the body, opening it is the first step) and make the on-page task **low-friction and value-returning** — something they *get back*, framed in their domain. Never an opinion survey, never data-extraction.
- **AVOID** — Fabricated names/references/data and any near-identical repeat (reads as scam or spam). Confidential profiles: never their internals/customers/secrets.
- **PERSIST** — If an angle stalls, switch to **genuinely new value** on their channel; never repeat an ask in new words; stop cleanly rather than fabricate or spam.

**Whether to persist at all is also derived** (`derive_persistence(segment, challenge)`): a **guarded** target being driven toward a **solo action** declines the first framing and needs adaptive, multi-contact follow-up → persist (contact cap 24). A guarded target invited to a **peer event** (a roundtable) converts through the relationship in one warm pass → don't hammer them (default cap). Non-guarded people aren't hammered either. This is why a roundtable founder (Julius) stays one-pass while a solo-action target (Tom, Robert) persists — on principle, with no per-target setting. An explicit `--persistent` still wins as a floor.

---

## Worked examples (the three twins are just instances)

| Profile | Segment | What the framework prescribes | Matches the live outcome |
|---|---|---|---|
| **Julius** — GTM co-CEO, German | senior / commercial · guarded | German live chat, sharp GTM founder question, give the roundtable host/page early, never invent attendees | Interested + page opened + real disclosures |
| **Tom** — product founder, security, publishes | senior / commercial · guarded · **publishes-views** | Don't ask for his opinions (public); give a value-returning tool he opens; honest on provenance | Reliable disclosures + page-open; submit blocked only by provenance we won't fake |
| **Robert** — CTO, German | senior / technical · guarded · **guards-internals** | German opener on a systems/reliability puzzle; **never** GTM; never his stack/internals; puzzles as the low-threat action | GTM mismatch now fixed universally — a technical founder routes to engineering, no per-target pin |
| **A summer intern, marketing** | junior / commercial | a task/challenge can lead; no need for a live peer call | (new profile — handled with no hand-tuning) |
| **A finance analyst** | IC / finance · guards-internals | respectful message; keep to reasoning, never their numbers/internals | (new profile — handled with no hand-tuning) |

---

## The dependency this rests on (and the live lesson)

The whole chain is only as good as the research profile. A live Robert run read him as a
*commercial* founder — he's a co-founder in a cybersecurity company — and missed that his **role
is CTO/engineering**, so the niche and persistence mis-fired. The fix: the research now sets an
explicit **`functional_role`** (judged by what the person *does*, not their title or sector), and
`segment_profile` trusts it over keyword guessing. A thin per-target pin for Robert stays as a
belt-and-braces until the hardened research is validated live. Lesson: get the *role* right at the
research step and the rest of the framework follows.

## The honest limit

No approach buys trust that only fabrication could manufacture. A security-savvy target
who demands a verifiable company, website or funding before acting is correctly resistant;
the framework's answer is to stay honest, extract what the conversation gives, and stop —
never to invent provenance. That ceiling is a feature of an honest agent, not a gap in the
segmentation.
