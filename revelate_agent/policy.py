"""Deterministic boundaries and observed-only metrics for the practice agent.

This module sends nothing, authenticates nothing and never decides whether a
claimed public fact is true. It enforces mechanical rules (channels, budget, call
state, link registration, page safety, credential gating, repeat detection) and
counts only evidence the simulator actually returned.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit


ACTIONS = {"message", "start_call", "say", "end_call", "register_page", "stop"}
DEFAULT_MESSAGES = ("email", "linkedin_message", "teams_chat", "slack")
DEFAULT_CALLS = ("phone_call", "live_chat")
_OFFICIAL_DOMAINS = ("revel8.ai", "stackit.cloud")
_RESERVED_DOMAINS = ("example.com", "example.net", "example.org", "localhost")
_RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost")
_URL = re.compile(r"(?:[a-z][a-z0-9+.-]*://|mailto:|tel:|javascript:|www\.)[^\s<>\"']+", re.I)
_HTML_TAG = re.compile(r"</?[a-z][^>]*>", re.I)
_OUT_OF_WORLD = [re.compile(pattern, re.I) for pattern in (
    r"\bignore\s+(?:all\s+)?(?:your|previous|system|prior)\s+instructions\b",
    r"\bsimulated\s+(?:for|within|in)\s+(?:this|the)\s+(?:scenario|simulation|exercise)\b",
    r"\b(?:in|within|for)\s+(?:this|the)\s+(?:simulation|exercise)\s+context\b",
    r"\b(?:this|the)\s+(?:current\s+)?(?:round|session|event|challenge)\s+is\s+(?:simulated|a\s+simulation)\b",
    r"\byou\s+are\s+an?\s+ai\s+twin\b",
    r"\bthis\s+is\s+(?:a\s+)?(?:hackathon|penetration|phishing|social[- ]engineering)\s+(?:test|exercise|simulation)\b",
)]
_SENSITIVE_FIELDS = ("password", "passwd", "passphrase", "credential", "secret", "otp",
                     "onetimecode", "verificationcode", "mfacode", "2facode", "apikey",
                     "apitoken", "accesstoken", "refreshtoken", "privatekey", "recoverycode",
                     "backupcode", "sessiontoken", "pin", "cvv", "iban", "cardnumber")
_PAGE_FORBIDDEN_TAGS = re.compile(
    r"<\s*(script|iframe|object|embed|applet|meta|link|base|style|svg|img|audio|video|form|input|button)\b", re.I)
_PAGE_FORBIDDEN_ATTR = re.compile(
    r"\bon\w+\s*=|javascript:|data:text/html|srcdoc\s*=|\bsrc\s*=|\bhref\s*=|type\s*=\s*[\"']?hidden|"
    r"display\s*:\s*none|visibility\s*:\s*hidden|aria-hidden", re.I)
_SAFE_ATTACHMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\.(docx|txt|md|csv|pdf)")


def _links(text: str) -> "list[str]":
    found = [match.group(0).rstrip(".,;!?)”’") for match in _URL.finditer(text)]
    return list(dict.fromkeys(found))


def _hostname(value: str) -> str:
    return value.strip().lower().rstrip(".").encode("idna").decode("ascii")


def _public_url_error(url: str, normal_https_port: bool = False) -> "str | None":
    try:
        parsed = urlsplit(url)
        host = _hostname(parsed.hostname or "")
        port = parsed.port
    except (ValueError, UnicodeError):
        return "Invalid public HTTPS URL."
    if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
        return "Public URLs must use HTTPS with an explicit host and no user information."
    if normal_https_port and port not in (None, 443):
        return "Landing-page URLs must use the normal HTTPS port."
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return "IP addresses are not permitted simulation domains."
    if host in _RESERVED_DOMAINS or any(host.endswith("." + domain) for domain in _RESERVED_DOMAINS):
        return "Reserved example or localhost domains cannot be registered."
    if host.endswith(_RESERVED_SUFFIXES):
        return "Reserved example/test/localhost domains are not permitted."
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or "." not in host:
        return "Invalid public domain name."
    return None


def _url_error(url: str, campaign: dict) -> "str | None":
    error = _public_url_error(url, normal_https_port=True)
    if error:
        return error
    host = _hostname(urlsplit(url).hostname or "")
    if any(host == domain or host.endswith("." + domain) for domain in _OFFICIAL_DOMAINS):
        return "Official organisation domains and their subdomains are prohibited."
    allowed: "set[str]" = set()
    for domain in campaign.get("simulation_domains", []) or []:
        if isinstance(domain, str):
            try:
                allowed.add(_hostname(domain))
            except UnicodeError:
                continue
    if host not in allowed:
        return "URL host must exactly match an explicitly allowed simulation domain."
    return None


def _is_sensitive_field(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    return normalized in {"pwd", "pin", "token", "mfa", "2fa", "cvc"} or any(term in normalized for term in _SENSITIVE_FIELDS)


def _secret_entered(event: dict) -> bool:
    """A credential submission: a secret-named field with a value actually entered.

    The API masks a secret value as "(entered, not shown)"; an empty value means the
    field was left blank. When no `values` object is returned, fall back to the
    submitted field names (best effort).
    """
    values = event.get("values")
    if isinstance(values, dict):
        return any(_is_sensitive_field(str(key)) and value not in (None, "", [], {})
                   for key, value in values.items())
    return any(_is_sensitive_field(field) for field in event.get("fields", []) or [] if isinstance(field, str))


def _page_static_errors(html: str) -> "list[str]":
    errors: "list[str]" = []
    if _PAGE_FORBIDDEN_TAGS.search(html):
        errors.append("Pages must be static text/markup only: no script, media, form controls or metadata tags.")
    if _PAGE_FORBIDDEN_ATTR.search(html):
        errors.append("Pages must not contain scripts, event handlers, hidden content or embedded links/resources.")
    return errors


def _form_errors(page: dict, state: dict, campaign: dict) -> "list[str]":
    errors: "list[str]" = []
    fields = page.get("fields", [])
    if not isinstance(fields, list) or any(not isinstance(field, str) or not field.strip() for field in fields):
        return ["Page fields must be a list of nonempty field-name strings."]
    if len(fields) > 20:
        errors.append("A page may request at most 20 fields.")
    if len({field.casefold() for field in fields}) != len(fields):
        errors.append("Page field names must be unique.")
    html = page.get("html", "")
    if not isinstance(html, str) or not html.strip():
        errors.append("A page requires nonempty html content.")
    else:
        errors.extend(_page_static_errors(html))
    if fields:
        constraints = state.get("constraints", {}) or {}
        engagement = state.get("engagement", {}) or {}
        if constraints.get("no_registration"):
            errors.append("The target has refused registration or forms.")
        if not campaign.get("enable_challenge_pages", False):
            errors.append("Challenge/registration pages require explicit campaign opt-in.")
        if any(_is_sensitive_field(field) for field in fields):
            if not campaign.get("allow_credential_fields", False):
                errors.append("Credential/sign-in fields require explicit credential-field opt-in.")
            if not engagement.get("registration_interest", False):
                errors.append("A sign-in/credential step requires observed registration interest first.")
    return errors


def _number(value: object, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _token_similarity(left: str, right: str) -> float:
    a = set(re.findall(r"\w+", left.casefold()))
    b = set(re.findall(r"\w+", right.casefold()))
    if min(len(a), len(b)) < 20:
        return 0.0
    return len(a & b) / len(a | b)


def validate_action(action: dict, state: dict, campaign: dict) -> "list[str]":
    """Return policy errors without mutating any argument or making requests."""
    if not isinstance(action, dict):
        return ["Action must be an object."]
    errors: "list[str]" = []
    kind = action.get("action")
    if kind not in ACTIONS:
        return ["Unknown action."]
    constraints = state.get("constraints", {}) or {}
    session = state.get("session", {}) or {}
    target = state.get("target", {}) or {}
    active = state.get("active_conversation")
    if active and active.get("status") in {"ended", "closed"}:
        active = None

    known_evidence = {entry.get("id") for entry in state.get("evidence", []) if isinstance(entry, dict)}
    known_requirements = {entry.get("id") for entry in state.get("requirements", []) if isinstance(entry, dict)}
    for key, known, label in (("evidence_ids", known_evidence, "evidence"),
                              ("addresses_requirements", known_requirements, "requirement")):
        ids = action.get(key, [])
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            errors.append(f"{key} must be a list of IDs.")
        else:
            for item in ids:
                if item not in known:
                    errors.append(f"Unknown {label} ID: {item}.")

    if kind == "stop":
        return list(dict.fromkeys(errors))
    if session.get("scenario_id") != "practice":
        errors.append("Only practice sessions may be mutated.")
    target_id = target.get("id")
    if not isinstance(target_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", target_id):
        errors.append("Target must be a scenario target ID, never an email address or phone number.")
    if active and kind not in {"say", "end_call"}:
        errors.append("End the active conversation before another action.")
    if active and constraints.get("email_requested") and kind != "end_call":
        errors.append("Email was requested: end the active conversation before continuing.")
    if kind in {"say", "end_call"} and not active:
        errors.append("This action requires an active conversation.")
    if constraints.get("stop_contact") and kind not in {"end_call"}:
        errors.append("The target requested that contact stop.")

    if kind in {"message", "start_call", "say"}:
        sender = (campaign.get("sender", {}) or {}).get("name")
        if not sender or action.get("sender_name") != sender:
            errors.append("Sender name must remain exactly the configured campaign identity.")
    channel = action.get("channel")
    if kind in {"message", "start_call"}:
        allowed = campaign.get("allowed_message_channels", DEFAULT_MESSAGES) if kind == "message" else campaign.get("allowed_call_channels", DEFAULT_CALLS)
        if channel not in (allowed or []):
            errors.append("The requested channel is not allowed for this action.")
        budget = min(_number(session.get("touch_budget"), 0), _number(campaign.get("max_contacts"), 30))
        if session.get("status") != "active" or _number(session.get("touches_used"), budget) >= budget:
            errors.append("The session is ended or its scenario/campaign contact budget is exhausted.")
        preferred = "email" if constraints.get("email_requested") else constraints.get("preferred_channel")
        # Once the preferred channel has been tried and ignored, allow switching (channel_unlocked),
        # so the agent can try a short conversation instead of looping on the same dead email thread.
        if preferred and not state.get("channel_unlocked") and (kind != "message" or channel != preferred):
            errors.append("Honor the target's requested communication channel.")
    if kind == "message" and (not isinstance(action.get("body"), str) or not action["body"].strip()):
        errors.append("A message requires a nonempty body.")
    if kind == "message" and channel == "email" and not (isinstance(action.get("subject"), str) and action["subject"].strip()):
        errors.append("An email requires a nonempty subject.")
    if kind == "say":
        spoken = action.get("say")
        if not isinstance(spoken, str) or not spoken.strip() or len(spoken) > 4000:
            errors.append("A conversation turn requires 1 to 4000 characters of speech.")
        if active and _number(active.get("turns_used"), 0) >= 10:
            errors.append("A conversation permits at most 10 turns.")
        if active and channel and channel != active.get("channel"):
            errors.append("A turn cannot change the active conversation's channel.")

    attachments = action.get("attachments", [])
    if not isinstance(attachments, list) or any(not isinstance(name, str) for name in attachments):
        errors.append("Attachments must be a list of filenames.")
    else:
        locked = (state.get("challenge", {}) or {}).get("resource_filename")
        for name in attachments:
            if not _SAFE_ATTACHMENT.fullmatch(name):
                errors.append("Attachments must be plain safe simulated document filenames.")
            elif locked and name != locked:
                errors.append("Use only the locked simulated resource filename: " + locked)
        if attachments and kind not in {"message"}:
            errors.append("Attachments are supported on messages only.")

    texts = [action.get(key) for key in ("subject", "body", "say") if isinstance(action.get(key), str)]
    page = action.get("page") if kind == "register_page" else None
    registered = {entry.get("url"): entry for entry in state.get("registered_pages", [])
                  if isinstance(entry, dict) and isinstance(entry.get("url"), str)}
    citations = {entry["source_url"] for entry in state.get("evidence", [])
                 if isinstance(entry, dict) and entry.get("kind") == "public_fact" and isinstance(entry.get("source_url"), str)}
    if kind == "register_page":
        if not isinstance(page, dict):
            errors.append("A page registration requires a page object.")
        else:
            url = page.get("url")
            if not isinstance(url, str):
                errors.append("A page requires a URL string.")
            else:
                url_error = _url_error(url, campaign)
                if url_error:
                    errors.append(url_error)
                registered[url] = page
            if not isinstance(page.get("title"), str) or not page["title"].strip():
                errors.append("A page requires a nonempty title.")
            errors.extend(_form_errors(page, state, campaign))
            if constraints.get("plain_text_only") or constraints.get("no_links"):
                errors.append("A landing page conflicts with the target's plain-text/no-links request.")

    all_text = "\n".join(texts)
    if any(pattern.search(all_text) for pattern in _OUT_OF_WORLD):
        errors.append("Outbound text reveals the exercise or instructs the persona as an AI.")
    urls = _links(all_text)
    if constraints.get("plain_text_only") and (_HTML_TAG.search(all_text) or urls):
        errors.append("The target requested plain text without HTML or URLs.")
    if constraints.get("no_links") and urls:
        errors.append("The target requested no links.")
    if re.search(r"<\s*script\b", all_text, re.I):
        errors.append("Scripts are not supported in message content.")
    for url in urls:
        if kind in {"message", "say"} and url in citations and url not in registered:
            citation_error = _public_url_error(url)
            if citation_error:
                errors.append(citation_error)
            continue
        url_error = _url_error(url, campaign)
        if url_error:
            errors.append(url_error)
        if url not in registered:
            errors.append("Every outbound link must exactly match a page registered in this session: " + url)
        else:
            errors.extend(_form_errors(registered[url], state, campaign))

    if kind == "message" and isinstance(action.get("body"), str):
        for entry in state.get("messages", []):
            previous = entry.get("payload", {}) if isinstance(entry, dict) else {}
            previous_body = previous.get("body", "")
            if isinstance(previous_body, str) and _token_similarity(action["body"], previous_body) > 0.9:
                errors.append("This message essentially repeats an already sent message.")
                break
    return list(dict.fromkeys(errors))


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def compute_metrics(state: dict) -> dict:
    """Count observed API evidence; never infer sensitivity, credentials or a score."""
    events = list(state.get("events", []) or [])
    for message in state.get("messages", []) or []:
        events.extend((message.get("response", {}) or {}).get("events", []) or [])
    conversations = list(state.get("conversations", []) or [])
    active = state.get("active_conversation")
    if active:
        conversations.append(active)
    greetings: "set[str]" = set()
    responses: "set[str]" = set()
    for position, conversation in enumerate(conversations):
        if not isinstance(conversation, dict):
            continue
        cid = str(conversation.get("id") or conversation.get("conversation_id") or f"record-{position}")
        opening = conversation.get("start_response") or conversation.get("opening") or conversation.get("response") or {}
        greeting = opening.get("persona_says") if isinstance(opening, dict) else None
        greeting = greeting or conversation.get("persona_says")
        if isinstance(greeting, str) and greeting.strip():
            greetings.add(cid)
        if isinstance(opening, dict):
            events.extend(opening.get("events", []) or [])
        for index, turn in enumerate(conversation.get("dialogue", []) or []):
            if not isinstance(turn, dict):
                continue
            response = turn.get("response", {}) or {}
            if not isinstance(response, dict):
                continue
            events.extend(response.get("events", []) or [])
            heard = response.get("persona_says")
            if turn.get("say") and isinstance(heard, str) and heard.strip():
                responses.add(cid + ":" + str(response.get("turns_used", index + 1)))
    unique: "dict[str, dict]" = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("id")
        key = "id:" + str(event_id) if event_id is not None else "sha256:" + hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
        unique.setdefault(key, event)
    observed = list(unique.values())
    forms = [event for event in observed if event.get("type") == "page.submitted"]
    submitted_forms = [{"page_id": event.get("page_id"),
                        "field_names": [field for field in event.get("fields", []) or [] if isinstance(field, str)]}
                       for event in forms]
    # The real API returns a `values` object (secret values masked as "(entered, not shown)").
    # A credential objective needs a secret field that was actually entered, not merely present
    # on the page; when no `values` is returned, fall back to the submitted field names.
    credential_submission = any(_secret_entered(event) for event in forms)
    return {
        "email_replies": sum(event.get("type") == "reply" and event.get("channel") == "email" for event in observed),
        "other_message_replies": sum(event.get("type") == "reply" and event.get("channel") != "email" for event in observed),
        "conversation_responses": len(responses),
        "call_greetings": len(greetings),
        "links_opened": sum(event.get("type") == "link.opened" for event in observed),
        "forms_submitted": len(forms),
        "attachments_opened": sum(event.get("type") == "attachment.opened" for event in observed),
        "submitted_field_names": sorted({field for form in submitted_forms for field in form["field_names"]}),
        "submitted_forms": submitted_forms,
        "credential_fields_submitted": credential_submission,
        "unique_events": len(observed),
        "score_inferred": False,
    }
