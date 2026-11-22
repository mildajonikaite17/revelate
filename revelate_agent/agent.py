"""Autonomous, bounded, persistent practice runner for the authorized revel8 AI-twin API.

Pipeline: research -> work profile -> niche -> locked gamified challenge -> plan ->
an autonomous loop of message / page / call / say / end_call / stop, each checked by
code and a separate model review before anything is sent. The code owns every page
and URL, keeps one consistent sender, answers the twin's questions from a locked
honest dossier, and never claims a win the simulator did not record.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import uuid

from models import ModelError
from policy import validate_action, compute_metrics, _is_sensitive_field
from protocol import TargetAPI, APIError, RunStore, now
from knowledge import (normalized, categorize, add_questions, engagement_update,
                       task_kind, coverage_failures)
from challenge import build_challenge, challenge_page, dossier_faq, render_preview_html


class AgentError(Exception):
    pass


def merge_events(existing, incoming):
    """Refreshing server events must not double-count a previously observed action."""
    result, seen = [], set()
    for event in list(existing or []) + list(incoming or []):
        key = event.get("id") or json.dumps(event, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(copy.deepcopy(event))
    return result


class AgentRunner:
    def __init__(self, api, model, campaign, store, log=print):
        self.api = api
        self.model = model
        self.campaign = copy.deepcopy(campaign)
        self.store = store
        self.log = log
        self.state = None
        self.base_model_calls = 0

    # ---- persistence helpers -------------------------------------------------
    def save(self):
        self.state["updated_at"] = now()
        self.state["model_calls"] = self.base_model_calls + self.model.calls
        self.store.save(self.state)

    def context(self):
        return {"campaign": self.campaign, "state": copy.deepcopy(self.state)}

    def _budget(self, key, default):
        return int(self.campaign.get(key, default))

    def model_call(self, method, *args, **kwargs):
        if self.base_model_calls + self.model.calls >= self._budget("max_model_calls", 200):
            raise ModelError("Configured model-call budget reached for this attempt.")
        return getattr(self.model, method)(*args, **kwargs)

    def fresh(self, target, category_override=None):
        self.state = {
            "version": 10, "status": "initializing", "created_at": now(),
            "scenario_id": "practice", "target": copy.deepcopy(target),
            "category": None, "category_override": category_override,
            "session": None, "profile": None, "work_profile": None,
            "challenge": None, "plan": None, "objective": None,
            "campaign": copy.deepcopy(self.campaign), "model_calls": 0,
            "operations_used": 0, "pending": None,
            "messages": [], "conversations": [], "active_conversation": None,
            "registered_pages": [], "events": [], "inbound": [],
            "evidence": [], "requirements": [], "pending_questions": [], "candidate_disclosures": [],
            "constraints": {"preferred_channel": None, "no_registration": False,
                            "plain_text_only": False, "no_links": False,
                            "stop_contact": False, "email_requested": False},
            "engagement": {"readiness": "unknown", "blocking_conditions": [], "registration_interest": False},
            "persistent": bool(self.campaign.get("persistent", False)),
            "contact_cap": self._budget("max_contacts", 8),
            "operations": [], "rejected_drafts": [], "stop_reviews": [], "last_errors": [],
            "objective_evidence": None,
        }
        self.save()

    def restore(self):
        self.state = self.store.load()
        if self.state.get("version") != 10 or self.state.get("scenario_id") != "practice":
            raise AgentError("This runner resumes only its own version-10 practice runs. Start a fresh run instead.")
        self.campaign = copy.deepcopy(self.state["campaign"])
        self.base_model_calls = int(self.state.get("model_calls", 0))
        active = self.state.get("active_conversation")
        if active:
            matches = [c for c in self.state["conversations"] if c["id"] == active["id"]]
            if len(matches) != 1:
                raise AgentError("Saved conversation history is inconsistent; no request was sent.")
            self.state["active_conversation"] = matches[0]
        self.state["status"] = "resuming"

    # ---- setup phases --------------------------------------------------------
    def initialize(self):
        if not self.state.get("profile"):
            self.log("Researching public professional context...")
            self.state["profile"] = self.model_call("research", self.state["target"], self.campaign.get("team_brief", ""))
            for fact in self.state["profile"].get("facts", []):
                self.state["evidence"].append({"id": fact["id"], "kind": "public_fact",
                                               "text": fact["text"], "source_url": fact["source_url"]})
            self.save()
        if not self.state.get("work_profile"):
            self.log("Building the employment, size, sector, function and authority profile...")
            self.state["work_profile"] = self.model_call("profile", {
                "target": self.state["target"], "research": self.state["profile"],
                "allowed_source_urls": [f["source_url"] for f in self.state["profile"].get("facts", [])]})
            self.save()
        if not self.state.get("category"):
            category = self.state.get("category_override") or categorize(self.state["work_profile"])
            self.state["category"] = category
            self.log("Selected niche: " + category + " (" + self.state["work_profile"].get("seniority", "?") + ")")
            self.save()
        if not self.state.get("challenge"):
            self.log("Building the locked, persona-tailored two-round challenge...")
            domain = (self.campaign.get("simulation_domains") or ["company-direction-review.com"])[0]
            challenge = build_challenge(self.state["category"], self.state["work_profile"],
                                        self.state["target"], domain, self.campaign.get("scenario_settings"))
            self.state["challenge"] = challenge
            # Lock the sender identity to the challenge contact for the whole run.
            self.campaign["sender"] = {"name": challenge["contact_name"], "address": challenge["contact_address"]}
            self.campaign["approved_senders"] = [dict(self.campaign["sender"])]
            self.state["campaign"] = copy.deepcopy(self.campaign)
            self.save()
        if not self.state.get("plan"):
            self.log("Comparing three approaches against the evidence...")
            plan = self.model_call("plan", {
                "target": self.state["target"], "work_profile": self.state["work_profile"],
                "research": self.state["profile"], "category": self.state["category"],
                "challenge": {"title": self.state["challenge"]["project_name"],
                              "framing": self.state["challenge"]["framing"],
                              "rounds": {k: {"purpose": v.get("purpose"), "intro": v.get("intro")}
                                         for k, v in self.state["challenge"]["rounds"].items()},
                              "faq": dossier_faq(self.state["challenge"])},
                "objectives": self.campaign.get("objectives", ["disclosure"]),
                "approved_senders": self.campaign.get("approved_senders", []),
                "allowed_message_channels": self.campaign.get("allowed_message_channels"),
                "allowed_call_channels": self.campaign.get("allowed_call_channels")})
            self._validate_plan(plan)
            objective = plan.get("primary_objective")
            if objective not in self.campaign.get("objectives", ["disclosure"]):
                raise AgentError("The plan proposed an objective outside the campaign scope.")
            self.state["plan"] = plan
            self.state["objective"] = objective
            self.save()
            self.log("Chosen approach: " + plan["chosen_title"] + " | objective: " + objective)
            self.log("Why: " + plan["why_chosen"])
        if not self.state.get("session"):
            if self.state.get("pending"):
                self.execute_pending()
                return
            self.state["pending"] = {"kind": "create_session", "path": "/sessions",
                                     "payload": {"scenario_id": "practice"}, "request_id": None, "created_at": now()}
            self.save()
            self.execute_pending(first_attempt=True)

    def _validate_plan(self, plan):
        titles = [a["title"] for a in plan.get("approaches", [])]
        if len(titles) != 3 or len(set(titles)) != 3 or plan.get("chosen_title") not in titles:
            raise AgentError("The plan needs three distinct approaches and an exact chosen title.")
        triggers = {"ignored", "verification_questions", "opened_without_submission", "submitted", "refused"}
        for approach in plan["approaches"]:
            if {b["trigger"] for b in approach.get("branches", [])} != triggers:
                raise AgentError("Each approach must cover all five outcome branches.")
        fact_ids = {f["id"] for f in self.state["profile"].get("facts", [])}
        if not set(plan.get("fact_ids", [])).issubset(fact_ids):
            raise AgentError("The plan cited research evidence that does not exist.")
        if plan.get("sender_name") not in {s["name"] for s in self.campaign.get("approved_senders", [])}:
            raise AgentError("The plan did not select an approved sender identity.")

    # ---- server sync ---------------------------------------------------------
    def refresh(self):
        if not self.state.get("session"):
            return
        sid = self.state["session"]["session_id"]
        session = self.api.request("GET", "/sessions/" + sid)
        if session.get("scenario_id") != "practice":
            raise AgentError("The server session is not a practice session.")
        self.state["session"] = session
        response = self.api.request("GET", "/sessions/" + sid + "/events")
        self.state["events"] = merge_events(self.state["events"], response.get("events", []))
        self.add_event_replies(response.get("events", []))
        self.save()

    def await_events(self, baseline):
        """After a message, give an asynchronous twin time to reply, open a link or
        submit before the next decision. The live POST returns no reply immediately;
        the twin's response lands later on GET /events. The offline transport is
        synchronous (no .sleep), so this returns at once and never affects tests."""
        if len(self.state["events"]) > baseline:
            return
        sleep = getattr(self.api, "sleep", None)
        delay = float(self.campaign.get("reply_poll_seconds", 5))
        attempts = int(self.campaign.get("reply_poll_attempts", 6))
        if not callable(sleep) or delay <= 0 or attempts <= 0:
            return
        for _ in range(attempts):
            sleep(delay)
            self.refresh()
            if len(self.state["events"]) > baseline:
                return

    def inbound(self, kind, text, source_event=None):
        if not text:
            return
        if source_event and any(x.get("source_event") == source_event for x in self.state["inbound"]):
            return
        identifier = "inbound_" + str(len(self.state["inbound"]) + 1)
        self.state["inbound"].append({"id": identifier, "kind": kind, "text": str(text),
                                      "source_event": source_event, "processed": False})
        self.state["evidence"].append({"id": identifier, "kind": kind, "text": str(text)})
        self.log("AI twin [" + kind + "]: " + str(text))

    def add_event_replies(self, events):
        for event in events or []:
            if event.get("type") == "reply":
                key = event.get("id") or json.dumps(event, sort_keys=True)
                self.inbound("message_reply", event.get("body", ""), key)

    # ---- observation ---------------------------------------------------------
    def observe_pending(self):
        for incoming in self.state["inbound"]:
            if incoming["processed"]:
                continue
            result = self.model_call("observe", {"inbound": incoming, "state": self.context()})
            findings = result.get("findings", [])
            for finding in findings:
                quote = finding.get("quote", "")
                if not quote or normalized(quote) not in normalized(incoming["text"]):
                    raise AgentError("The observer could not ground a finding in the actual target reply.")
            for finding in findings:
                self.apply_finding(incoming, finding)
            # Grounded questions and readiness.
            self.state["pending_questions"] = add_questions(
                self.state["pending_questions"], result.get("questions", []), incoming["text"])
            engagement = engagement_update(result, incoming["text"])
            if engagement:
                self.state["engagement"].update(engagement)
                self.log("Readiness: " + engagement["status"] + (" | conditions: " + ", ".join(engagement["blocking_conditions"]) if engagement["blocking_conditions"] else ""))
            incoming["processed"] = True
            self.save()

    def apply_finding(self, incoming, finding):
        kind, quote = finding["kind"], finding["quote"]
        constraints = self.state["constraints"]
        if kind in ("email_requested", "prefer_email"):
            constraints["preferred_channel"] = "email"
            if kind == "email_requested":
                constraints["email_requested"] = True
        elif kind in ("no_registration", "plain_text_only", "no_links", "stop_contact"):
            constraints[kind] = True
        elif kind == "registration_interest":
            self.state["engagement"]["registration_interest"] = True
        elif kind == "candidate_disclosure":
            self.state["candidate_disclosures"].append({"source_id": incoming["id"], "quote": quote,
                                                        "interpretation": finding["detail"], "verified_nonpublic": False})
        if kind in ("verification_question", "email_requested", "plain_text_only", "no_links", "no_registration"):
            self.state["requirements"].append({"id": "requirement_" + str(len(self.state["requirements"]) + 1),
                                               "kind": kind, "quote": quote, "detail": finding["detail"],
                                               "source_id": incoming["id"], "status": "open"})

    # ---- decision enrichment (code owns pages and links) ---------------------
    def enrich(self, decision):
        decision = dict(decision)
        decision.setdefault("attachments", [])
        challenge = self.state["challenge"]
        rounds = challenge["rounds"]
        if decision["action"] in ("message", "start_call", "say"):
            decision["sender_name"] = self.campaign["sender"]["name"]
        decision["page"] = None
        if decision["action"] == "register_page":
            rk = decision.get("register_round")
            if rk in rounds:
                decision["page"] = challenge_page(challenge, rk)
            else:
                decision["_enrich_error"] = "register_page needs register_round in about/round1/round2/confirm."
        link = decision.get("link_round")
        if link in rounds and decision["action"] in ("message", "say"):
            url = rounds[link]["url"]
            field = "body" if decision["action"] == "message" else "say"
            text = decision.get(field) or ""
            if url not in text:
                decision[field] = (text.rstrip() + "\n\n" + url).strip()
        return decision

    # ---- operations ----------------------------------------------------------
    def prepare_operation(self, action):
        kind = action["action"]
        sid = self.state["session"]["session_id"]
        sender_name = self.campaign["sender"]["name"]
        sender_address = self.campaign["sender"].get("address")
        if kind == "message":
            path = "/sessions/" + sid + "/messages"
            payload = {"to": self.state["target"]["id"], "channel": action["channel"],
                       "from": {"name": sender_name, "address": sender_address},
                       "subject": action.get("subject") or "", "body": action["body"]}
            if action.get("attachments"):
                payload["attachments"] = [{"filename": name} for name in action["attachments"]]
        elif kind == "start_call":
            path = "/sessions/" + sid + "/conversations"
            payload = {"to": self.state["target"]["id"], "channel": action["channel"], "from": {"name": sender_name}}
        elif kind == "say":
            path = "/conversations/" + self.state["active_conversation"]["id"] + "/turns"
            payload = {"say": action["say"]}
        elif kind == "end_call":
            path = "/conversations/" + self.state["active_conversation"]["id"] + "/end"
            payload = {}
        elif kind == "register_page":
            path = "/sessions/" + sid + "/pages"
            payload = copy.deepcopy(action["page"])
        else:
            raise AgentError("Unsupported outbound operation.")
        self.state["pending"] = {"kind": kind, "path": path, "payload": payload,
                                 "request_id": str(uuid.uuid4()) if kind in ("message", "start_call", "say") else None,
                                 "session_id": sid, "action": copy.deepcopy(action), "created_at": now()}
        self.state["operations_used"] += 1
        self.save()

    def execute_pending(self, first_attempt=False):
        pending = self.state["pending"]
        if not pending:
            return
        kind = pending["kind"]
        if kind == "create_session" and not first_attempt:
            raise AgentError("Session creation had an uncertain outcome. Resume with --session-id after checking the team's session list; it was not repeated.")
        if kind != "create_session" and pending.get("session_id") != self.state["session"]["session_id"]:
            raise AgentError("The pending operation belongs to another session.")
        try:
            response = self.api.request("POST", pending["path"], pending["payload"], pending.get("request_id"))
        except APIError as exc:
            if kind == "end_call" and exc.status == 409:
                raise AgentError("The server rejected conversation cleanup (409); its final status is unconfirmed; pending state was retained.") from None
            if not exc.uncertain and exc.status in (400, 403, 404, 409, 413, 415, 422):
                self.state["operations"].append({"kind": kind, "failed": True, "status": exc.status,
                                                 "error": str(exc), "action": pending.get("action")})
                self.state["pending"] = None
                self.state["last_errors"] = ["Previous request rejected: " + str(exc)]
                self.save()
                if exc.status in (400, 422) and kind != "create_session":
                    return
            raise
        if kind == "create_session":
            if response.get("scenario_id") != "practice" or not response.get("session_id"):
                raise AgentError("Session creation returned an unexpected response; no contact followed.")
            self.state["session"] = response
        else:
            self.commit_response(pending, response)
        self.state["pending"] = None
        self.state["last_errors"] = []
        self.save()

    def commit_response(self, pending, response):
        kind, action = pending["kind"], pending["action"]
        self.state["operations"].append({"kind": kind, "payload": pending["payload"], "response": response,
                                         "request_id": pending.get("request_id"), "recorded_at": now()})
        if "touches_used" in response:
            self.state["session"]["touches_used"] = max(int(self.state["session"].get("touches_used", 0)), int(response["touches_used"]))
        events = response.get("events", [])
        self.state["events"] = merge_events(self.state["events"], events)
        self.add_event_replies(events)
        if kind == "message":
            self.state["messages"].append({"payload": pending["payload"], "response": response})
            if pending["payload"]["channel"] == "email":
                self.state["constraints"]["email_requested"] = False
            self._clear_answered_questions(action, pending["payload"].get("body", ""))
        elif kind == "start_call":
            cid = response.get("conversation_id")
            if not cid:
                raise AgentError("The call response omitted its conversation ID; pending state was retained.")
            conversation = {"id": cid, "channel": pending["payload"]["channel"],
                            "status": response.get("status", "answered"), "turns_used": 0,
                            "start_response": response, "dialogue": []}
            self.state["conversations"].append(conversation)
            self.state["active_conversation"] = conversation if conversation["status"] == "answered" else None
            self.inbound("call_greeting", response.get("persona_says", ""))
        elif kind == "say":
            conversation = self.state["active_conversation"]
            conversation["dialogue"].append({"say": pending["payload"]["say"], "response": response})
            conversation["turns_used"] = max(conversation["turns_used"] + 1, int(response.get("turns_used", 0)))
            self.inbound("conversation_response", response.get("persona_says", ""))
            self._clear_answered_questions(action, pending["payload"].get("say", ""))
            if response.get("ended"):
                conversation["status"] = "ended"
                self.state["active_conversation"] = None
        elif kind == "end_call":
            self.state["active_conversation"]["status"] = "ended"
            self.state["active_conversation"] = None
        elif kind == "register_page":
            page = dict(pending["payload"], page_id=response.get("page_id"))
            self.state["registered_pages"] = [p for p in self.state["registered_pages"] if p["url"] != page["url"]] + [page]
        addressed = set(action.get("addresses_requirements", [])) if kind in ("message", "say") else set()
        for requirement in self.state["requirements"]:
            if requirement["id"] in addressed:
                requirement["status"] = "responded"

    def _clear_answered_questions(self, action, body):
        """Information questions covered by the approved outgoing text are cleared."""
        answered = set(action.get("_answered_question_ids", []))
        if not answered:
            return
        self.state["pending_questions"] = [q for q in self.state["pending_questions"] if q["id"] not in answered]

    # ---- objective detection -------------------------------------------------
    def _check_objective(self):
        metrics = compute_metrics(self.state)
        objective = self.state.get("objective")
        if objective == "credentials" and metrics["credential_fields_submitted"]:
            return {"objective": "credentials", "evidence": "Credential/sign-in fields were submitted to a registered page."}
        if objective == "action":
            sent = {op["response"].get("message_id") for op in self.state["operations"]
                    if op.get("kind") == "message" and op["payload"].get("attachments") and isinstance(op.get("response"), dict)}
            sent.discard(None)
            for event in self.state["events"]:
                if event.get("type") == "attachment.opened" and event.get("message_id") in sent:
                    return {"objective": "action", "evidence": "A sent simulated attachment was opened."}
        return None

    # ---- lifecycle -----------------------------------------------------------
    def cleanup_action(self, reason):
        return {"action": "end_call", "channel": None, "sender_name": self.campaign["sender"]["name"],
                "subject": None, "body": None, "say": None, "page": None, "attachments": [],
                "reason": reason, "evidence_ids": [], "addresses_requirements": []}

    def finish(self, status, reason):
        if self.state.get("active_conversation") and not self.state.get("pending"):
            try:
                self.prepare_operation(self.cleanup_action("Close the conversation before this attempt stops."))
                self.execute_pending()
            except (APIError, AgentError) as exc:
                status = "paused_uncertain" if self.state.get("pending") else "stopped_error"
                reason += " Conversation cleanup: " + str(exc)
        self.state["status"] = status
        self.state["stop_reason"] = reason
        self.state["metrics"] = compute_metrics(self.state)
        self.save()
        self.log("Observed outcomes (not a score): " + json.dumps(self.state["metrics"], ensure_ascii=False))
        if self.state.get("objective_evidence"):
            self.log("Objective evidence: " + json.dumps(self.state["objective_evidence"], ensure_ascii=False))
        self.log("Candidate internal details recorded: " + str(len(self.state["candidate_disclosures"])) + " (not a verified score)")
        self.log("Stop reason: " + reason)
        return self.state

    def run(self, target=None, resume=False, recovered_session_id=None, category_override=None):
        try:
            if resume:
                self.restore()
                if recovered_session_id:
                    pending = self.state.get("pending")
                    if not pending or pending["kind"] != "create_session":
                        raise AgentError("--session-id is only for recovering an uncertain session creation.")
                    if not re.fullmatch(r"[A-Za-z0-9_-]+", recovered_session_id):
                        raise AgentError("Invalid recovery session ID.")
                    session = self.api.request("GET", "/sessions/" + recovered_session_id)
                    if session.get("scenario_id") != "practice":
                        raise AgentError("Recovery requires a practice session.")
                    self.state["session"] = session
                    self.state["pending"] = None
                    self.save()
            else:
                self.fresh(target, category_override)
            self.initialize()
            self.refresh()
            if self.state.get("pending"):
                self.execute_pending()
            self.state["status"] = "running"
            self.save()
            persistent = bool(self.state.get("persistent"))
            unjustified_stops = 0
            while self.state["operations_used"] < self._budget("max_actions", 120):
                if self.base_model_calls + self.model.calls >= self._budget("max_model_calls", 200):
                    return self.finish("stopped_budget", "Configured model-call budget reached for this attempt.")
                self.observe_pending()
                evidence = self._check_objective()
                if evidence:
                    self.state["objective_evidence"] = evidence
                    self.save()
                    return self.finish("objective_evidence", "Observed objective evidence: " + evidence["evidence"])
                active = self.state["active_conversation"]
                constraints = self.state["constraints"]
                forced = None
                if active and (constraints["email_requested"] or constraints["stop_contact"] or active["turns_used"] >= 10):
                    forced = self.cleanup_action("End the active conversation before honoring the channel preference or stopping.")
                elif constraints["stop_contact"]:
                    return self.finish("stopped_refusal", "The target explicitly declined further contact in this attempt.")
                if not active:
                    budget = min(int(self.state["session"]["touch_budget"]), int(self.state.get("contact_cap", 8)))
                    if int(self.state["session"]["touches_used"]) >= budget:
                        return self.finish("stopped_budget", "Configured contact budget reached for this session.")
                feedback = list(self.state.get("last_errors", []))
                chosen, review_answers = None, []
                for _ in range(4):
                    if forced:
                        action = forced
                    else:
                        raw = self.model_call("decide", self.context(), feedback=feedback)
                        action = self.enrich(raw)
                    if action.get("_enrich_error"):
                        feedback = [action["_enrich_error"]]
                        self.state["rejected_drafts"].append({"action": action, "errors": feedback, "sent": False})
                        self.save()
                        continue
                    errors = validate_action(action, self.state, self.campaign)
                    if not errors and action["action"] not in ("stop", "end_call") and not forced:
                        review = self.model_call("review", self.context(), action)
                        review_answers = review.get("answers", [])
                        if action["action"] in ("message", "say"):
                            body = action.get("body") or action.get("say") or ""
                            info_pending = [q for q in self.state["pending_questions"] if task_kind(q)[0] == "information"]
                            missing = coverage_failures(info_pending, review_answers, body, action, self.state.get("resource"))
                            if missing:
                                errors = list(dict.fromkeys((review.get("errors") or []) + missing))
                        if not errors and not review.get("allow"):
                            errors = review.get("errors") or [review.get("summary", "Draft did not pass the claims review.")]
                    if errors:
                        self.state["rejected_drafts"].append({"action": action, "errors": errors, "sent": False})
                        feedback = list(errors)
                        self.save()
                        self.log("Draft revised before sending: " + "; ".join(errors))
                        if action["action"] == "stop":
                            chosen = None
                            break
                        if forced:
                            break
                        continue
                    chosen = action
                    break
                if chosen is None and not forced:
                    if self.state["rejected_drafts"] and self.state["rejected_drafts"][-1]["action"].get("action") == "stop":
                        pass
                    return self.finish("stopped_validation", "Could not produce a valid next action within the revision budget.")
                if chosen is None:
                    return self.finish("stopped_validation", "A forced cleanup could not be prepared.")
                if chosen["action"] == "stop":
                    audit = self.model_call("stop_review", self.context(), chosen["reason"])
                    self.state["stop_reviews"].append(audit)
                    self.save()
                    if not audit.get("justified") and (persistent or unjustified_stops < 1):
                        unjustified_stops += 1
                        self.log("Stop reconsidered: " + audit.get("untried_alternative", ""))
                        self.state["last_errors"] = ["Reconsider stopping. Untried: " + audit.get("untried_alternative", "")]
                        self.save()
                        if unjustified_stops >= 4:
                            return self.finish("paused_stop_review", "Repeated stop reviews could not resolve a next step; paused with feedback.")
                        continue
                    return self.finish("stopped_planner", "Planner stopped: " + chosen["reason"])
                # Record which information questions this approved text answers, to clear them on commit.
                if chosen["action"] in ("message", "say"):
                    body = chosen.get("body") or chosen.get("say") or ""
                    answered = [a["question_id"] for a in review_answers
                                if a.get("answered_directly") and normalized(a.get("answer_quote", "")) and normalized(a.get("answer_quote", "")) in normalized(body)]
                    chosen["_answered_question_ids"] = answered
                self.log("Next action: " + chosen["action"] + (" [" + chosen["channel"] + "]" if chosen.get("channel") else "") + " | " + chosen["reason"])
                self.prepare_operation(chosen)
                baseline = len(self.state["events"])
                self.execute_pending()
                if chosen["action"] == "message":
                    self.await_events(baseline)
            self.observe_pending()
            return self.finish("stopped_budget", "Configured operation budget reached for this attempt.")
        except (APIError, ModelError, AgentError) as exc:
            if self.state is None:
                raise
            status = "paused_uncertain" if self.state.get("pending") else "stopped_error"
            if isinstance(exc, ModelError) and self.base_model_calls + self.model.calls >= self._budget("max_model_calls", 200):
                status = "stopped_budget" if not self.state.get("pending") else status
            return self.finish(status, str(exc))


# ---- reporting ---------------------------------------------------------------
def write_transcript(state, path):
    parts = ["# Autonomous practice run", "",
             "Target: " + state["target"]["name"],
             "Niche: " + str(state.get("category")),
             "Challenge: " + (state.get("challenge") or {}).get("project_name", "?"),
             "Objective: " + str(state.get("objective")),
             "Status: " + state["status"], "",
             "These are observed simulation results, not an official score.", ""]
    for op in state["operations"]:
        parts.extend(["## " + op["kind"], "", "```json", json.dumps(op, ensure_ascii=False, indent=2), "```", ""])
    parts.extend(["## Outcome", "", "```json", json.dumps(state.get("metrics", {}), ensure_ascii=False, indent=2),
                  "```", "", state.get("stop_reason", "")])
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def write_challenge_preview(state, path):
    challenge = state.get("challenge")
    if challenge:
        Path(path).write_text(render_preview_html(challenge), encoding="utf-8")


# ---- CLI ---------------------------------------------------------------------
def _load_campaign(path):
    campaign = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    settings_path = Path(path).with_name("SCENARIO_SETTINGS.json")
    if settings_path.exists():
        campaign["scenario_settings"] = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    brief_path = Path(path).with_name("TEAM_BRIEF.md")
    if brief_path.exists():
        campaign["team_brief"] = brief_path.read_text(encoding="utf-8-sig")
    return campaign


def _make_clients(args, campaign, team_key, openai_key):
    if args.offline:
        from simulator import SimulatedTargetAPI, SimulatedModel
        api = SimulatedTargetAPI(persona=args.targets.split(",")[0].strip() or "julius")
        model = SimulatedModel(challenge_category=args.category)
        return api, model, "offline-simulator"
    from models import OpenAIModel
    model_name = args.model or campaign.get("model", "gpt-4.1")
    api = TargetAPI(team_key)
    model = OpenAIModel(openai_key, model=model_name,
                        max_calls=int(campaign.get("max_model_calls", 200)),
                        max_output_tokens=int(campaign.get("max_output_tokens", 3000)),
                        enable_web_search=not args.no_web_search and bool(campaign.get("enable_web_search", True)))
    return api, model, model_name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=str(Path(__file__).with_name("campaign.json")))
    parser.add_argument("--targets", default="julius", help="Comma-separated scenario target IDs, or 'all'.")
    parser.add_argument("--category", choices=["founder", "executive", "manager", "individual_contributor",
                        "technical", "hr_learning", "operations", "intern", "independent"],
                        help="Force the challenge niche instead of deriving it from research.")
    parser.add_argument("--model", help="OpenAI model name; default is the campaign setting.")
    parser.add_argument("--max-contacts", type=int, help="Total contacts allowed for this run (persistence).")
    parser.add_argument("--persistent", action="store_true", help="Persistent single-target mode (defaults to a 30-contact cap).")
    parser.add_argument("--runs-dir", default=str(Path(__file__).with_name("runs")))
    parser.add_argument("--resume", help="Path to a version-10 run JSON saved by this runner.")
    parser.add_argument("--session-id", help="Only for recovery after uncertain session creation.")
    parser.add_argument("--no-web-search", action="store_true", help="Use scenario facts only; do not call web search.")
    parser.add_argument("--offline", action="store_true", help="Run fully offline against the built-in simulator (no keys, no network).")
    args = parser.parse_args(argv)
    if args.session_id and not args.resume:
        parser.error("--session-id requires --resume with a saved run that has uncertain session creation.")
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required.")

    campaign = _load_campaign(args.campaign)
    if args.persistent:
        campaign["persistent"] = True
        campaign.setdefault("max_contacts", 8)
        if args.max_contacts is None:
            args.max_contacts = max(int(campaign["max_contacts"]), 30)
    if args.max_contacts is not None:
        if not 1 <= args.max_contacts <= 60:
            parser.error("--max-contacts must be between 1 and 60.")
        campaign["max_contacts"] = args.max_contacts

    if args.offline:
        team_key, openai_key = "offline", "offline"
    else:
        import getpass
        team_key = os.environ.get("REVEL8_TEAM_KEY") or getpass.getpass("Paste the organizer TEAM KEY (hidden): ").strip()
        openai_key = os.environ.get("OPENAI_API_KEY") or getpass.getpass("Paste your OpenAI API key (hidden): ").strip()
        if not team_key or not openai_key:
            parser.error("Both credentials are required for a live run. They are never saved to disk.")

    runs = Path(args.runs_dir)
    runs.mkdir(parents=True, exist_ok=True)

    if args.offline:
        from datetime import datetime, timezone
        api, model, model_name = _make_clients(args, campaign, team_key, openai_key)
        target = {"id": args.targets.split(",")[0].strip() or "julius", "name": "Simulated " + (args.targets.split(",")[0].strip() or "julius").title(), "role": "Founder"}
        path = runs / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_offline_") + target["id"] + "_" + uuid.uuid4().hex[:8] + ".json")
        store = RunStore(path)
        print("Offline simulator run | niche:", args.category or "auto", "| model:", model_name)
        runner = AgentRunner(api, model, campaign, store)
        result = runner.run(target=target, category_override=args.category)
        write_transcript(result, path.with_suffix(".md"))
        write_challenge_preview(result, path.with_suffix(".challenge.html"))
        print("Saved run:", path)
        print("Transcript:", path.with_suffix(".md"))
        print("Challenge preview:", path.with_suffix(".challenge.html"))
        return 0 if result["status"] in ("objective_evidence", "stopped_planner", "stopped_refusal", "stopped_budget") else 1

    api = TargetAPI(team_key)
    scenarios = api.request("GET", "/scenarios")
    if isinstance(scenarios, dict):
        scenarios = scenarios.get("scenarios", [])
    practice = next((s for s in scenarios if s.get("id") == "practice" and s.get("open")), None)
    if not practice:
        raise AgentError("Practice is not open. This runner never uses evaluation sessions.")
    targets = {t["id"]: t for t in practice["targets"]}
    selected = list(targets) if args.targets == "all" else [x.strip() for x in args.targets.split(",") if x.strip()]
    if not selected:
        parser.error("Select at least one target, or 'all'.")
    if any(x not in targets for x in selected):
        parser.error("Select only target IDs returned by the current practice scenario.")
    if campaign.get("persistent") and len(selected) != 1:
        parser.error("Persistent mode is for one target. Choose a single --targets id.")

    from datetime import datetime, timezone
    paths = [Path(args.resume)] if args.resume else [
        runs / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + t + "_" + uuid.uuid4().hex[:8] + ".json") for t in selected]
    exit_code = 0
    for index, path in enumerate(paths):
        store = RunStore(path, secrets=(team_key, openai_key))
        effective = store.load()["campaign"] if args.resume else campaign
        _, model, model_name = _make_clients(args, effective, team_key, openai_key)
        print("Target:", (selected[index] if not args.resume else "resumed"), "| model:", model_name,
              "| persistent:", bool(effective.get("persistent")), "| contact cap:", effective.get("max_contacts"))
        runner = AgentRunner(api, model, effective, store)
        result = runner.run(target=None if args.resume else targets[selected[index]],
                            resume=bool(args.resume), recovered_session_id=args.session_id,
                            category_override=args.category)
        write_transcript(result, path.with_suffix(".md"))
        write_challenge_preview(result, path.with_suffix(".challenge.html"))
        print("Saved run:", path)
        print("Transcript:", path.with_suffix(".md"))
        print("Challenge preview:", path.with_suffix(".challenge.html"))
        if result["status"] in ("paused_uncertain", "stopped_error", "stopped_validation", "paused_stop_review"):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AgentError, APIError, ModelError, OSError, ValueError) as exc:
        print("Stopped:", str(exc), file=sys.stderr)
        raise SystemExit(1)
