"""built import UPSERT — 해시 유지 시 원장 컬럼을 갱신한다."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "built" / "import_molit.py"


def test_insert_upserts_ledger_fields():
    sql = SRC.read_text(encoding="utf-8")
    assert "ON CONFLICT (transaction_hash) DO UPDATE SET" in sql
    assert "gross_area = EXCLUDED.gross_area" in sql
    assert "beopjungri_code = EXCLUDED.beopjungri_code" in sql
    assert "price = EXCLUDED.price" in sql
    assert "mapping_notes = EXCLUDED.mapping_notes" in sql
