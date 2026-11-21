"""Generate standalone, styled previews of every niche's gamified challenge.

These are for the pitch and for designing the copy - they are NOT what the agent
sends. Inside the simulator the agent registers plain, text-first versions of the
same pages. Run `py preview.py` and open previews/index.html.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import challenge as ch

SAMPLE = {"employer_or_practice": "Acme", "seniority": "varies"}
TARGET = {"id": "sample", "name": "Sample Persona"}

INDEX_CSS = """
body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:#0f1424;color:#eef1f8}
.wrap{max-width:860px;margin:0 auto;padding:40px 20px}
h1{font-size:30px;margin:0 0 6px}.sub{color:#9aa6c4;margin:0 0 26px}
a.card{display:block;text-decoration:none;color:inherit;background:#1a2238;border:1px solid #2a3350;border-radius:14px;padding:18px 20px;margin:12px 0}
a.card:hover{border-color:#6ea8fe}
.t{font-size:18px;font-weight:700}.d{color:#9aa6c4;font-size:14px;margin-top:4px}
.badge{display:inline-block;font-size:12px;color:#7ef0c0;border:1px solid #2a3350;border-radius:999px;padding:4px 10px;margin-bottom:18px}
"""


def main() -> int:
    out = ROOT / "previews"
    out.mkdir(exist_ok=True)
    cards = []
    for niche in ch.CATEGORY_SPECS:
        challenge = ch.build_challenge(niche, SAMPLE, TARGET, "company-direction-review.com", {})
        (out / (niche + ".html")).write_text(ch.render_preview_html(challenge), encoding="utf-8")
        spec = ch.CATEGORY_SPECS[niche]
        cards.append('<a class="card" href="' + niche + '.html"><div class="t">' + escape(spec["label"])
                     + " - " + escape(spec["title"]) + '</div><div class="d">' + escape(spec["framing"]) + "</div></a>")
    index = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
             "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
             "<title>Revelate challenge previews</title><style>" + INDEX_CSS + "</style></head><body><div class=\"wrap\">"
             "<span class=\"badge\">pitch preview - not what the twin receives</span>"
             "<h1>Revelate gamified challenge</h1>"
             "<p class=\"sub\">A different two-round challenge per persona niche: Round 1 builds trust with light "
             "reasoning, Round 2 is a company-knowledge self-check. Click a niche to see its rounds.</p>"
             + "".join(cards) + "</div></body></html>")
    (out / "index.html").write_text(index, encoding="utf-8")
    print("Wrote", len(ch.CATEGORY_SPECS) + 1, "files to", out)
    print("Open:", out / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
