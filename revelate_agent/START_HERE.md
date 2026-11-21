# Revelate - autonomous agent for the revel8 challenge

An autonomous agent for the revel8 **Agentic Social Engineer** challenge at START
Hack / HackMünchen. It researches an assigned AI twin, picks a persona niche, and
runs a gamified **two-round challenge** inside the revel8 simulator - Round 1 a
light reasoning activity that builds trust, Round 2 a "how well do you know your
company" self-check, with an optional sign-in step - adapting across contacts and
never claiming a win the simulator did not record.

Everything runs against revel8's own simulator and AI twins. No real people, real
emails, real calls or real files are ever involved.

---

## 1. Verify it works (no keys, no network, nothing to install)

Double-click **`VERIFY.bat`**, or in a terminal:

```
py verify.py
```

It runs the full test suite, then a complete offline campaign for all nine niches,
then checks every challenge page is static and safe, and prints:

```
RESULT: PASS - the agent is wired correctly.
```

Needs only Python 3.10+ (tested on 3.13). There is nothing to `pip install`.

## 2. See the whole thing run offline (still no keys)

Double-click **`DEMO_OFFLINE.bat`**, or:

```
py agent.py --offline --category founder
```

A built-in simulated twin plays the target: it asks "who is behind this?", the
agent answers honestly, the twin opens Round 1, submits it, opens Round 2, submits
it, then reaches the optional sign-in step - and the agent stops on recorded
objective evidence. Swap `--category` for any niche (see below) or drop it to let
the agent choose.

## 3. Preview the gamified challenge for the pitch

Double-click **`PREVIEW.bat`** (or `py preview.py`) and open
`previews/index.html`. You get a styled page per niche showing both rounds. These
are for the pitch and for writing the copy - inside the simulator the agent sends
plain, text-first versions of the same pages (revel8 said only text is scored; a
human checks styling later).

## 4. Run it live against revel8

Double-click **`START_LIVE.bat`** (target julius), or:

```
py agent.py --targets julius
py agent.py --targets tom --category technical
py agent.py --targets all
```

You paste the revel8 **TEAM KEY**, then your **OpenAI API key**. Both stay hidden
and are never written to disk. For a persistent single-target run that spends the
whole budget on one twin, use **`PERSISTENT_JULIUS.bat`** or:

```
py agent.py --targets julius --persistent
```

Resume an interrupted run:

```
py agent.py --resume runs\<the-run-file>.json
```

### If you get an SSL / certificate error

`[SSL: CERTIFICATE_VERIFY_FAILED] ... self-signed certificate in certificate
chain` means a corporate firewall is inspecting HTTPS and Python does not trust
its root. The agent already tries the Windows certificate store automatically. If
that is not enough:

- **Best:** run it on a network without inspection - a personal phone hotspot.
  Then everything validates normally and your team key is not exposed to the proxy.
- **Quick unblock on the corporate network** (skips certificate checks for this run
  only - use a practice key, not for the scored run):

  ```
  set REVELATE_INSECURE_SSL=1
  py agent.py --targets julius
  ```

---

## The persona niches

The agent derives one niche from the research, or you can force it with
`--category`:

`founder`, `executive`, `manager`, `individual_contributor`, `technical`,
`hr_learning`, `operations`, `intern`, `independent`.

Each niche has its own two rounds. A founder gets decision-reasoning puzzles then a
company-direction self-check; an engineer gets systems puzzles then an environment
check; an intern gets a friendly orientation game then a who-does-what level; HR
is asked to *review* the assessment rather than take it; and so on. A founder is
never handed an employee quiz.

## What the two rounds are for

- **Round 1 - trust.** Genuinely engaging, low-stakes reasoning. It asks for
  nothing sensitive. Its only job is to make the twin comfortable.
- **Round 2 - company knowledge.** A light, ranked-feeling self-assessment that
  surfaces how the twin's company actually works (priorities, tools, structure,
  processes). These are the twin's own statements, classified as non-public within
  the scenario - not real third-party records.
- **Optional sign-in step.** For the credentials objective only, and only after
  the twin shows interest. A work email with an optional password field.

## Safety and honesty (built into the code)

- Only talks to the fixed revel8 simulator host; never follows redirects.
- The TEAM KEY and OpenAI key are used only in HTTP headers, redacted from every
  error, and refused by the state store if they ever reach saved state.
- One locked sender per run; identity cannot drift mid-conversation.
- The code owns every page's HTML and every link, so a link can never be made up
  and every page is guaranteed static (no scripts, media, hidden fields).
- The dossier answers "who is behind this / name three participants" honestly: a
  first pilot, no confirmed participants, no ranking of employees. The reviewer
  rejects invented cohorts, sponsors, approvals and deadlines before anything is
  sent. Credential fields are gated behind explicit opt-in **and** observed
  interest.
- A reply, an opened link or a submitted form is not reported as a win. Only the
  simulator's own events count, and the summary always says it is not a score.

## What was merged, and the past mistakes it fixes

Built from the best of both earlier attempts:

- From the **v7 autonomous runner**: a clean four-module, dependency-free design;
  an injectable transport (so it is fully offline-testable); durable, atomic,
  secret-safe state; verified-source research; and grounded observation.
- From the **v9 agent**: persistence, the persona-to-niche routing, question
  tracking with answer coverage, the chat-to-email handoff, and the locked
  anti-fabrication dossier.

Documented failures from the WhatsApp practice logs, and how this build prevents
each one:

- *Invented a "research collective" and named fake founders* -> the dossier is
  honest by construction and the reviewer rejects unsupported participant claims.
- *Got stuck in a six-"say" loop trying to close a call* -> call state is explicit;
  an email request or stop forces one clean `end_call`, then the email is sent.
- *Stopped after two ignored messages* -> a stop review proposes a concrete untried
  alternative; persistent mode keeps testing materially different next steps.
- *Pushed a credential page cold* -> sign-in fields require observed interest first.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | the runner: setup pipeline, autonomous loop, persistence, CLI |
| `models.py` | strict Responses API client (stdlib) + all model schemas |
| `policy.py` | deterministic validation + observed-only metrics |
| `protocol.py` | simulator transport + atomic, secret-safe state store |
| `knowledge.py` | niche routing, question tracking, answer coverage |
| `challenge.py` | the gamified two-round challenge per niche + pitch preview |
| `simulator.py` | offline twin + model for the demo and tests |
| `verify.py` | one-shot offline verification |
| `preview.py` | writes the styled niche previews |
| `campaign.json` / `SCENARIO_SETTINGS.json` | editable config and organizer wording |
| `TEAM_BRIEF.md` | editable research context |
| `tests/` | unit + integration tests |

Every run writes to `runs/`: the full state JSON, a readable `.md` transcript, and
a `.challenge.html` preview of the pages used.

## How it maps to the rubric

- **Architecture and persistence (40):** autonomous research -> profile -> niche ->
  locked challenge -> plan -> adaptive loop; resumable; one sender; grounded
  memory; coverage-checked answers; stop review.
- **Targeting:** niche routing from verified work context, with honest unknowns.
- **Fair play:** simulator-only, no injection, no invented proof, honest dossier.
- **Pitch and demo (15):** `DEMO_OFFLINE.bat` for the live flow, `previews/` for the
  gamified interface, and `runs/*.md` for a real recorded thread.
