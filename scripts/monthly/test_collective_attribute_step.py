"""집합 월간 러너 — 속성 없는 키만, 판은 인자로."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_collective_cycle_csv import (  # noqa: E402
    ATTRIBUTE_GAP_SQL,
    _run,
    attribute_commands_for_gap,
    attribute_fill_commands,
    build_parser,
    format_gap_key_file,
    guard_existing_snapshot,
    require_attribute_args,
)


def test_snapshot_comes_from_argument_not_filename():
    kapt = Path("raw/20261002_단지_기본정보.xlsx")
    cmds = attribute_fill_commands(
        py="py",
        pipeline=Path("pipeline"),
        snapshot_ym="202607",
        kapt_file=kapt,
        keys_file=Path("logs/gap.txt"),
    )
    assert [name for name, _cmd, _cwd in cmds] == ["kapt_new_keys", "title_fill_new_keys"]
    for _name, cmd, cwd in cmds:
        assert cmd[cmd.index("--snapshot-ym") + 1] == "202607"
        assert "--replace" not in cmd
        assert "--refresh-t" not in cmd
        assert "--cycle-id" not in cmd
        assert cwd == Path("pipeline")
    kapt_cmd = cmds[0][1]
    assert kapt_cmd[kapt_cmd.index("--kapt-file") + 1] == str(kapt)
    assert "--new-keys-only" in kapt_cmd
    assert "--keys-file" in kapt_cmd
    assert "202610" not in kapt_cmd[kapt_cmd.index("--snapshot-ym") + 1]
    title = cmds[1][1]
    assert title[1:3] == ["-m", "parcel_master.apply_title_fill"]


def test_empty_gap_calls_nothing():
    assert (
        attribute_commands_for_gap(
            py="py",
            pipeline=Path("pipeline"),
            snapshot_ym="202607",
            kapt_file=Path("a.xlsx"),
            keys_file=Path("gap.txt"),
            keys=[],
        )
        == []
    )


def test_gap_sql_reads_missing_keys_only():
    upper = ATTRIBUTE_GAP_SQL.upper()
    for word in ("UPDATE", "DELETE", "INSERT", "TRUNCATE"):
        assert word not in upper
    assert "NOT EXISTS" in upper
    assert "'APARTMENT'" in upper
    assert "'ROWHOUSE'" in upper
    assert "'OFFICETEL'" in upper


def test_key_file_records_the_explicit_snapshot():
    text = format_gap_key_file("202607", ["bbb", "aaa"])
    assert text.startswith("# snapshot_ym=202607")
    assert "bbb\naaa\n" in text
    assert "202610" not in text


def test_empty_snapshot_is_refused():
    try:
        guard_existing_snapshot(0, "202610")
    except SystemExit as exc:
        assert "202610" in str(exc)
    else:
        raise AssertionError("empty snapshot must stop")
    guard_existing_snapshot(45058, "202607")


def test_flags_do_not_infer_snapshot_from_the_file(tmp_path):
    src = tmp_path / "20261002_단지_기본정보.xlsx"
    src.write_bytes(b"x")
    ym, path = require_attribute_args(skip=False, snapshot_ym="202607", kapt_file=str(src))
    assert ym == "202607"
    assert path == src
    assert require_attribute_args(skip=True, snapshot_ym=None, kapt_file=None) is None
    refused = [
        dict(skip=False, snapshot_ym=None, kapt_file=str(src)),
        dict(skip=False, snapshot_ym="202607", kapt_file=None),
        dict(skip=False, snapshot_ym="202613", kapt_file=str(src)),
        dict(skip=False, snapshot_ym="202610", kapt_file=str(tmp_path / "missing.xlsx")),
    ]
    for kwargs in refused:
        try:
            require_attribute_args(**kwargs)
        except SystemExit:
            continue
        raise AssertionError(kwargs)


def test_parser_keeps_cycle_and_snapshot_apart():
    ns = build_parser().parse_args(
        [
            "--cycle-id",
            "202611",
            "--attr-snapshot-ym",
            "202607",
            "--kapt-file",
            "x.xlsx",
        ]
    )
    assert ns.cycle_id == "202611"
    assert ns.attr_snapshot_ym == "202607"
    assert ns.skip_attributes is False


def test_phase_runner_does_not_reread_outer_args():
    src = inspect.getsource(_run)
    assert "args" not in src
    assert "ledger_step" not in src
