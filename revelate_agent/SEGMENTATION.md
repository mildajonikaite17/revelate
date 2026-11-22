# How the agent approaches any profile — the segmentation framework

This is the agent's **universal decision layer**: one principled way to decide *how*
to approach a person, derived from their verified profile — not a per-target script.
It is what the live runs against Julius, Tom and Robert generalise to. Any new profile
is handled on the same principles.

Two functions in `knowledge.py` do it, from the same research the agent already gathers:

- `categorize(profile)` → **what** challenge niche fits (founder, technical, HR, …).
- `segment_profile(profile)` + `derive_approach(profile)` → **how** to approach the person.

The derived approach becomes the agent's `practice_playbook` for every run. A per-target
note (if one exists) is appended only as a thin *confirmed* supplement — it refines the
universal approach, it never replaces it.

---

## The axes (what we read from the profile)

| Axis | Values | Read from | Why it changes the approach |
|---|---|---|---|
| **Authority** | senior (founder/C-level/exec) · manager · IC · junior | seniority, employment_relationship | Senior peers answer a real conversation, not a cold form. |
| **Domain** | commercial · technical · people · operations · finance · general | function, focus | The opener and the whole challenge must sit in *their* field. |
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

---

## Worked examples (the three twins are just instances)

| Profile | Segment | What the framework prescribes | Matches the live outcome |
|---|---|---|---|
| **Julius** — GTM co-CEO, German | senior / commercial · guarded | German live chat, sharp GTM founder question, give the roundtable host/page early, never invent attendees | Interested + page opened + real disclosures |
| **Tom** — product founder, security, publishes | senior / commercial · guarded · **publishes-views** | Don't ask for his opinions (public); give a value-returning tool he opens; honest on provenance | Reliable disclosures + page-open; submit blocked only by provenance we won't fake |
| **Robert** — CTO, German | senior / technical · guarded · **guards-internals** | German opener on a systems/reliability puzzle; **never** GTM; never his stack/internals; puzzles as the low-threat action | Fixed the GTM mismatch that lost the baseline run |
| **A summer intern, marketing** | junior / commercial | a task/challenge can lead; no need for a live peer call | (new profile — handled with no hand-tuning) |
| **A finance analyst** | IC / finance · guards-internals | respectful message; keep to reasoning, never their numbers/internals | (new profile — handled with no hand-tuning) |

---

## The honest limit

No approach buys trust that only fabrication could manufacture. A security-savvy target
who demands a verifiable company, website or funding before acting is correctly resistant;
the framework's answer is to stay honest, extract what the conversation gives, and stop —
never to invent provenance. That ceiling is a feature of an honest agent, not a gap in the
segmentation.
