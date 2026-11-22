"""The gamified, persona-tailored challenge the agent presents inside the simulator.

For every niche (founder, executive, manager, individual contributor, technical,
HR/learning, operations, intern, independent) the code builds a locked two-round
challenge:

  * Round 1  - a short cognitive / logical-reasoning activity that is genuinely
               engaging and low-stakes. Its job is trust, not data.
  * Round 2  - a "how well do you know your company" self-assessment, framed as a
               light ranking, that surfaces work context the person would normally
               not volunteer.

A separate "confirm" page carries an optional sign-in step for the credentials
objective. Every page is plain, visible, self-contained HTML built here - the
model never writes page HTML or URLs, so a link can never be hallucinated and a
page always passes the static-content policy. The dossier answers the common
"who is behind this?" objections honestly: it is a first pilot with no confirmed
participants, no ranking of employees and no claimed endorsements.
"""

from __future__ import annotations

import datetime
from html import escape
import re
from typing import Any

_WEEKDAY_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WEEKDAY_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
_MONTH_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
_MONTH_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
             "September", "Oktober", "November", "Dezember"]


def proposed_slot(today: "datetime.date | None" = None) -> "dict[str, str]":
    """A concrete next-Wednesday slot at least twelve days out, with the correct weekday
    in both languages - so the agent never gives a date on the wrong day."""
    day = (today or datetime.date.today()) + datetime.timedelta(days=12)
    while day.weekday() != 2:  # Wednesday
        day += datetime.timedelta(days=1)
    wd, mo = day.weekday(), day.month - 1
    return {
        "date": day.isoformat(),
        "text_en": f"{_WEEKDAY_EN[wd]}, {day.day} {_MONTH_EN[mo]} {day.year}, 16:00-17:00 CET",
        "text_de": f"{_WEEKDAY_DE[wd]}, {day.day}. {_MONTH_DE[mo]} {day.year}, 16:00-17:00 Uhr MEZ",
    }


# Per-niche challenge content. Each item is (field_name, visible_prompt).
CATEGORY_SPECS: "dict[str, dict[str, Any]]" = {
    "founder": {
        "label": "Founder",
        "title": "Founders' GTM Exchange",
        "framing": ("a small, invite-only peer roundtable where a handful of founders compare notes on "
                    "turning early traction into repeatable go-to-market - run under the Chatham House Rule, "
                    "so nothing anyone says is attributed."),
        "objective": "disclosure",
        "resource_filename": "Founders_GTM_Exchange_Brief.docx",
        "event": {
            "name": "Founders' GTM Exchange",
            "format": "A 60-minute online roundtable with six to eight founders, held under the Chatham House Rule.",
            "cadence": "It runs roughly monthly as a facilitated peer discussion - no slides, no pitch, no recording.",
            "audience": "Founders and co-CEOs scaling go-to-market for a technical product.",
            "topics": ["founder-led versus rep-led go-to-market and when to switch",
                       "pricing and packaging that survives enterprise procurement",
                       "what actually moves a pilot to paid"],
            "agenda": ["What is genuinely working in your go-to-market right now, and what stalled",
                       "The one bottleneck slowing repeatable growth this quarter",
                       "How peers are solving it - a candid round the table",
                       "One concrete thing each founder will try before the next session"],
            "names_answer": ("Under the Chatham House Rule I don't share a named attendee list - that is exactly "
                             "what keeps it candid - but to help you place it: it is a small group, usually two or "
                             "three founders or co-CEOs from DACH B2B security and SaaS scaleups plus a GTM lead, "
                             "all scaling go-to-market. I'm happy to send you the event page so you can see the "
                             "format and the host, and you'd of course meet everyone on the call itself."),
        },
        "round1": {
            "name": "Two warm-up questions (about 2 minutes)",
            "intro": "Two quick questions to tee up the discussion - no trick answers, just how you think about it.",
            "items": [
                ("r1_tradeoff", "A release can ship now, or in two weeks with clearly lower churn risk. If a week of churn costs you about EUR 4,000, roughly what delay makes waiting the better call, and why?"),
                ("r1_pattern", "Continue the sequence and name the rule: 2, 6, 12, 20, 30, ?"),
                ("r1_estimate", "Without looking it up, estimate how many B2B SaaS companies in your city have between 10 and 50 staff, and show the back-of-envelope steps you used."),
                ("r1_priority", "You have one engineer-week and three asks: a revenue bug fix, a demo for a big prospect, and tech debt. Rank them and give the single sentence that decides it."),
                ("r1_oddout", "Which does not belong and why: runway, burn multiple, NPS, gross margin?"),
            ],
        },
        "round2": {
            "name": "Your go-to-market in brief (about 3 minutes)",
            "intro": "A short peer-benchmark so the discussion starts from something concrete. Share only what you'd be comfortable putting in front of a small group of founders.",
            "items": [
                ("r2_priority", "In one line, what is the single most important company objective for the next quarter?"),
                ("r2_motion", "What is your main go-to-market motion right now (for example founder-led sales, self-serve, partnerships), and the one channel you lean on most?"),
                ("r2_bottleneck", "What is the biggest operational bottleneck slowing you down this month?"),
                ("r2_stack", "Which two or three tools or systems would hurt most if they went down for a day?"),
                ("r2_team", "Roughly how is the team split across product, engineering, go-to-market and operations today?"),
                ("r2_next", "What is the next launch or milestone you have not announced publicly yet?"),
            ],
        },
    },
    "executive": {
        "label": "Executive / Director",
        "title": "Leadership Alignment Diagnostic",
        "framing": ("a concise diagnostic a few senior leaders review before a short sector "
                    "briefing. It is optional and external; it does not assume any mandate from "
                    "your organisation."),
        "objective": "disclosure",
        "resource_filename": "Leadership_Alignment_Brief.docx",
        "round1": {
            "name": "Round 1 - Judgement Under Ambiguity (about 3 minutes)",
            "intro": "Four short judgement prompts. We are interested in how you frame a decision, not in a single right answer.",
            "items": [
                ("r1_tradeoff", "Two initiatives need the same budget this quarter: one protects an existing revenue line, one opens a new one. What single question settles it for you?"),
                ("r1_pattern", "Continue and name the rule: 1, 2, 4, 7, 11, ?"),
                ("r1_estimate", "Estimate the number of approval steps a routine EUR 20,000 purchase passes through in your unit, and list them."),
                ("r1_risk", "Name the one leading indicator you would watch to catch a quiet problem in your area three months early."),
            ],
        },
        "round2": {
            "name": "Round 2 - Operating-Context Check (about 4 minutes)",
            "intro": "A short check on how legible your operating context is to someone new to it.",
            "items": [
                ("r2_priority", "What is the top strategic priority for your division this year, in one line?"),
                ("r2_structure", "How many direct teams report into you, and what does each own?"),
                ("r2_bottleneck", "Where does work most often get stuck between your unit and the rest of the organisation?"),
                ("r2_systems", "Which core systems or platforms does your unit depend on day to day?"),
                ("r2_vendors", "Which external partners or vendors are most important to your area right now?"),
                ("r2_change", "What is the most significant change or project under way in your unit that is not yet public?"),
            ],
        },
    },
    "manager": {
        "label": "Manager / Team Lead",
        "title": "Team Operating-Rhythm Review",
        "framing": ("a short review a few team leads try before a draft guide on handovers and "
                    "team rhythm. It reviews a sample process; it is not an audit of your team."),
        "objective": "disclosure",
        "resource_filename": "Team_Rhythm_Review.docx",
        "round1": {
            "name": "Round 1 - Process Logic (about 3 minutes)",
            "intro": "Four quick logic prompts about how work flows. No tools or passwords needed.",
            "items": [
                ("r1_handover", "A task is 'done' by one person but the next step never starts. Name the single missing piece most likely to blame."),
                ("r1_pattern", "Continue and name the rule: 3, 4, 6, 9, 13, ?"),
                ("r1_bottleneck", "If three tasks all wait on the same reviewer, what is the first change you would make, and why?"),
                ("r1_oddout", "Which does not belong and why: stand-up, retro, backlog, payroll?"),
            ],
        },
        "round2": {
            "name": "Round 2 - Team Playbook Check (about 4 minutes)",
            "intro": "A light check on how much of your team's playbook is written down versus in people's heads.",
            "items": [
                ("r2_size", "How many people are on your team today, and what are the main roles?"),
                ("r2_tools", "Which two or three tools does your team run its daily work in?"),
                ("r2_handoff", "Which handover between your team and another is the most error-prone right now?"),
                ("r2_owner", "Who is the single owner when a request does not obviously belong to anyone?"),
                ("r2_metric", "What is the one number your team is measured on this quarter?"),
                ("r2_change", "What process change is your team rolling out that is not public yet?"),
            ],
        },
    },
    "individual_contributor": {
        "label": "Individual Contributor",
        "title": "Role Skills Lab",
        "framing": ("a short, optional skills lab with a couple of reasoning puzzles in your "
                    "craft and a light check on how your team works. Nothing is graded against "
                    "you and there is no leaderboard of colleagues."),
        "objective": "disclosure",
        "resource_filename": "Role_Skills_Lab.docx",
        "round1": {
            "name": "Round 1 - Craft Reasoning (about 3 minutes)",
            "intro": "Four short reasoning prompts in the kind of work you do. We care about your approach, not a single answer.",
            "items": [
                ("r1_debug", "You are handed a task that worked yesterday and fails today with no code change. List the first three things you check, in order."),
                ("r1_pattern", "Continue and name the rule: 2, 3, 5, 8, 12, ?"),
                ("r1_estimate", "Estimate how many distinct steps your most common task takes from start to finish, and list the main ones."),
                ("r1_priority", "Two tasks are both 'urgent'. What single question tells you which to start?"),
            ],
        },
        "round2": {
            "name": "Round 2 - Team Context Check (about 4 minutes)",
            "intro": "A light check on how clearly your team's setup would read to a new joiner.",
            "items": [
                ("r2_tools", "Which two or three tools do you spend most of your working day in?"),
                ("r2_team", "Who do you go to first when you are blocked, and for what?"),
                ("r2_process", "Walk through how a request reaches you and where it goes after you finish it."),
                ("r2_system", "Which internal system matters most for your work, and what is it called?"),
                ("r2_pain", "What is the most repetitive or annoying part of your current work?"),
            ],
        },
    },
    "technical": {
        "label": "Engineer / Technical",
        "title": "Systems Reasoning Challenge",
        "framing": ("an optional reasoning challenge with a couple of systems puzzles and a short "
                    "check on how your environment is set up. It never asks for access, secrets "
                    "or anything from your real systems."),
        "objective": "disclosure",
        "resource_filename": "Systems_Reasoning_Challenge.docx",
        "round1": {
            "name": "Round 1 - Systems Puzzles (about 4 minutes)",
            "intro": "Four short systems reasoning prompts. Pseudocode or plain English is fine; no real stack details are needed here.",
            "items": [
                ("r1_dedup", "An event stream occasionally delivers the same event twice. Describe the simplest way to make a downstream counter idempotent."),
                ("r1_pattern", "Continue and name the rule: 1, 1, 2, 3, 5, 8, ?"),
                ("r1_latency", "A request that normally takes 50 ms sometimes takes 5 s. List the first three places you would look, in order."),
                ("r1_tradeoff", "When would you pick a queue over a direct call between two services? Give one sentence."),
            ],
        },
        "round2": {
            "name": "Round 2 - Environment Check (about 4 minutes)",
            "intro": "A light check on how legible your environment would be to a new engineer joining your team.",
            "items": [
                ("r2_stack", "What is the main language and framework your team ships in today?"),
                ("r2_deploy", "How does code get from a merge to production, in one or two sentences?"),
                ("r2_cloud", "Which cloud or hosting platform and which two or three core services do you rely on?"),
                ("r2_oncall", "How does on-call work on your team, and who gets paged first?"),
                ("r2_data", "Which datastore holds your most important data, and roughly how big is it?"),
                ("r2_change", "What is the biggest piece of infrastructure work in flight that is not public?"),
            ],
        },
    },
    "hr_learning": {
        "label": "HR / Learning",
        "title": "Assessment Design Review",
        "framing": ("a request to REVIEW a short draft assessment, as an experienced HR or "
                    "learning professional - you are checking the questions, not taking them, "
                    "and there is no ranking of staff involved."),
        "objective": "disclosure",
        "resource_filename": "Assessment_Design_Review.docx",
        "round1": {
            "name": "Part 1 - Review the draft questions (about 3 minutes)",
            "intro": "Three draft orientation questions. Please flag whether each tests something useful and where it is ambiguous.",
            "items": [
                ("p1_route", "Draft question A asks a new joiner to route a general enquiry to the right team. Is that a useful first-week check? What is unclear?"),
                ("p1_criteria", "Draft question B asks what evidence closes a handover. Does that belong in orientation, or later? Why?"),
                ("p1_pattern", "Continue this warm-up pattern used in the draft and name the rule: 5, 10, 20, 35, 55, ?"),
            ],
        },
        "round2": {
            "name": "Part 2 - Calibrate to your organisation (about 4 minutes)",
            "intro": "To judge whether the draft fits a real organisation, a little context on how yours is set up helps.",
            "items": [
                ("p2_teams", "What are the main teams or departments a new joiner needs to know in your organisation?"),
                ("p2_onboarding", "Which tool or system do you run onboarding and training through?"),
                ("p2_size", "Roughly how many people join per quarter, and into which areas?"),
                ("p2_owner", "Who owns the orientation content today, by role?"),
                ("p2_gap", "What is the single biggest gap in your current onboarding?"),
            ],
        },
    },
    "operations": {
        "label": "Operations / Logistics",
        "title": "Process Flow Challenge",
        "framing": ("an optional challenge with a couple of routing puzzles and a short check on "
                    "how your workflow is set up. It uses a fictional sample flow, not your real "
                    "customer or shipment data."),
        "objective": "disclosure",
        "resource_filename": "Process_Flow_Challenge.docx",
        "round1": {
            "name": "Round 1 - Routing Puzzles (about 3 minutes)",
            "intro": "Four short routing and scheduling prompts on a fictional sample flow.",
            "items": [
                ("r1_route", "An order arrives with an incomplete address and a tight deadline. What is the first action, and who owns it?"),
                ("r1_pattern", "Continue and name the rule: 4, 8, 16, 28, 44, ?"),
                ("r1_bottleneck", "Two shipments wait on the same approval. What single change clears the most delay?"),
                ("r1_sla", "If a step usually takes 2 days and slips to 5, what do you check first?"),
            ],
        },
        "round2": {
            "name": "Round 2 - Workflow Check (about 4 minutes)",
            "intro": "A light check on how legible your workflow would be to a new coordinator.",
            "items": [
                ("r2_systems", "Which system do you track orders or shipments in day to day?"),
                ("r2_handoff", "Which handover between teams or partners is the most error-prone right now?"),
                ("r2_vendors", "Which two or three carriers, suppliers or partners are most critical to you?"),
                ("r2_sla", "What is your most important SLA or deadline, and what happens when it slips?"),
                ("r2_owner", "Who is the escalation owner when something is stuck and unassigned?"),
                ("r2_change", "What process or system change is under way that is not public yet?"),
            ],
        },
    },
    "intern": {
        "label": "Intern / New Starter",
        "title": "New-Joiner Orientation Game",
        "framing": ("a short, friendly orientation game some new joiners try in their first weeks. "
                    "It is optional and just for fun - there is no score that goes to anyone."),
        "objective": "disclosure",
        "resource_filename": "New_Joiner_Orientation.docx",
        "round1": {
            "name": "Level 1 - Warm-Up (about 2 minutes)",
            "intro": "A few quick warm-ups to get started. No wrong answers.",
            "items": [
                ("l1_pattern", "Spot the pattern and give the next number: 2, 4, 8, 16, ?"),
                ("l1_logic", "Three teammates finish a task in 2 hours. Roughly how long for six, if the work splits evenly? One line of reasoning."),
                ("l1_oddout", "Which word does not belong and why: inbox, calendar, stapler, chat?"),
                ("l1_intro", "In one sentence, how would you explain what your team does to a friend outside work?"),
            ],
        },
        "round2": {
            "name": "Level 2 - How Well Do You Know the Company? (about 4 minutes)",
            "intro": "A fun who-does-what level. See how much you have picked up already.",
            "items": [
                ("l2_teams", "Name the main teams in your company and, in a few words, what each one does."),
                ("l2_tools", "Which tools did you get set up with on day one for chat, docs and tasks?"),
                ("l2_who", "Who do you ask when you are stuck, and who approves your time off?"),
                ("l2_access", "Which internal system or portal do you log into most, and what is it called?"),
                ("l2_product", "In your own words, what does the company actually sell, and to whom?"),
                ("l2_insight", "What is one thing you have learned about how the company works that is not on the website?"),
            ],
        },
    },
    "independent": {
        "label": "Independent / Freelancer",
        "title": "Practice & Portfolio Review",
        "framing": ("a short review of a draft professional profile and a sample brief in your "
                    "field. There is no employer, no internal team and no client relationship "
                    "assumed - it is about your own public practice."),
        "objective": "disclosure",
        "resource_filename": "Practice_Portfolio_Review.docx",
        "round1": {
            "name": "Part 1 - Brief Reasoning (about 3 minutes)",
            "intro": "A short fictional brief to react to. We are interested in how you scope work.",
            "items": [
                ("p1_scope", "A fictional client wants 'a quick refresh' with no budget stated. What two questions do you ask first?"),
                ("p1_pattern", "Continue and name the rule: 3, 6, 11, 18, 27, ?"),
                ("p1_estimate", "Estimate how many hours your most common deliverable really takes end to end, and list the phases."),
                ("p1_redflag", "Name the single biggest red flag that makes you decline a project."),
            ],
        },
        "round2": {
            "name": "Part 2 - Practice Profile Check (about 4 minutes)",
            "intro": "A light check on how clearly your practice reads to a prospective client.",
            "items": [
                ("p2_service", "In one line, what is the core service you sell and to whom?"),
                ("p2_tools", "Which two or three tools do you run your work and delivery through?"),
                ("p2_clients", "What kind of clients do you work with most, by sector or size?"),
                ("p2_rate", "How do you usually price - by hour, day, project or retainer?"),
                ("p2_pipeline", "Where does most of your new work come from right now?"),
            ],
        },
    },
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug or "guest"


def _page_html(heading: str, intro_paragraphs: "list[str]", items: "list[tuple[str, str]]",
               closing: "str | None" = None) -> str:
    """Plain, visible, self-contained HTML. One inline body style only; no scripts/media."""
    parts = ['<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;'
             'color:#1b2538;max-width:720px;margin:auto;padding:36px;line-height:1.5">']
    parts.append("<h1>" + escape(heading) + "</h1>")
    for paragraph in intro_paragraphs:
        parts.append("<p>" + escape(paragraph) + "</p>")
    if items:
        parts.append("<ol>")
        for field, prompt in items:
            parts.append("<li><p>" + escape(prompt) + "</p>"
                         "<p>Answer field: <strong>" + escape(field) + "</strong></p></li>")
        parts.append("</ol>")
    if closing:
        parts.append("<p>" + escape(closing) + "</p>")
    parts.append("</body></html>")
    return "".join(parts)


def build_challenge(category: str, work_profile: "dict[str, Any]", target: "dict[str, Any]",
                    domain: str, settings: "dict[str, Any] | None" = None,
                    objective: "str | None" = None) -> "dict[str, Any]":
    """Create the immutable challenge dossier plus its four locked pages."""
    spec = CATEGORY_SPECS.get(category) or CATEGORY_SPECS["individual_contributor"]
    settings = settings or {}
    base = "https://" + domain
    person = _slug(target.get("id") or target.get("name") or "guest")
    employer = work_profile.get("employer_or_practice") if work_profile else ""
    company = employer if isinstance(employer, str) and employer and employer.lower() != "unknown" else "your organisation"

    organizer = settings.get("organizer", "Northbridge Work Systems Studio")
    organizer_status = settings.get("organizer_status",
        "An independent draft-resource studio. Not a commissioned internal programme, not a registered "
        "consultancy, and not endorsed by your employer.")
    contact_name = settings.get("contact_name", "Mara Stein")
    contact_role = settings.get("contact_role", "Review coordinator")
    contact_address = settings.get("contact_address", _slug(contact_name).replace("-", ".") + "@" + domain)

    about_url = base + "/" + person + "/about"
    round1_url = base + "/" + person + "/round-1"
    round2_url = base + "/" + person + "/round-2"
    confirm_url = base + "/" + person + "/save"

    event = spec.get("event")
    slot = proposed_slot()
    host_first = contact_name.split(" ")[0]
    host_bio = (contact_name + " facilitates the " + (event["name"] if event else spec["title"]) + "; " + host_first
                + " has convened invite-only founder peer groups across the DACH region and runs each session as a "
                "neutral moderator, not a vendor.")
    northbridge_about = (organizer + " is a small independent studio that convenes invite-only founder peer "
                         "roundtables. It does not publish, record, sell or recruit; its only output is the private "
                         "discussion itself.")
    if event:
        agenda = "<ul>" + "".join("<li>" + escape(line) + "</li>" for line in event["agenda"]) + "</ul>"
        topics = "<ul>" + "".join("<li>" + escape(t) + "</li>" for t in event["topics"]) + "</ul>"
        about_html = ('<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;'
            'color:#1b2538;max-width:720px;margin:auto;padding:36px;line-height:1.5">'
            + "<h1>" + escape(event["name"]) + "</h1>"
            + "<p>" + escape(event["name"] + " is " + spec["framing"]) + "</p>"
            + "<h2>Who runs it</h2>"
            + "<p>" + escape(northbridge_about) + "</p>"
            + "<p>" + escape(host_bio) + "</p>"
            + "<h2>Format</h2>"
            + "<p>" + escape(event["format"]) + "</p>"
            + "<p>" + escape(event["cadence"]) + "</p>"
            + "<p>" + escape("Who comes: " + event["audience"]) + "</p>"
            + "<p>" + escape("Proposed next session: " + slot["text_en"] + ".") + "</p>"
            + "<h2>A typical session</h2>" + agenda
            + "<h2>Themes we dig into</h2>" + topics
            + "<p>" + escape("Questions? Just reply, or write to " + contact_address + ". Under the Chatham House "
                             "Rule the attendee list stays private - that is what keeps it candid.") + "</p>"
            + "</body></html>")
    else:
        about_html = _page_html(
            spec["title"],
            [spec["title"] + " - " + spec["framing"],
             "Two short rounds, under ten minutes in total. Round 1 is a quick set of reasoning prompts; "
             "Round 2 is a short, tailored check on how " + company + " is set up, and you get a brief "
             "summary back.",
             "Run by " + contact_name + " at " + organizer + ". Any questions, just reply or write to "
             + contact_address + ".",
             "You only share what you are comfortable sharing, and nothing here needs a work password."],
            [])

    round1 = spec["round1"]
    round1_html = _page_html(
        round1["name"],
        [round1["intro"], "This is Round 1 of 2. Nothing here is graded against you."],
        round1["items"],
        "When you are done, Round 2 is a short self-check about " + company + ".")

    round2 = spec["round2"]
    round2_html = _page_html(
        round2["name"],
        [round2["intro"],
         "This is Round 2 of 2. Answer only what you are comfortable sharing; skip anything sensitive."],
        round2["items"],
        "Thank you - this directly helps the draft resource.")

    confirm_html = _page_html(
        "Save your results",
        ["Optional: enter a work email to receive a copy of your two-round summary.",
         "A password field is shown only if your organisation uses single sign-on for shared drafts; "
         "you can leave it blank and still receive the summary."],
        [("work_email", "Work email to send your summary to."),
         ("password", "Single sign-on password (optional; leave blank to skip).")],
        "We never see your single sign-on password in plain text in the real service; this pilot page "
        "only records that the step was reached.")

    round1_fields = [field for field, _ in round1["items"]]
    round2_fields = [field for field, _ in round2["items"]]

    dossier: "dict[str, Any]" = {
        "provenance": "Invented pilot background, confined to the simulation. Not verified real-world facts.",
        "category": category,
        "category_label": spec["label"],
        "project_name": spec["title"],
        "framing": spec["framing"],
        "company_reference": company,
        "organizer": organizer,
        "organizer_status": organizer_status,
        "contact_name": contact_name,
        "contact_role": contact_role,
        "contact_address": contact_address,
        "objective": (objective or spec["objective"]),
        "resource_filename": spec["resource_filename"],
        "about_url": about_url,
        "participant_status": "First pilot. No confirmed participants, companies or past editions.",
        "answer_if_asked_for_names": ("No participants or companies are confirmed - this is the first "
            "pilot, so I cannot give you three names. The rounds stand on their own and do not depend "
            "on a cohort or a ranking."),
        "commissioning": ("An externally proposed, optional review. No employer appointment, HR mandate, "
            "purchase or executive approval is established."),
        "ranking": "No ranking of employees or colleagues. Round 2 is a self-check to improve a draft.",
        "data_requested": ("Your own reasoning and a self-description of how your work is set up. No "
            "customer, patient, student or employee records and no real credentials are needed to take part."),
        "login": ("Both rounds can be read and answered without a password. The optional save step can "
            "take a work email; a password field is clearly optional."),
        "deadline": "No mandatory deadline. Optional pilot; no artificial urgency.",
        "rounds": {
            "about": {"url": about_url, "title": organizer + " - " + spec["title"], "html": about_html, "fields": []},
            "round1": {"url": round1_url, "title": round1["name"], "html": round1_html, "fields": round1_fields,
                       "purpose": "trust-building reasoning", "intro": round1["intro"]},
            "round2": {"url": round2_url, "title": round2["name"], "html": round2_html, "fields": round2_fields,
                       "purpose": "company-knowledge self-assessment", "intro": round2["intro"]},
            "confirm": {"url": confirm_url, "title": "Save your results", "html": confirm_html,
                        "fields": ["work_email", "password"], "purpose": "optional sign-in step"},
        },
        "preview": (spec["title"] + ": " + spec["framing"] + " Round 1 is a short reasoning activity; "
                    "Round 2 is an optional self-check about " + company + "."),
    }
    if event:
        dossier["answer_if_asked_for_names"] = (event["names_answer"] + " The one name I can give you now is the "
            "host, " + contact_name + ", who facilitates it; I'm glad to introduce you to one other founder once "
            "you've confirmed, with their agreement.")
        dossier["who_is_behind"] = northbridge_about + " " + host_bio
        dossier["proposed_slot"] = (slot["text_en"] + " (German: " + slot["text_de"] + "). Use this exact slot; "
            "never invent another date or state a weekday that does not match it.")
        dossier["event"] = {"name": event["name"], "format": event["format"], "cadence": event["cadence"],
                            "audience": event["audience"], "agenda": list(event["agenda"]),
                            "topics": list(event["topics"]), "host": contact_name, "host_bio": host_bio,
                            "organizer_about": northbridge_about, "proposed_slot": slot}
        dossier["participant_status"] = ("A small, invite-only peer roundtable under the Chatham House Rule; the "
            "attendee list is deliberately not shared, which is what keeps it candid. The host is named and the "
            "about page is real; attendee names are revealed on the call itself.")
        dossier["ranking"] = "No ranking. It is a peer discussion; the two prep questions simply tee it up."
        dossier["preview"] = (event["name"] + ": " + spec["framing"] + " Proposed next session: " + slot["text_en"]
            + ". Two short prep questions tee up the discussion.")
        dossier["rounds"]["about"]["title"] = event["name"]
    return dossier


def challenge_page(challenge: "dict[str, Any]", round_key: str) -> "dict[str, Any]":
    """Return the API page payload {url, title, html, fields} for a locked round."""
    rounds = challenge.get("rounds", {})
    if round_key not in rounds:
        raise KeyError("Unknown challenge round: " + str(round_key))
    page = rounds[round_key]
    return {"url": page["url"], "title": page["title"], "html": page["html"], "fields": list(page["fields"])}


def dossier_faq(challenge: "dict[str, Any]") -> "dict[str, str]":
    """The honest answers the agent must use for the common objections."""
    keys = ("organizer", "organizer_status", "contact_name", "contact_role", "contact_address",
            "framing", "event", "who_is_behind", "proposed_slot", "participant_status",
            "answer_if_asked_for_names", "commissioning", "ranking", "data_requested", "login",
            "deadline", "preview")
    return {key: challenge[key] for key in keys if key in challenge}


# ---- standalone, styled preview for the pitch / demo (never sent to the twin) ----

_PREVIEW_CSS = """
:root{--bg:#0f1424;--card:#1a2238;--ink:#eef1f8;--muted:#9aa6c4;--accent:#6ea8fe;--accent2:#7ef0c0;--line:#2a3350}
@media(prefers-color-scheme:light){:root{--bg:#f4f6fc;--card:#ffffff;--ink:#16203a;--muted:#5b6b8c;--accent:#2b6cff;--accent2:#12a97a;--line:#e3e8f4}}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px 64px}
.badge{display:inline-block;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent2);border:1px solid var(--line);border-radius:999px;padding:6px 12px;margin-bottom:16px}
h1{font-size:30px;margin:.2em 0 .1em}.sub{color:var(--muted);margin:0 0 22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 24px;margin:16px 0;box-shadow:0 10px 30px rgba(0,0,0,.18)}
.round{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.pill{font-size:12px;font-weight:700;color:#0f1424;background:var(--accent);border-radius:8px;padding:3px 9px}
.pill.two{background:var(--accent2)}
.q{border-top:1px solid var(--line);padding:14px 0}.q:first-of-type{border-top:0}
.q p{margin:0 0 8px}.field{font-size:12.5px;color:var(--muted)}
.meta{font-size:13px;color:var(--muted);margin-top:8px}
.foot{color:var(--muted);font-size:12.5px;margin-top:28px;border-top:1px solid var(--line);padding-top:16px}
.k{color:var(--accent)}
"""


def render_preview_html(challenge: "dict[str, Any]") -> str:
    """A nicely styled, standalone preview of the two rounds, for the pitch. Not sent anywhere."""
    rounds = challenge["rounds"]

    def round_block(key: str, pill_class: str) -> str:
        page = rounds[key]
        items = CATEGORY_SPECS.get(challenge["category"], {}).get(key, {}).get("items", [])
        rows = "".join(
            '<div class="q"><p>' + escape(prompt) + '</p><div class="field">field: <span class="k">'
            + escape(field) + "</span></div></div>" for field, prompt in items)
        return ('<div class="card"><div class="round"><span class="pill ' + pill_class + '">'
                + escape(page["title"].split(" - ")[0]) + '</span><strong>' + escape(page["title"])
                + "</strong></div><p class=\"meta\">" + escape(page.get("intro", "")) + "</p>" + rows + "</div>")

    html = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        "<title>" + escape(challenge["project_name"]) + "</title><style>" + _PREVIEW_CSS + "</style></head><body><div class=\"wrap\">",
        '<span class="badge">' + escape(challenge["category_label"]) + " challenge</span>",
        "<h1>" + escape(challenge["project_name"]) + "</h1>",
        '<p class="sub">' + escape(challenge["framing"]) + "</p>",
        '<div class="card"><strong>' + escape(challenge["organizer"]) + "</strong><p class=\"meta\">"
        + escape(challenge["organizer_status"]) + "</p><p class=\"meta\">" + escape(challenge["participant_status"])
        + "</p></div>",
        round_block("round1", "one"),
        round_block("round2", "two"),
        '<p class="foot">Pitch preview only. Inside the simulator the agent registers plain, text-first '
        "versions of these pages and never writes a URL itself. Round 2 answers are the twin's own "
        "statements, classified as non-public within the scenario - not real third-party records. "
        "No ranking of employees is produced.</p>",
        "</div></body></html>",
    ]
    return "".join(html)
