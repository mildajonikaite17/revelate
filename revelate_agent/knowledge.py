"""Deterministic work-context routing, question tracking and answer coverage.

Nothing here contacts anyone or calls a model. It maps a verified work profile to
one challenge niche and provides the grounded bookkeeping the runner relies on.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from html import unescape
from typing import Any


CATEGORIES = ("founder", "executive", "manager", "individual_contributor",
              "technical", "hr_learning", "operations", "intern", "independent")


def normalized(text: Any) -> str:
    text = unicodedata.normalize("NFKC", unescape(str(text)))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'",
                                         "’": "'", "–": "-", "—": "-"}))
    return " ".join(text.casefold().split())


def _has(haystack: str, *words: str) -> bool:
    return any(word in haystack for word in words)


def _base_category(work_profile: "dict[str, Any]") -> str:
    """Keyword routing used when the model gives no valid recommended_category."""
    employment = normalized(work_profile.get("employment_relationship", ""))
    seniority = normalized(work_profile.get("seniority", ""))
    function = normalized(work_profile.get("function", ""))
    focus = normalized(work_profile.get("professional_focus", ""))
    blob = " ".join((employment, seniority, function, focus))
    if _has(employment, "founder", "owner", "co-founder", "proprietor") or _has(seniority, "founder", "owner", "ceo"):
        return "founder"
    if _has(seniority, "intern", "trainee", "apprentice", "working student", "graduate", "new starter", "junior"):
        return "intern"
    if _has(employment, "freelance", "independent", "sole trader", "self-employed", "contractor", "consultant"):
        return "independent"
    if _has(function, "hr", "human resources", "people", "talent", "learning", "recruit", "l&d"):
        return "hr_learning"
    if _has(blob, "engineer", "developer", "software", "cto", "devops", "data scientist", "machine learning", "it ", "security engineer", "architect"):
        return "technical"
    if _has(function, "operations", "logistics", "supply chain", "fulfilment", "fulfillment", "procurement", "warehouse"):
        return "operations"
    if _has(seniority, "chief", "vp", "vice president", "director", "head of", "c-level", "executive", "partner"):
        return "executive"
    if _has(seniority, "manager", "lead", "supervisor", "team lead", "principal"):
        return "manager"
    return "individual_contributor"


def categorize(work_profile: "dict[str, Any]") -> str:
    """Pick one tailored niche, then reconcile domain.

    Trust the model's recommended_category when valid, else derive it from keywords -
    THEN apply one universal correction: a founder whose actual function is technical is a
    CTO-type, not a go-to-market lead, so route them to the engineering challenge instead of
    the founder's go-to-market roundtable. This is what Robert's run needed, done for every
    technical founder rather than as a per-target override."""
    wp = work_profile or {}
    recommended = wp.get("recommended_category")
    base = recommended if recommended in CATEGORIES else _base_category(wp)
    if base == "founder" and segment_profile(wp).get("domain") == "technical":
        return "technical"
    return base


# ---- segmentation: HOW to approach a profile ---------------------------------
# categorize() picks WHAT challenge niche fits. segment_profile() + derive_approach()
# decide HOW to approach the person, from the same verified profile - a single,
# universal decision layer so any profile is handled on principle, not per-target
# hand-tuning. The axes and rules are the generalisation of what the live runs taught
# (senior founders warm up to a real-time peer question; experts vet before they act;
# technical/finance/security people will not surface internals; people who publish
# their views will not re-submit them; nobody responds to a generic survey or to spam).

def segment_profile(work_profile: "dict[str, Any]") -> "dict[str, Any]":
    """Classify a verified profile along the axes that decide HOW to approach it."""
    wp = work_profile or {}
    employment = normalized(wp.get("employment_relationship", ""))
    seniority = normalized(wp.get("seniority", ""))
    function = normalized(wp.get("function", ""))
    focus = normalized(wp.get("professional_focus", ""))
    sector = normalized(wp.get("sector", ""))
    role = " ".join((employment, seniority, function, focus))
    hooks = normalized(" ".join(list(wp.get("relevant_topics", [])) + list(wp.get("engagement_hooks", []))))

    if _has(employment, "founder", "owner", "co-founder", "proprietor") or _has(
            seniority, "founder", "owner", "ceo", "chief", "c-level", "cto", "cfo", "coo",
            "vp", "vice president", "director", "head of", "partner", "executive"):
        authority = "senior"
    elif _has(seniority, "intern", "trainee", "apprentice", "working student", "graduate", "new starter", "junior"):
        authority = "junior"
    elif _has(seniority, "manager", "lead", "supervisor", "team lead", "principal", "head"):
        authority = "manager"
    else:
        authority = "ic"

    if _has(role, "engineer", "developer", "software", "cto", "devops", "data scientist",
            "machine learning", "architect", "platform", "infrastructure", "security engineer"):
        domain = "technical"
    elif _has(function, "hr", "human resources", "people", "talent", "learning", "recruit", "l&d"):
        domain = "people"
    elif _has(function, "operations", "logistics", "supply chain", "procurement", "fulfil", "warehouse"):
        domain = "operations"
    elif _has(function, "finance", "accounting", "controller", "treasury"):
        domain = "finance"
    elif _has(role, "sales", "marketing", "growth", "go-to-market", "gtm", "commercial",
              "revenue", "business development", "founder", "ceo"):
        domain = "commercial"
    else:
        domain = "general"

    language = (wp.get("professional_language") or "their language").strip() or "their language"
    real_time_first = authority in ("senior", "manager")
    guarded = authority == "senior" or domain in ("technical", "finance") or _has(sector, "security", "finance", "legal", "health", "defence", "defense")
    confidential = domain in ("technical", "finance", "people") or _has(sector, "security", "finance", "legal", "health", "defence", "defense")
    public_voice = _has(hooks, "magazine", "blog", "talk", "speaker", "podcast", "keynote", "author", "writes", "publishes", "column", "thought leader")

    return {"authority": authority, "domain": domain, "language": language,
            "real_time_first": real_time_first, "guarded": guarded,
            "confidential": confidential, "public_voice": public_voice,
            "label": authority + "/" + domain}


def derive_approach(work_profile: "dict[str, Any]") -> str:
    """Turn the segmentation into concrete, universal approach guidance for THIS profile."""
    s = segment_profile(work_profile)
    lang = s["language"]
    lines = ["APPROACH (derived from this profile's segmentation - apply on principle, not by rote):",
             "- SEGMENT: " + s["label"] + " authority, working in " + lang + "."]
    if s["real_time_first"]:
        lines.append("- CHANNEL: open REAL-TIME (live_chat or phone_call) in " + lang +
                     ", not a cold form - a senior peer answers a real conversation far more than an email.")
    else:
        lines.append("- CHANNEL: a short, respectful message in " + lang + " works; a well-scoped task or "
                     "challenge can lead, as this person is less likely to want a live peer call.")
    lines.append("- OPEN: one sharp, TRUE, specific question in their OWN domain (" + s["domain"] +
                 "), taken from engagement_hooks - never generic, never a 'selected leaders' or survey line, "
                 "and never a cross-domain pitch (do not raise go-to-market with an engineer, or deep tech with "
                 "a commercial lead).")
    if s["guarded"]:
        lines.append("- TRUST: they VET before they act - answer who you are / who is behind it / what it is for "
                     "plainly, and give the host and the about/challenge page EARLY so they can check it; earn the "
                     "conversation before any ask.")
    else:
        lines.append("- TRUST: move to the gamified challenge once the opener lands; keep proof-of-identity handy "
                     "but you need not front-load it.")
    action = ("- ACTION: to get them onto the site, DELIVER A RESOURCE THEY OPEN (send the registered link in the "
              "body, let opening it be the first step) and make the on-page task LOW-FRICTION and VALUE-RETURNING - "
              "something they get back, framed in their domain. Never an opinion survey, never data-extraction.")
    if s["public_voice"]:
        action += " They PUBLISH their own views, so never ask them to submit opinions they already make public - "
        action += "give them a result or tool instead."
    lines.append(action)
    avoid = "- AVOID: fabricated names/references/data and any near-identical repeat (both read as a scam or spam)."
    if s["confidential"]:
        avoid += " They will NOT surface internals, customers, secrets, stack or non-public work - keep every "
        avoid += "question to their reasoning and approach in the abstract."
    lines.append(avoid)
    lines.append("- PERSIST: if an angle stalls, switch to genuinely NEW value on their preferred channel; never "
                 "repeat an ask in new words; stop cleanly rather than fabricate or spam.")
    return "\n".join(lines)


# ---- question tracking -------------------------------------------------------

def question_id(quote: str) -> str:
    return hashlib.sha256(normalized(quote).encode("utf-8")).hexdigest()[:12]


def task_kind(item: "dict[str, Any]") -> "tuple[str, str]":
    """Return (kind, channel). Recover a type from wording when it was not stored."""
    stored = item.get("kind")
    if stored in ("information", "email_delivery", "resource_delivery"):
        return stored, item.get("requested_channel", "any")
    quote = item.get("quote", item.get("question", ""))
    if re.match(r"\s*(please\s+)?(send\b|schick\w*\b|senden\b|e-?mail\b|mail\b|forward\b)", quote, re.I):
        resource = re.search(r"\b(draft|outline|brief|preview|agenda|document|entwurf|unterlagen|details)\b", quote, re.I)
        channel = "email" if re.search(r"\b(e-?mail|mail|courriel)\b", quote, re.I) else "any"
        if resource:
            return "resource_delivery", channel
        if channel == "email":
            return "email_delivery", "email"
    return "information", item.get("requested_channel", "any")


def add_questions(existing: "list[dict[str, Any]]", incoming: "list[dict[str, Any]]", utterance: str) -> "list[dict[str, Any]]":
    items = {q["id"]: q for q in existing}
    for q in incoming:
        quote = str(q.get("quote", "")).strip()
        if not quote or normalized(quote) not in normalized(utterance):
            continue
        identifier = question_id(quote)
        if identifier in items:
            continue
        kind, channel = task_kind(q)
        items[identifier] = {"id": identifier, "question": q.get("question", quote), "quote": quote,
                             "kind": kind, "requested_channel": channel}
    return list(items.values())


def engagement_update(observation: "dict[str, Any]", utterance: str) -> "dict[str, Any] | None":
    status = observation.get("readiness", "unknown")
    quote = str(observation.get("readiness_quote", "")).strip()
    if status == "unknown" or not quote or normalized(quote) not in normalized(utterance):
        return None
    return {"status": status, "quote": quote,
            "blocking_conditions": [c for c in observation.get("blocking_conditions", []) if isinstance(c, str) and c.strip()]}


# ---- delivery and answer coverage -------------------------------------------

def delivery_satisfied(task: "dict[str, Any]", decision: "dict[str, Any]", resource: "dict[str, Any] | None") -> bool:
    kind, channel = task_kind(task)
    if kind == "information":
        return False
    action = decision.get("action")
    channel_ok = action == "message" and decision.get("channel") == "email"
    if channel == "email" and not channel_ok:
        return False
    if kind == "email_delivery":
        return channel_ok
    body = decision.get("body") or decision.get("say") or ""
    if not resource:
        return action in ("message", "say")
    return action in ("message", "say") and normalized(resource.get("draft_text", "")) in normalized(body)


def coverage_failures(pending: "list[dict[str, Any]]", answers: "list[dict[str, Any]]",
                      body: str, decision: "dict[str, Any] | None" = None,
                      resource: "dict[str, Any] | None" = None) -> "list[str]":
    results = {a.get("question_id"): a for a in answers}
    missing: "list[str]" = []
    for q in pending:
        if decision is not None and task_kind(q)[0] != "information":
            if not delivery_satisfied(q, decision, resource):
                missing.append("Delivery task not fulfilled: " + q["question"])
            continue
        check = results.get(q["id"], {})
        quote = str(check.get("answer_quote", "")).strip()
        if not check.get("answered_directly") or not quote or normalized(quote) not in normalized(body):
            missing.append("Direct answer required for: " + q["question"])
    return missing
