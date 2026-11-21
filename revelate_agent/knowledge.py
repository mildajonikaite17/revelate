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


def categorize(work_profile: "dict[str, Any]") -> str:
    """Pick one tailored niche. Trust the model's recommendation when valid, else derive it."""
    recommended = (work_profile or {}).get("recommended_category")
    if recommended in CATEGORIES:
        return recommended
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
