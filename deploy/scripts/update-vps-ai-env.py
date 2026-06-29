"""VPS backend/.env — OpenAI 키 upsert (stdin JSON: openai_api_key, openai_model)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ENV_PATH = Path("/opt/ch2_Macro/backend/.env")


def main() -> None:
    payload = json.load(sys.stdin)
    key = str(payload.get("openai_api_key") or "").strip()
    model = str(payload.get("openai_model") or "gpt-4o-mini").strip()
    if not key:
        print("ERROR: openai_api_key required", file=sys.stderr)
        sys.exit(1)

    text = ENV_PATH.read_text(encoding="utf-8")
    updates = {
        "OPENAI_API_KEY": key,
        "OPENAI_MODEL": model,
        "AI_POLISH_ENABLED": str(payload.get("ai_polish_enabled", "false")),
        "AI_RATE_LIMIT_PER_MINUTE": str(payload.get("ai_rate_limit_per_minute", "30")),
    }
    for kk, vv in updates.items():
        if re.search(rf"^{kk}=", text, re.M):
            text = re.sub(rf"^{kk}=.*$", f"{kk}={vv}", text, flags=re.M)
        else:
            text = text.rstrip() + f"\n{kk}={vv}\n"
    ENV_PATH.write_text(text, encoding="utf-8")
    print("env ok")


if __name__ == "__main__":
    main()
