"""
행정구역 위상 인접 그래프 빌드 → land_stats.region_neighbors

예시 (repo root):
  python pipeline/build_region_neighbors.py --sigungu 43113
  python pipeline/build_region_neighbors.py --sido 43
  python pipeline/build_region_neighbors.py --all
  python pipeline/build_region_neighbors.py --all --skip-existing

필요: VWORLD_API_KEY, DATABASE_URL (backend/.env), shapely
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(_ROOT / "pipeline"))

from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text

load_dotenv(_BACKEND / ".env")

_LOG_DIR = _ROOT / "pipeline" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_DIR / "region_neighbors_build.log", encoding="utf-8"),
    ],
)
_LOG = logging.getLogger("build_region_neighbors")

try:
    from shapely.geometry import shape
except ImportError as exc:  # pragma: no cover
    raise SystemExit("shapely 필요: pip install shapely") from exc

from app.map.vworld_client import (  # noqa: E402
    _stamp_ch2_codes,
    bbox_from_features,
    box_geom_filter,
    expand_bbox,
    fetch_features_soft,
)


def _database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        url = "postgresql+psycopg2://postgres:password@localhost:5432/land_stats"
    return url


def _vworld_creds() -> tuple[str, str]:
    key = (os.environ.get("VWORLD_API_KEY") or "").strip()
    domain = (os.environ.get("VWORLD_API_DOMAIN") or "localhost").strip()
    if not key:
        raise SystemExit("VWORLD_API_KEY 없음")
    return key, domain


def _code_of(feat: dict, *, level: str = "eupmyeondong") -> str | None:
    props = feat.get("properties") or {}
    if level == "beopjungri":
        code = props.get("ch2_code") or props.get("li_cd")
        if code is None:
            return None
        s = str(code).strip()
        # 리: 10자리. …00(법정동)은 리 그래프에서 제외
        if len(s) >= 10 and not s.endswith("00"):
            return s[:10]
        return None
    code = props.get("ch2_code") or props.get("emd_cd")
    if code is None:
        return None
    s = str(code).strip()
    if len(s) >= 10 and s.endswith("00"):
        s = s[:8]
    elif len(s) > 8:
        s = s[:8]
    return s or None


def fetch_emd_for_sigungu(api_key: str, domain: str, sig5: str) -> list[dict]:
    attr = f"emd_cd:like:{sig5}%"
    fc = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level="eupmyeondong",
        attr_filter=attr,
        size=1000,
    )
    _stamp_ch2_codes(
        fc.get("features") or [],
        request_level="eupmyeondong",
        effective_level="eupmyeondong",
    )
    return list(fc.get("features") or [])


def fetch_ri_for_sigungu(api_key: str, domain: str, sig5: str) -> list[dict]:
    attr = f"li_cd:like:{sig5}%"
    fc = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level="beopjungri_ri",
        attr_filter=attr,
        size=1000,
    )
    feats = list(fc.get("features") or [])
    _stamp_ch2_codes(
        feats,
        request_level="beopjungri",
        effective_level="beopjungri_ri",
    )
    if len(feats) >= 1000:
        _LOG.warning("sigungu=%s RI fetch hit size=1000 — may be truncated", sig5)
    return feats


def fetch_emd_near_bbox(
    api_key: str,
    domain: str,
    bbox: tuple[float, float, float, float],
    *,
    pad_deg: float = 0.04,
) -> list[dict]:
    padded = expand_bbox(bbox, pad_deg)
    geom = box_geom_filter(padded)
    fc = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level="eupmyeondong",
        geom_filter=geom,
        size=1000,
    )
    _stamp_ch2_codes(
        fc.get("features") or [],
        request_level="eupmyeondong",
        effective_level="eupmyeondong",
    )
    return list(fc.get("features") or [])


def fetch_ri_near_bbox(
    api_key: str,
    domain: str,
    bbox: tuple[float, float, float, float],
    *,
    pad_deg: float = 0.04,
) -> list[dict]:
    padded = expand_bbox(bbox, pad_deg)
    geom = box_geom_filter(padded)
    fc = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level="beopjungri_ri",
        geom_filter=geom,
        size=1000,
    )
    feats = list(fc.get("features") or [])
    _stamp_ch2_codes(
        feats,
        request_level="beopjungri",
        effective_level="beopjungri_ri",
    )
    return feats


def merge_features_by_code(*groups: list[dict], level: str = "eupmyeondong") -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for group in groups:
        for feat in group:
            code = _code_of(feat, level=level)
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(feat)
    return out


def list_sigungu_codes(api_key: str, domain: str, sido2: str | None = None) -> list[str]:
    attr = f"sig_cd:like:{sido2}%" if sido2 else None
    fc = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level="sigungu",
        attr_filter=attr,
        size=1000,
    )
    out: list[str] = []
    seen: set[str] = set()
    for feat in fc.get("features") or []:
        props = feat.get("properties") or {}
        sig = str(props.get("sig_cd") or "").strip()
        if len(sig) < 5:
            continue
        sig5 = sig[:5]
        if sig5 in seen:
            continue
        seen.add(sig5)
        out.append(sig5)
    return sorted(out)


# 시도 코드 (행정개편 포함). VWorld 시도 레이어 JSON 오류 시 폴백.
_SIDO_CODES_FALLBACK = [
    "11",  # 서울
    "26",  # 부산
    "27",  # 대구
    "28",  # 인천
    "29",  # 광주
    "30",  # 대전
    "31",  # 울산
    "36",  # 세종
    "41",  # 경기
    "42",  # 강원(구)
    "43",  # 충북
    "44",  # 충남
    "45",  # 전북(구)
    "46",  # 전남
    "47",  # 경북
    "48",  # 경남
    "50",  # 제주
    "51",  # 강원(신)
    "52",  # 전북(신)
]


def list_sigungu_from_db(engine, *, level: str = "eupmyeondong") -> list[str]:
    """land_stats.region_codes 에서 시군구 5자리 목록."""
    if level == "beopjungri":
        # 리가 실제로 있는 시군구만 (법정동 …00 제외)
        sql = """
            SELECT DISTINCT LEFT(beopjungri_code, 5) AS sig
            FROM region_codes
            WHERE beopjungri_code IS NOT NULL
              AND LENGTH(TRIM(beopjungri_code)) >= 10
              AND RIGHT(TRIM(beopjungri_code), 2) <> '00'
            ORDER BY 1
        """
    else:
        sql = """
            SELECT DISTINCT LEFT(eupmyeondong_code, 5) AS sig
            FROM region_codes
            WHERE eupmyeondong_code IS NOT NULL
              AND LENGTH(TRIM(eupmyeondong_code)) >= 5
            ORDER BY 1
        """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    out = [str(r[0]).strip() for r in rows if r[0] and str(r[0]).strip()]
    return sorted({s[:5] for s in out if len(s) >= 5})


def list_all_sido_codes(api_key: str, domain: str) -> list[str]:
    try:
        fc = fetch_features_soft(
            api_key=api_key,
            domain=domain,
            level="sido",
            size=100,
        )
    except Exception as exc:
        _LOG.warning("VWorld sido list failed (%s) — using fallback codes", exc)
        return list(_SIDO_CODES_FALLBACK)

    out: list[str] = []
    seen: set[str] = set()
    for feat in fc.get("features") or []:
        props = feat.get("properties") or {}
        code = str(props.get("ctprvn_cd") or props.get("ch2_code") or "").strip()
        if len(code) < 2:
            continue
        s2 = code[:2]
        if s2 in seen:
            continue
        seen.add(s2)
        out.append(s2)
    if len(out) < 10:
        _LOG.warning("sido list short (%d) — using fallback", len(out))
        return list(_SIDO_CODES_FALLBACK)
    # 신코드 보강
    for s2 in _SIDO_CODES_FALLBACK:
        if s2 not in seen:
            out.append(s2)
    return sorted(set(out))


def build_edges(
    features: list[dict],
    *,
    level: str = "eupmyeondong",
    buffer_m_deg: float = 0.00005,
) -> set[tuple[str, str]]:
    items: list[tuple[str, object]] = []
    for feat in features:
        code = _code_of(feat, level=level)
        geom = feat.get("geometry")
        if not code or not geom:
            continue
        try:
            g = shape(geom)
            if g.is_empty:
                continue
            if not g.is_valid:
                g = g.buffer(0)
            items.append((code, g))
        except Exception as exc:
            _LOG.warning("skip geom %s: %s", code, exc)

    edges: set[tuple[str, str]] = set()
    n = len(items)
    for i in range(n):
        ci, gi = items[i]
        gi_buf = gi.buffer(buffer_m_deg)
        for j in range(i + 1, n):
            cj, gj = items[j]
            if ci == cj:
                continue
            try:
                if gi_buf.intersects(gj) or gi.touches(gj) or gi.intersects(gj):
                    a, b = (ci, cj) if ci < cj else (cj, ci)
                    edges.add((a, b))
            except Exception:
                continue
    return edges


def upsert_edges(engine, *, level: str, edges: set[tuple[str, str]], replace_codes: set[str] | None):
    pairs: list[dict] = []
    for a, b in edges:
        pairs.append({"level": level, "code": a, "neighbor": b})
        pairs.append({"level": level, "code": b, "neighbor": a})

    with engine.begin() as conn:
        if replace_codes:
            codes_list = sorted(replace_codes)
            # expanding IN 은 대량일 때 청크
            chunk = 500
            for i in range(0, len(codes_list), chunk):
                part = codes_list[i : i + chunk]
                conn.execute(
                    text(
                        """
                        DELETE FROM region_neighbors
                        WHERE level = :level
                          AND (code IN :codes OR neighbor_code IN :codes)
                        """
                    ).bindparams(bindparam("codes", expanding=True)),
                    {"level": level, "codes": part},
                )
        if pairs:
            conn.execute(
                text(
                    """
                    INSERT INTO region_neighbors (level, code, neighbor_code)
                    VALUES (:level, :code, :neighbor)
                    ON CONFLICT DO NOTHING
                    """
                ),
                pairs,
            )
    _LOG.info("upserted directed edges~%d (undirected=%d)", len(pairs), len(edges))


def ensure_region_neighbors_table(engine) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS region_neighbors (
        level TEXT NOT NULL,
        code TEXT NOT NULL,
        neighbor_code TEXT NOT NULL,
        PRIMARY KEY (level, code, neighbor_code),
        CONSTRAINT region_neighbors_level_chk
            CHECK (level IN ('eupmyeondong', 'beopjungri')),
        CONSTRAINT region_neighbors_neq_chk
            CHECK (code <> neighbor_code)
    );
    """
    idx1 = "CREATE INDEX IF NOT EXISTS idx_region_neighbors_code ON region_neighbors (level, code);"
    idx2 = (
        "CREATE INDEX IF NOT EXISTS idx_region_neighbors_neighbor "
        "ON region_neighbors (level, neighbor_code);"
    )
    with engine.begin() as conn:
        conn.execute(text(ddl))
        conn.execute(text(idx1))
        conn.execute(text(idx2))


def sigungu_already_built(engine, *, level: str, sig5: str) -> bool:
    """시군구 그래프가 카탈로그 대비 충분히 채워졌으면 skip.

    링 빌드만 타고 코드 몇 개만 있는 경우(세종 36110 등)는 재빌드한다.
    """
    pref = f"{sig5}%"
    with engine.connect() as conn:
        n_graph = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT code) FROM region_neighbors
                WHERE level = :level
                  AND code LIKE :pref
                """
            ),
            {"level": level, "pref": pref},
        ).scalar()
        if level == "beopjungri":
            n_cat = conn.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT TRIM(beopjungri_code))
                    FROM region_codes
                    WHERE beopjungri_code IS NOT NULL
                      AND LENGTH(TRIM(beopjungri_code)) >= 10
                      AND RIGHT(TRIM(beopjungri_code), 2) <> '00'
                      AND LEFT(TRIM(beopjungri_code), 5) = :sig5
                    """
                ),
                {"sig5": sig5},
            ).scalar()
        else:
            n_cat = conn.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT TRIM(eupmyeondong_code))
                    FROM region_codes
                    WHERE eupmyeondong_code IS NOT NULL
                      AND LENGTH(TRIM(eupmyeondong_code)) >= 8
                      AND LEFT(TRIM(eupmyeondong_code), 5) = :sig5
                    """
                ),
                {"sig5": sig5},
            ).scalar()
    graph_n = int(n_graph or 0)
    cat_n = int(n_cat or 0)
    if cat_n <= 0:
        return graph_n > 0
    return graph_n >= max(1, int(0.8 * cat_n))


def build_one_sigungu(
    engine,
    *,
    api_key: str,
    domain: str,
    level: str,
    sig5: str,
) -> tuple[int, int]:
    """Returns (feature_count, undirected_edge_count)."""
    if level == "beopjungri":
        core = fetch_ri_for_sigungu(api_key, domain, sig5)
        code_level = "beopjungri"
    else:
        core = fetch_emd_for_sigungu(api_key, domain, sig5)
        code_level = "eupmyeondong"

    primary_codes = {c for c in (_code_of(f, level=code_level) for f in core) if c}
    if not primary_codes:
        _LOG.warning("sigungu=%s level=%s no features", sig5, level)
        return 0, 0
    bbox = bbox_from_features(core)
    ring: list[dict] = []
    if bbox:
        if level == "beopjungri":
            ring = fetch_ri_near_bbox(api_key, domain, bbox, pad_deg=0.04)
        else:
            ring = fetch_emd_near_bbox(api_key, domain, bbox, pad_deg=0.04)
    features = merge_features_by_code(core, ring, level=code_level)
    edges = build_edges(features, level=code_level)
    edges = {(a, b) for a, b in edges if a in primary_codes or b in primary_codes}
    upsert_edges(engine, level=level, edges=edges, replace_codes=primary_codes)
    return len(features), len(edges)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build region_neighbors from VWorld")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--sigungu", help="5자리 시군구 코드 (예: 43113)")
    g.add_argument("--sido", help="2자리 시도 코드 (예: 43)")
    g.add_argument("--all", action="store_true", help="전국 시군구 순회 빌드")
    parser.add_argument(
        "--level",
        default="eupmyeondong",
        choices=["eupmyeondong", "beopjungri"],
        help="eupmyeondong=읍면동, beopjungri=리",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="이미 edge가 있는 시군구는 건너뜀 (재개용)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="시군구 사이 VWorld 부하 완화 대기(초)",
    )
    args = parser.parse_args()

    api_key, domain = _vworld_creds()
    engine = create_engine(_database_url())
    ensure_region_neighbors_table(engine)

    if args.sigungu:
        sig_list = [args.sigungu.strip()[:5]]
    elif args.sido:
        sido = args.sido.strip()[:2]
        _LOG.info("listing sigungu for sido=%s", sido)
        sig_list = list_sigungu_codes(api_key, domain, sido)
    else:
        _LOG.info("listing all sigungu for national build level=%s", args.level)
        sig_list = list_sigungu_from_db(engine, level=args.level)
        if len(sig_list) < 20:
            _LOG.warning(
                "DB sigungu list short (%d) — falling back to VWorld by sido",
                len(sig_list),
            )
            sidos = list_all_sido_codes(api_key, domain)
            _LOG.info("sido codes=%s", ",".join(sidos))
            sig_list = []
            for s2 in sidos:
                try:
                    part = list_sigungu_codes(api_key, domain, s2)
                    _LOG.info("sido=%s sigungu=%d", s2, len(part))
                    sig_list.extend(part)
                except Exception as exc:
                    _LOG.warning("sido=%s list failed: %s", s2, exc)
                time.sleep(args.sleep)
            sig_list = sorted(set(sig_list))
        else:
            _LOG.info("sigungu from region_codes=%d", len(sig_list))

    _LOG.info("target sigungu count=%d level=%s", len(sig_list), args.level)
    ok = 0
    skipped = 0
    failed = 0
    total_edges = 0
    t0 = time.time()

    for i, sig5 in enumerate(sig_list, start=1):
        try:
            if args.skip_existing and sigungu_already_built(engine, level=args.level, sig5=sig5):
                skipped += 1
                _LOG.info("[%d/%d] skip existing sigungu=%s", i, len(sig_list), sig5)
                continue
            _LOG.info("[%d/%d] building sigungu=%s", i, len(sig_list), sig5)
            _nfeat, nedge = build_one_sigungu(
                engine,
                api_key=api_key,
                domain=domain,
                level=args.level,
                sig5=sig5,
            )
            ok += 1
            total_edges += nedge
            _LOG.info(
                "[%d/%d] done sigungu=%s features~%d edges=%d",
                i,
                len(sig_list),
                sig5,
                _nfeat,
                nedge,
            )
        except Exception as exc:
            failed += 1
            _LOG.exception("[%d/%d] FAILED sigungu=%s: %s", i, len(sig_list), sig5, exc)
        if args.sleep > 0:
            time.sleep(args.sleep)

    elapsed = time.time() - t0
    with engine.connect() as conn:
        db_n = conn.execute(text("SELECT COUNT(*) FROM region_neighbors")).scalar()
    _LOG.info(
        "FINISHED ok=%d skipped=%d failed=%d pass_edges~%d db_directed=%s elapsed=%.1fs",
        ok,
        skipped,
        failed,
        total_edges,
        db_n,
        elapsed,
    )


if __name__ == "__main__":
    main()
