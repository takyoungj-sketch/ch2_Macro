#!/usr/bin/env python3
"""Local QA for /learn/stats/ static pages."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAPTERS = [
    ("index", None),
    ("data-and-variables", None),
    ("mean-and-median", None),
    ("quantiles", None),
    ("spread", None),
    ("iqr-outliers", ["iqr-multiplier"]),
    ("sample-size", None),
    ("correlation", None),
    ("regression", None),
    ("log-regression", None),
    ("model-fit", ["r-squared", "adj-r-squared", "mape"]),
    ("cross-validation", ["cross-validation", "cv-mape", "model-recommendation"]),
    ("reading-results", None),
]

MOJIBAKE_MARKERS = ("?계", "?이", "?료", "???", "\ufffd")

errors: list[str] = []
warnings: list[str] = []


def check_file(slug: str, required_ids: list[str] | None) -> None:
    rel = "index.html" if slug == "index" else f"{slug}/index.html"
    path = ROOT / rel
    if not path.exists():
        errors.append(f"{rel}: missing file")
        return

    text = path.read_text(encoding="utf-8")
    label = rel

    if any(m in text for m in MOJIBAKE_MARKERS):
        errors.append(f"{label}: possible encoding corruption")

    if "learn-stats-toc.js" not in text:
        errors.append(f"{label}: missing learn-stats-toc.js")

    if slug == "index":
        if text.count("/learn/stats/") < 12:
            warnings.append(f"{label}: expected 12+ chapter hrefs")
        return

    if text.count('class="learn-chapter__step"') < 5:
        errors.append(f"{label}: expected 5 sections")

    if "learn-macro-mock" not in text:
        errors.append(f"{label}: missing learn-macro-mock")

    if "청주시 흥덕구" not in text:
        warnings.append(f"{label}: missing 청주시 흥덕구")

    for rid in required_ids or []:
        if f'id="{rid}"' not in text:
            errors.append(f"{label}: missing id #{rid}")

    for m in re.findall(r'href="(/learn/stats/([a-z0-9-]+)/)"', text):
        href, sub = m
        if not (ROOT / sub / "index.html").exists():
            errors.append(f"{label}: broken chapter link {href}")


def main() -> int:
    for slug, ids in CHAPTERS:
        check_file(slug, ids)

    print("=== Learn Stats QA ===")
    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nNo errors.")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
