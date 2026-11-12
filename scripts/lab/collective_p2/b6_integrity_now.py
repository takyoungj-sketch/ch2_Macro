"""현재 로컬 DB(이전 전)에 integrity_p2 를 읽기 전용으로 돌려 본다 — 이전 전에는 ERR이 나와야 정상."""
import sys
from _db import ROOT, engine
sys.path.insert(0, str(ROOT / "pipeline"))
from collective.integrity_p2 import check_collective_p2
class R:
    errors = warnings = 0
    def section(self, t): print("==", t)
    def ok(self, m): print("[OK]", m)
    def warn(self, m): self.warnings += 1; print("[WARN]", m)
    def err(self, m): self.errors += 1; print("[ERR]", m)
    def info(self, m): print("     ", m)
with engine().connect() as c, engine("built").connect() as b:
    check_collective_p2(R(), c, b, deep=True)
