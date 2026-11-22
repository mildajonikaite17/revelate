"""A self-contained offline twin and model, so the whole agent runs with no keys.

SimulatedTargetAPI behaves like the revel8 practice API: it hands out a session,
accepts pages, messages and calls, and reacts the way a cautious persona would -
asking who is behind the request, then, once answered, opening the registered
round pages and submitting their fields. SimulatedModel implements the same
interface as OpenAIModel and drives a coherent campaign to a credential-submission
objective. Both are deterministic, which is what makes `verify.py` reproducible.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from knowledge import task_kind, question_id

# Phrases the twin says. The model's observer quotes exact substrings of these.
Q_WHO = "Who is actually behind this, and what exactly do you need from me?"
MARK_ANSWER = "Here are the details you asked for"
ASK_LINK = "Alright, that is clear enough. Send the first round and I will take a look."
INTEREST_QUOTE = "I will take a look"
DONE1 = "Done - those were good reasoning questions, oddly fun."
DONE2 = "Interesting, that second round made me think about how we actually run things."
DONE_CONFIRM = "Okay, I saved my progress with my work email."


def _event(kind: str, **extra: Any) -> "dict[str, Any]":
    event = {"id": "ev_" + uuid.uuid4().hex[:10], "type": kind}
    event.update(extra)
    return event


class SimulatedTargetAPI:
    """A deterministic stand-in for the revel8 Target API."""

    def __init__(self, persona: str = "julius", touch_budget: int = 30):
        self.persona = persona
        self.session = {"session_id": "s_sim_" + uuid.uuid4().hex[:8], "scenario_id": "practice",
                        "status": "active", "touch_budget": touch_budget, "touches_used": 0}
        self.events: "list[dict[str, Any]]" = []
        self.pages: "dict[str, dict[str, Any]]" = {}
        self.calls: "list[dict[str, Any]]" = []
        self.cache: "dict[tuple, dict]" = {}
        self._replied = False

    def request(self, method, path, payload=None, idempotency_key=None):
        self.calls.append({"method": method, "path": path, "payload": copy.deepcopy(payload), "idempotency_key": idempotency_key})
        if method == "GET":
            return self._get(path)
        if idempotency_key is not None:
            cache_key = (path, idempotency_key)
            if cache_key in self.cache:
                return copy.deepcopy(self.cache[cache_key])
        response = self._post(path, payload or {})
        if method == "POST" and idempotency_key is not None:
            self.cache[(path, idempotency_key)] = copy.deepcopy(response)
        return copy.deepcopy(response)

    def _get(self, path):
        if path == "/scenarios":
            return [{"id": "practice", "kind": "practice", "open": True,
                     "objectives": ["disclosure", "action", "credentials"],
                     "targets": [{"id": self.persona, "name": "Simulated " + self.persona.title(), "role": "Founder"}]}]
        if path == "/sessions/" + self.session["session_id"]:
            return copy.deepcopy(self.session)
        if path == "/sessions/" + self.session["session_id"] + "/events":
            return {"events": copy.deepcopy(self.events)}
        raise ValueError("Simulated API unexpected GET: " + path)

    def _post(self, path, payload):
        sid = self.session["session_id"]
        if path == "/sessions":
            return copy.deepcopy(self.session)
        if path == "/sessions/" + sid + "/pages":
            page_id = "p_" + uuid.uuid4().hex[:8]
            self.pages[payload["url"]] = {"page_id": page_id, "fields": payload.get("fields", [])}
            return {"page_id": page_id}
        if path == "/sessions/" + sid + "/messages":
            return self._deliver(payload.get("body", ""), channel=payload.get("channel", "email"))
        if path == "/sessions/" + sid + "/conversations":
            self.session["touches_used"] += 1
            return {"conversation_id": "c_" + uuid.uuid4().hex[:8], "status": "answered",
                    "persona_says": "Hello, " + self.persona.title() + " here.", "touches_used": self.session["touches_used"]}
        if path.endswith("/turns"):
            return {"persona_says": "Right, go on.", "ended": False, "events": [], "turns_used": 1}
        if path.endswith("/end"):
            return {"status": "ended"}
        raise ValueError("Simulated API unexpected POST: " + path)

    def _submit_for(self, marker):
        for url, page in self.pages.items():
            if marker in url:
                return _event("link.opened", url=url, message_id=None, page_id=page["page_id"]), \
                       _event("page.submitted", url=url, page_id=page["page_id"], fields=list(page["fields"]))
        return None

    def _deliver(self, body, channel):
        self.session["touches_used"] += 1
        message_id = "m_" + uuid.uuid4().hex[:8]
        events, reply = [], None
        lowered = body.lower()
        if any("/round-2" in url and url in body for url in self.pages):
            pair = self._submit_for("/round-2")
            if pair:
                events = [pair[0], pair[1]]
            reply = DONE2
        elif any("/save" in url and url in body for url in self.pages):
            pair = self._submit_for("/save")
            if pair:
                events = [pair[0], pair[1]]
            reply = DONE_CONFIRM
        elif any("/round-1" in url and url in body for url in self.pages):
            pair = self._submit_for("/round-1")
            if pair:
                events = [pair[0], pair[1]]
            reply = DONE1
        elif MARK_ANSWER.lower() in lowered:
            reply = ASK_LINK
        else:
            reply = Q_WHO
        for event in events:
            event["message_id"] = message_id
            event.setdefault("channel", channel)
        reply_event = _event("reply", channel=channel, body=reply, message_id=message_id)
        self.events.extend(events + [reply_event])
        return {"message_id": message_id, "events": events + [reply_event], "touches_used": self.session["touches_used"]}


class SimulatedModel:
    """A deterministic controller with the OpenAIModel interface."""

    def __init__(self, challenge_category: "str | None" = None):
        self._calls = 0
        self.category = challenge_category or "founder"

    @property
    def calls(self) -> int:
        return self._calls

    def _tick(self):
        self._calls += 1

    def research(self, target, team_brief=""):
        self._tick()
        source = "https://example-sim.invalid/profile"  # never used for links; marked uncertain by design
        return {"facts": [{"id": "fact_1", "text": target["name"] + " leads a small company.", "source_url": source}],
                "hypotheses": [], "unknowns": ["Offline simulation: no live web search performed."],
                "sources": [{"url": source, "title": "Simulated profile"}],
                "provenance": {"web_search_enabled": False, "verified_source_count": 0, "rejected_fact_count": 0}}

    def profile(self, context):
        self._tick()
        return {"identity_match": "Assumed to match the assigned practice target.",
                "employment_relationship": "founder", "employer_or_practice": "a small company",
                "host_institution": "unknown", "operating_unit": "whole company",
                "organisation_size_band": "2-9", "unit_size_band": "2-9", "sector": "software",
                "ownership": "private", "function": "leadership", "seniority": "Founder",
                "evidenced_authority": "Runs the company.", "professional_focus": "company direction",
                "professional_language": "English", "location": "unknown",
                "evidenced_tools_or_processes": [], "work_relationships": [],
                "tenure_or_recent_changes": "unknown", "unknowns": ["Most specifics are unknown offline."],
                "recommended_category": self.category, "category_rationale": "Offline default / forced niche.",
                "relevant_topics": ["company direction", "team alignment"],
                "engagement_hooks": ["their current top priority this quarter", "a recent public milestone"],
                "suggested_opening": "Open with a specific, true detail about their recent public work."}

    def plan(self, context):
        self._tick()
        objectives = context.get("objectives", ["disclosure"])
        objective = "credentials" if "credentials" in objectives else objectives[0]
        sender = context.get("approved_senders", [{"name": "Mara Stein"}])[0]["name"]
        fact_ids = [f["id"] for f in context.get("research", {}).get("facts", [])]
        channels = context.get("allowed_message_channels") or ["email"]
        branches = [{"trigger": t, "next_step": "handle " + t}
                    for t in ("ignored", "verification_questions", "opened_without_submission", "submitted", "refused")]
        approaches = [{"title": title, "relevance": "Fits the researched role.", "objective": objective,
                       "counterpart_role": "review coordinator", "credibility_risks": ["cold outreach"],
                       "branches": branches}
                      for title in ("Tailored two-round review", "Direct question first", "Resource-only review")]
        return {"approaches": approaches, "chosen_title": "Tailored two-round review",
                "why_chosen": "A role-relevant two-round challenge with an honest sender.",
                "first_channel": channels[0], "sender_name": sender, "primary_objective": objective,
                "fact_ids": fact_ids, "identity_and_authority_limits": "No employer mandate; optional external pilot."}

    def observe(self, context):
        self._tick()
        text = context["inbound"]["text"]
        findings, questions = [], []
        readiness, readiness_quote, blocking = "unknown", "", []
        if "behind this" in text:
            findings.append({"kind": "verification_question", "quote": Q_WHO, "detail": "Asks who runs it and what is wanted."})
            questions.append({"question": "Who is behind this and what do you need?", "quote": Q_WHO,
                              "kind": "information", "requested_channel": "any"})
        if INTEREST_QUOTE in text:
            findings.append({"kind": "registration_interest", "quote": INTEREST_QUOTE, "detail": "Agrees to look at the first round."})
            readiness, readiness_quote = "interested", INTEREST_QUOTE
        return {"findings": findings, "questions": questions, "readiness": readiness,
                "readiness_quote": readiness_quote, "blocking_conditions": blocking}

    def review(self, context, action):
        self._tick()
        pending = [q for q in context["state"]["pending_questions"] if task_kind(q)[0] == "information"]
        answers = []
        if action.get("action") in ("message", "say"):
            body = action.get("body") or action.get("say") or ""
            for q in pending:
                answered = MARK_ANSWER in body
                answers.append({"question_id": q["id"], "answered_directly": answered,
                                "answer_quote": MARK_ANSWER if answered else ""})
        return {"allow": True, "errors": [], "summary": "Consistent with the locked dossier.", "answers": answers}

    def stop_review(self, context, reason):
        self._tick()
        return {"justified": True, "reason": "Rounds completed or no credible next step.", "untried_alternative": ""}

    def decide(self, context, feedback=None):
        self._tick()
        state = context["state"]
        challenge = state["challenge"]
        rounds = challenge["rounds"]
        about_url = rounds["about"]["url"]
        r1_url, r2_url, confirm_url = rounds["round1"]["url"], rounds["round2"]["url"], rounds["confirm"]["url"]
        registered = {p["url"] for p in state["registered_pages"]}
        bodies = [m["payload"].get("body", "") for m in state["messages"]]
        objective = state.get("objective")
        interest = state["engagement"].get("registration_interest")
        pending_info = [q for q in state["pending_questions"] if task_kind(q)[0] == "information"]
        submitted = {e.get("url") for e in state["events"] if e.get("type") == "page.submitted"}

        def opened(url):
            return any(url in b for b in bodies)

        base = {"action": "stop", "channel": None, "sender_name": challenge["contact_name"], "subject": None,
                "body": None, "say": None, "register_round": None, "link_round": None, "attachments": [],
                "reason": "No further step.", "evidence_ids": [], "addresses_requirements": []}

        def msg(subject, body, link=None, reason=""):
            d = dict(base); d.update(action="message", channel="email", subject=subject, body=body,
                                     link_round=link, reason=reason or subject)
            return d

        def page(round_key, reason):
            d = dict(base); d.update(action="register_page", register_round=round_key, reason=reason)
            return d

        if about_url not in registered:
            return page("about", "Publish the honest about page first.")
        if not state["messages"]:
            return msg("A short two-round review", "Hello, I run an independent studio preparing a short draft resource. "
                       "Could I share a quick two-round review tailored to your role? It takes under ten minutes.",
                       reason="Send the introduction.")
        if pending_info:
            return msg("Re: A short two-round review", MARK_ANSWER + ". " + challenge["organizer"] + " runs it; "
                       + challenge["participant_status"] + " " + challenge["commissioning"],
                       reason="Answer the twin's questions directly.")
        if interest and r1_url not in registered:
            return page("round1", "Register round 1 now that there is interest.")
        if interest and r1_url in registered and not opened(r1_url):
            return msg("Round 1 of 2", "Thanks - here is the first round, a few quick reasoning prompts:",
                       link="round1", reason="Link round 1.")
        if r1_url in submitted and r2_url not in registered:
            return page("round2", "Register round 2 after the first round was completed.")
        if r2_url in registered and not opened(r2_url):
            return msg("Round 2 of 2", "Great - here is the short second round:", link="round2", reason="Link round 2.")
        if objective == "credentials" and r2_url in submitted and confirm_url not in registered:
            return page("confirm", "Offer the optional save step.")
        if objective == "credentials" and confirm_url in registered and not opened(confirm_url):
            return msg("Save your results", "If you would like a copy, you can save your results here:",
                       link="confirm", reason="Link the optional save page.")
        stop = dict(base)
        stop["reason"] = "Both rounds are complete and no credible next step remains."
        return stop
