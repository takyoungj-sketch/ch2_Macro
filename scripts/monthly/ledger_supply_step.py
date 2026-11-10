"""Non-fatal ledger supply step shared by the three monthly runners."""

from __future__ import annotations

import json
import subprocess
from datetime import date


def ledger_step(repo, python, log, domain, phase, cycle, y_from, y_to):
    start = date(int(y_from[:4]), int(y_from[4:]), 1)
    month = int(y_to[4:])
    stop = date(int(y_to[:4]) + int(month == 12), month % 12 + 1, 1)
    out = repo / "clean_snapshots" / cycle / "ledger_supply"
    baseline = out / f"{domain}_before.json.gz"
    report = out / f"{domain}_coverage.json"
    cmd = [
        python, str(repo / "pipeline" / "monthly_ledger_supply.py"), phase, domain,
        "--cycle-id", cycle, "--start", str(start), "--stop", str(stop),
        "--baseline", str(baseline), "--report", str(report),
    ]
    try:
        subprocess.run(cmd, cwd=repo, check=True)
        return True
    except (subprocess.CalledProcessError, OSError) as exc:
        log.warning("%s 대장 공급 %s 실패 (%s). 월간 실거래 작업을 계속합니다.",
                    domain, phase, type(exc).__name__)
        try:
            out.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps({"domain": domain, "cycle": cycle, "warning": f"{phase}_failed"}),
                              encoding="utf-8")
        except OSError:
            log.warning("%s 대장 공급 경고 파일을 기록할 수 없습니다.", domain)
        return False
