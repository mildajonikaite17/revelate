"""One-shot verifier. Run `py verify.py` to prove the agent is wired correctly.

It needs NO revel8 key, NO OpenAI key and NO network. It:
  1. runs the full unit and integration test suites,
  2. runs a complete offline campaign for every persona niche and checks each one
     reaches recorded objective evidence through the gamified two-round challenge,
  3. confirms every challenge page the agent would register is static and safe.

Exit code 0 means everything passed.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import challenge as ch
from policy import _page_static_errors, _is_sensitive_field
from agent import AgentRunner
from simulator import SimulatedTargetAPI, SimulatedModel

NICHES = ["founder", "executive", "manager", "individual_contributor",
          "technical", "hr_learning", "operations", "intern", "independent"]


def _campaign():
    return {"name": "verify", "objectives": ["disclosure", "action", "credentials"],
            "allowed_message_channels": ["email", "linkedin_message", "teams_chat", "slack"],
            "allowed_call_channels": ["phone_call", "live_chat"],
            "simulation_domains": ["company-direction-review.com"],
            "enable_challenge_pages": True, "allow_credential_fields": True,
            "max_contacts": 30, "max_actions": 120, "max_model_calls": 200, "persistent": True}


def run_tests() -> bool:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    print("  tests run:", result.testsRun, "| failures:", len(result.failures), "| errors:", len(result.errors))
    for case, trace in result.failures + result.errors:
        print("  FAILED:", case)
        print("   ", trace.strip().splitlines()[-1])
    return result.wasSuccessful()


def run_campaigns() -> bool:
    ok = True
    for niche in NICHES:
        api = SimulatedTargetAPI(persona="julius")
        model = SimulatedModel(challenge_category=niche)
        runner = AgentRunner(api, model, _campaign(), _MemStore(), log=lambda *a, **k: None)
        with redirect_stdout(io.StringIO()):
            # Use a generic, UNPINNED target id so the per-twin niche pins (TARGET_CATEGORY)
            # don't override the niche this campaign is exercising.
            result = runner.run(target={"id": "verify-target", "name": "Test Target", "role": "Founder"})
        metrics = result.get("metrics", {})
        passed = (result["status"] == "objective_evidence" and metrics.get("credential_fields_submitted")
                  and metrics.get("forms_submitted") == 3 and result["category"] == niche)
        print(f"  {niche:<24} status={result['status']:<18} forms={metrics.get('forms_submitted')} "
              f"creds={metrics.get('credential_fields_submitted')}  {'OK' if passed else 'FAIL'}")
        ok = ok and passed
    return ok


def check_pages() -> bool:
    ok = True
    for niche in ch.CATEGORY_SPECS:
        challenge = ch.build_challenge(niche, {"employer_or_practice": "Acme"}, {"id": "x", "name": "X"},
                                       "company-direction-review.com", {})
        for key in ("about", "round1", "round2", "confirm"):
            page = ch.challenge_page(challenge, key)
            errors = _page_static_errors(page["html"])
            if errors or len(page["fields"]) != len(set(page["fields"])) or len(page["fields"]) > 20:
                print(f"  {niche}/{key}: PAGE PROBLEM {errors}")
                ok = False
        if any(_is_sensitive_field(f) for f in challenge["rounds"]["round1"]["fields"] + challenge["rounds"]["round2"]["fields"]):
            print(f"  {niche}: a reasoning round unexpectedly contains a credential field")
            ok = False
    print(f"  checked {len(ch.CATEGORY_SPECS)} niches x 4 pages: {'all static and safe' if ok else 'PROBLEM'}")
    return ok


class _MemStore:
    def __init__(self):
        self._state = None

    def exists(self):
        return self._state is not None

    def load(self):
        import json
        return json.loads(json.dumps(self._state))

    def save(self, state):
        import json
        self._state = json.loads(json.dumps(state))


def main() -> int:
    print("Revelate agent verification (offline, no keys, no network)\n")
    print("[1/3] Running unit and integration tests...")
    tests_ok = run_tests()
    print("\n[2/3] Running a full offline challenge campaign for every niche...")
    campaigns_ok = run_campaigns()
    print("\n[3/3] Checking every challenge page is static and safe...")
    pages_ok = check_pages()
    print("\n" + "=" * 60)
    all_ok = tests_ok and campaigns_ok and pages_ok
    print("RESULT:", "PASS - the agent is wired correctly." if all_ok else "FAIL - see messages above.")
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
