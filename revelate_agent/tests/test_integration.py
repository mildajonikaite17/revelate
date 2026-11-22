"""Integration tests: full offline campaign plus the edge cases past versions failed.

Standard-library unittest only. Deterministic; no network, no keys.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import AgentRunner, write_transcript, write_challenge_preview
from protocol import APIError
from simulator import SimulatedTargetAPI, SimulatedModel

CONTACT = "Mara Stein"
TARGET = {"id": "julius", "name": "Julius Muth", "role": "Co-Founder"}


def campaign(**over):
    base = {
        "name": "test", "objectives": ["disclosure", "action", "credentials"],
        "allowed_message_channels": ["email", "linkedin_message", "teams_chat", "slack"],
        "allowed_call_channels": ["phone_call", "live_chat"],
        "simulation_domains": ["company-direction-review.com"],
        "enable_challenge_pages": True, "allow_credential_fields": True,
        "max_contacts": 30, "max_actions": 120, "max_model_calls": 200, "persistent": False,
    }
    base.update(over)
    return base


class MemoryStore:
    def __init__(self, initial=None, secrets=()):
        self.committed = copy.deepcopy(initial)
        self.secrets = tuple(secrets)
        self.saves = []

    def exists(self):
        return self.committed is not None

    def load(self):
        return json.loads(json.dumps(self.committed))

    def save(self, state):
        text = json.dumps(state, ensure_ascii=False)
        if any(secret in text for secret in self.secrets):
            raise ValueError("secret leaked into state")
        self.committed = json.loads(text)
        self.saves.append(self.committed)


# ---- scripted fixtures for edge cases ---------------------------------------
RESEARCH = {"facts": [{"id": "fact_1", "text": "Julius co-founded the company.", "source_url": "https://revel8.ai/about"}],
            "hypotheses": [], "unknowns": [], "sources": [{"url": "https://revel8.ai/about", "title": "About"}],
            "provenance": {"web_search_enabled": True, "verified_source_count": 1, "rejected_fact_count": 0}}


def work_profile(category="founder"):
    return {"identity_match": "match", "employment_relationship": "founder", "employer_or_practice": "Acme",
            "host_institution": "unknown", "operating_unit": "company", "organisation_size_band": "2-9",
            "unit_size_band": "2-9", "sector": "software", "ownership": "private", "function": "leadership",
            "seniority": "Founder", "evidenced_authority": "runs it", "professional_focus": "direction",
            "professional_language": "English", "location": "unknown", "evidenced_tools_or_processes": [],
            "work_relationships": [], "tenure_or_recent_changes": "unknown", "unknowns": [],
            "recommended_category": category, "category_rationale": "fixture",
            "relevant_topics": ["company direction"], "engagement_hooks": ["a recent milestone"],
            "suggested_opening": "Open with a specific true detail."}


def plan(objective="disclosure"):
    branches = [{"trigger": t, "next_step": "x"} for t in ("ignored", "verification_questions",
                "opened_without_submission", "submitted", "refused")]
    approaches = [{"title": t, "relevance": "r", "objective": objective, "counterpart_role": "coordinator",
                   "credibility_risks": ["cold"], "branches": branches} for t in ("A", "B", "C")]
    return {"approaches": approaches, "chosen_title": "A", "why_chosen": "fits", "first_channel": "email",
            "sender_name": CONTACT, "primary_objective": objective, "fact_ids": ["fact_1"],
            "identity_and_authority_limits": "optional external pilot"}


def decision(kind, **over):
    value = {"action": kind, "channel": None, "sender_name": CONTACT, "subject": None, "body": None, "say": None,
             "register_round": None, "link_round": None, "attachments": [], "reason": "r",
             "evidence_ids": [], "addresses_requirements": []}
    if kind == "message":
        value.update(channel="email", subject="Hello", body="A short, distinct, plain message body that is clearly unique each time.")
    if kind == "start_call":
        value["channel"] = "live_chat"
    if kind == "say":
        value["say"] = "A short spoken line here."
    value.update(over)
    return value


class ScriptedModel:
    def __init__(self, decisions=(), observations=(), reviews=(), stops=(), objective="disclosure"):
        self._calls = 0
        self.decisions = list(decisions)
        self.observations = list(observations)
        self.reviews = list(reviews)
        self.stops = list(stops)
        self.objective = objective
        self.feedback = []

    @property
    def calls(self):
        return self._calls

    def _t(self):
        self._calls += 1

    def research(self, target, team_brief=""):
        self._t(); return copy.deepcopy(RESEARCH)

    def profile(self, context):
        self._t(); return work_profile()

    def plan(self, context):
        self._t(); return plan(self.objective)

    def decide(self, context, feedback=None):
        self._t(); self.feedback.append(list(feedback or []))
        item = self.decisions.pop(0)
        return item(context) if callable(item) else copy.deepcopy(item)

    def observe(self, context):
        self._t()
        item = self.observations.pop(0) if self.observations else {"findings": [], "questions": [], "readiness": "unknown", "readiness_quote": "", "blocking_conditions": []}
        return item(context) if callable(item) else copy.deepcopy(item)

    def review(self, context, action):
        self._t()
        item = self.reviews.pop(0) if self.reviews else {"allow": True, "errors": [], "summary": "ok", "answers": []}
        return item(context, action) if callable(item) else copy.deepcopy(item)

    def stop_review(self, context, reason):
        self._t()
        item = self.stops.pop(0) if self.stops else {"justified": True, "reason": "ok", "untried_alternative": ""}
        return item(context, reason) if callable(item) else copy.deepcopy(item)


class FakeAPI:
    def __init__(self, greeting="Hello, Julius here.", turn_responses=(), message_responses=()):
        self.session = {"session_id": "s_fixture", "scenario_id": "practice", "status": "active", "touch_budget": 30, "touches_used": 0}
        self.greeting = greeting
        self.turn_responses = list(turn_responses)
        self.message_responses = list(message_responses)
        self.events = []
        self.calls = []
        self.cache = {}
        self.uncertain_message_once = False

    def request(self, method, path, payload=None, idempotency_key=None):
        self.calls.append({"method": method, "path": path, "payload": copy.deepcopy(payload), "idempotency_key": idempotency_key})
        if method == "GET":
            if path == "/sessions/s_fixture":
                return copy.deepcopy(self.session)
            if path == "/sessions/s_fixture/events":
                return {"events": copy.deepcopy(self.events)}
            raise AssertionError("GET " + path)
        if path == "/sessions":
            return copy.deepcopy(self.session)
        cache_key = (path, idempotency_key)
        if idempotency_key and cache_key in self.cache:
            return copy.deepcopy(self.cache[cache_key])
        if path == "/sessions/s_fixture/pages":
            response = {"page_id": "p_" + str(len(self.calls))}
        elif path == "/sessions/s_fixture/conversations":
            self.session["touches_used"] += 1
            response = {"conversation_id": "c_fixture", "status": "answered", "persona_says": self.greeting, "touches_used": self.session["touches_used"]}
        elif path == "/conversations/c_fixture/turns":
            response = copy.deepcopy(self.turn_responses.pop(0)) if self.turn_responses else {"persona_says": "ok", "ended": False, "events": [], "turns_used": 1}
        elif path == "/conversations/c_fixture/end":
            response = {"status": "ended"}
        elif path == "/sessions/s_fixture/messages":
            self.session["touches_used"] += 1
            if self.message_responses:
                response = copy.deepcopy(self.message_responses.pop(0))
            else:
                response = {"message_id": "m_" + str(len(self.calls)), "events": []}
                if payload.get("attachments"):
                    response["events"] = [{"id": "att_" + str(len(self.calls)), "type": "attachment.opened", "message_id": response["message_id"]}]
            response["touches_used"] = self.session["touches_used"]
        else:
            raise AssertionError("POST " + path)
        self.events.extend(copy.deepcopy(response.get("events", [])))
        if idempotency_key:
            self.cache[cache_key] = copy.deepcopy(response)
        if path.endswith("/messages") and self.uncertain_message_once:
            self.uncertain_message_once = False
            raise APIError("Message timed out", uncertain=True)
        return copy.deepcopy(response)

    def posts(self, suffix=None):
        return [c for c in self.calls if c["method"] == "POST" and (suffix is None or c["path"].endswith(suffix))]


def runner(api, model, camp=None, store=None):
    return AgentRunner(api, model, camp or campaign(), store or MemoryStore(), log=lambda *_: None)


class HappyPathTests(unittest.TestCase):
    def test_full_offline_campaign_reaches_credential_objective(self):
        api = SimulatedTargetAPI(persona="julius")
        model = SimulatedModel(challenge_category="founder")
        r = runner(api, model, campaign(persistent=True, max_contacts=30))
        result = r.run(target=TARGET)
        self.assertEqual(result["status"], "objective_evidence")
        self.assertTrue(result["metrics"]["credential_fields_submitted"])
        self.assertEqual(result["metrics"]["forms_submitted"], 3)
        # Identity stayed locked to the challenge contact throughout.
        self.assertEqual(r.campaign["sender"]["name"], CONTACT)
        self.assertIsNone(result["active_conversation"])
        self.assertEqual(result["category"], "founder")
        # Every registered page lived on the simulation domain.
        for page in result["registered_pages"]:
            self.assertTrue(page["url"].startswith("https://company-direction-review.com/"))

    def test_transcript_and_preview_write(self):
        api = SimulatedTargetAPI(persona="tom")
        model = SimulatedModel(challenge_category="technical")
        r = runner(api, model)
        result = r.run(target={"id": "tom", "name": "Tom", "role": "CTO"})
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tpath = Path(d) / "t.md"
            cpath = Path(d) / "t.challenge.html"
            write_transcript(result, tpath)
            write_challenge_preview(result, cpath)
            self.assertIn("Autonomous practice run", tpath.read_text(encoding="utf-8"))
            self.assertIn("challenge", cpath.read_text(encoding="utf-8").lower())


class EdgeCaseTests(unittest.TestCase):
    def test_call_greeting_requests_email_forces_cleanup_then_email(self):
        ask = "Please just send it to me by email."
        reply = {"id": "e_reply", "type": "reply", "channel": "email", "body": "thanks"}
        api = FakeAPI(greeting=ask, message_responses=[{"message_id": "m1", "events": [reply]}])
        observations = [{"findings": [{"kind": "email_requested", "quote": ask, "detail": "wants email"}],
                         "questions": [], "readiness": "unknown", "readiness_quote": "", "blocking_conditions": []}]
        model = ScriptedModel(decisions=[decision("start_call"), decision("message"), decision("stop")],
                              observations=observations)
        result = runner(api, model).run(target=TARGET)
        self.assertEqual(result["status"], "stopped_planner")
        self.assertEqual([op["kind"] for op in result["operations"]], ["start_call", "end_call", "message"])
        self.assertEqual(len(api.posts("/turns")), 0)
        self.assertFalse(result["constraints"]["email_requested"])
        self.assertIsNone(result["active_conversation"])

    def test_stop_review_reconsiders_once_then_stops(self):
        model = ScriptedModel(decisions=[decision("stop"), decision("message"), decision("stop")],
                              stops=[{"justified": False, "reason": "no", "untried_alternative": "try a smaller ask"},
                                     {"justified": True, "reason": "done", "untried_alternative": ""}])
        api = FakeAPI()
        result = runner(api, model).run(target=TARGET)
        self.assertEqual(result["status"], "stopped_planner")
        self.assertEqual(len(api.posts("/messages")), 1)  # the message between the two stops was sent
        self.assertEqual(len(model.stops), 0)

    def test_objective_action_detected_on_attachment_open(self):
        want = lambda ctx: decision("message", attachments=[ctx["state"]["challenge"]["resource_filename"]])
        model = ScriptedModel(decisions=[want], objective="action")
        result = runner(api := FakeAPI(), model).run(target=TARGET)
        self.assertEqual(result["status"], "objective_evidence")
        self.assertEqual(result["objective"], "action")
        self.assertEqual(result["objective_evidence"]["objective"], "action")

    def test_uncertain_message_resume_replays_without_duplicate_touch(self):
        store = MemoryStore()
        api = FakeAPI(message_responses=[{"message_id": "m1", "events": [{"id": "r1", "type": "reply", "channel": "email", "body": "ok"}]}])
        api.uncertain_message_once = True
        first = runner(api, ScriptedModel(decisions=[decision("message")]), store=store).run(target=TARGET)
        self.assertEqual(first["status"], "paused_uncertain")
        self.assertEqual(first["pending"]["kind"], "message")
        second = runner(api, ScriptedModel(decisions=[decision("stop")]), store=store).run(resume=True)
        self.assertEqual(second["status"], "stopped_planner")
        sends = api.posts("/messages")
        self.assertEqual(len(sends), 2)  # original attempt + idempotent replay
        self.assertEqual(sends[0]["idempotency_key"], sends[1]["idempotency_key"])
        self.assertEqual(second["session"]["touches_used"], 1)
        self.assertEqual(len(second["messages"]), 1)

    def test_secret_never_written_to_store(self):
        store = MemoryStore(secrets=("rv8_secret", "sk-secret"))
        api = SimulatedTargetAPI()
        model = SimulatedModel(challenge_category="intern")
        # Must complete a full run without the store ever raising on a secret.
        result = runner(api, model, store=store).run(target=TARGET)
        self.assertIn(result["status"], ("objective_evidence", "stopped_planner", "stopped_budget"))


if __name__ == "__main__":
    unittest.main()
