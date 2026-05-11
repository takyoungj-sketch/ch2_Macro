"""One-off: apply db/002_paid_analyze_index.sql to the DB from app settings."""
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_backend))

from sqlalchemy import create_engine, text

from app.config import settings

_root = _backend.parent
_sql_path = _root / "db" / "002_paid_analyze_index.sql"
raw = _sql_path.read_text(encoding="utf-8")
lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
sql = "\n".join(lines)

if not sql.strip():
    raise SystemExit("No SQL in 002_paid_analyze_index.sql")

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    conn.execute(text(sql))
    conn.commit()
print("OK:", _sql_path.name)
