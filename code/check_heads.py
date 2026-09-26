"""Every published page must carry the same head furniture -- asserted, not remembered.

Why this exists: the icon and link-preview tags were added to the three pages on 2026-09-26, but
now.html is REGENERATED every day by make_now.py, whose template did not have them. The next
06:01 sync would have deleted them, in a commit labelled "data: sync ..." where nobody would look.
The template is fixed; this check is what keeps the next generator from undoing it.

    python code/check_heads.py           check the three published pages
    python code/check_heads.py --fix     not supported: a check that edits is a check nobody runs
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# page -> the og:url that page must declare (the canonical address of ITSELF)
PAGES = {
    "index.html": "https://dirkdiggler1026.github.io/executability-report/",
    "index.zh.html": "https://dirkdiggler1026.github.io/executability-report/",
    "now.html": "https://dirkdiggler1026.github.io/executability-report/now.html",
}

ASSETS = ["favicon.ico", "favicon-32.png", "apple-touch-icon.png", "og-image.png"]

REQUIRED_META = ["og:type", "og:title", "og:description", "og:image", "og:image:width",
                 "og:image:height", "og:image:alt", "og:url", "og:locale", "og:site_name"]
REQUIRED_LINK = ["favicon.ico", "favicon-32.png", "apple-touch-icon.png"]


def main() -> int:
    bad: list[str] = []
    for name in ASSETS:
        if not (ROOT / name).is_file():
            bad.append(f"{name} is missing from the repository root")

    for page, og_url in PAGES.items():
        p = ROOT / page
        if not p.is_file():
            bad.append(f"{page} is missing")
            continue
        html = p.read_text(encoding="utf-8")
        head_end = html.find("</head>")
        if head_end < 0:
            bad.append(f"{page}: no </head>")
            continue
        head = html[:head_end]

        if "<title>" not in head:
            bad.append(f"{page}: <title> is not inside <head>")
        for tag in REQUIRED_LINK:
            if tag not in head:
                bad.append(f"{page}: no <link> for {tag}")
        for prop in REQUIRED_META:
            if f'property="{prop}"' not in head:
                bad.append(f"{page}: no {prop}")
        if f'name="twitter:card"' not in head:
            bad.append(f"{page}: no twitter:card")
        if f'content="{og_url}"' not in head:
            bad.append(f"{page}: og:url is not {og_url}")
        m = re.search(r'property="og:image" content="([^"]+)"', head)
        if m and not m.group(1).startswith("https://"):
            bad.append(f"{page}: og:image is relative ({m.group(1)}) -- scrapers will not "
                       f"resolve it")
        if "<meta name=\"description\"" not in head:
            bad.append(f"{page}: no <meta name=description>")

    for line in bad:
        print("  FAIL", line)
    print(f"\n{'FAILED: ' + str(len(bad)) + ' head problem(s)' if bad else 'ok -- three pages, one head'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
