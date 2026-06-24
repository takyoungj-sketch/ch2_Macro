# CH2_MACRO 시스템 아키텍처

> 최종 업데이트: 2026-06-24  
> 대상: 새로운 개발자·AI가 저장소만 읽어도 전체 구조를 이해할 수 있도록 작성.

---

## 1. 시스템 개요

CH2_MACRO는 **국토부 실거래 데이터를 수집·정제·집계하여 감정평가사에게 토지 거래 통계를 제공**하는 웹 서비스다.

| 항목 | 내용 |
|------|------|
| 주 사용자 | 감정평가사 (법인·개인) |
| 데이터 원천 | 국토부 실거래가 공개 시스템 (토지·복합부동산·집합건물) |
| 갱신 주기 | 월 1~5일 (직전 월 말 기준) |
| 배포 환경 | AWS Lightsail VPS (Nginx + FastAPI systemd) |
| 로컬 개발 | Windows PC (PostgreSQL 18 로컬) |

---

## 2. 전체 레이어 구조

```
┌──────────────────────────────────────────────────────┐
│                  Frontend (React 3종)                │
│  토지(:5173)  ·  복합부동산(:5174)  ·  집합(:5175)   │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP /api/*
┌──────────────────▼───────────────────────────────────┐
│             Backend (FastAPI, port 8000)             │
│  free_v2 · paid · upper_stats · built · collective   │
│  collective_commercial · regional_profile · twin_v8  │
└──────────────────┬───────────────────────────────────┘
                   │ SQLAlchemy
┌──────────────────▼───────────────────────────────────┐
│                  PostgreSQL 18                       │
│                                                      │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │   land_stats    │  │ built_stats  │  │collecti │ │
│  │  (토지 원장     │  │ (복합부동산) │  │ve_stats │ │
│  │   + 사전집계)   │  │              │  │ (집합)  │ │
│  └─────────────────┘  └──────────────┘  └─────────┘ │
└──────────────────────────────────────────────────────┘
          ▲
          │ pg_dump / pg_restore (Promote)
┌─────────┴────────────────────────────────────────────┐
│              Pipeline (Python, 로컬 실행)            │
│  collect → clean → dedupe → build_stats_v2          │
│  → build_upper_stats_v2 → twin/profile 빌드          │
└──────────────────────────────────────────────────────┘
          ▲
          │ xlsx / CSV
┌─────────┴────────────────────────────────────────────┐
│           Raw Data (국토부 MOLIT 엑셀/CSV)           │
└──────────────────────────────────────────────────────┘
```

---

## 3. 도메인별 DB 분리

| DB | 주요 테이블 | 담당 API |
|----|------------|---------|
| `land_stats` | `land_transactions`, `land_basic_stats_v2`, `land_upper_stats_v2`, `twin_neighbor_v8`, `regional_profile`, `analysis_cache` | `/api/free/v2`, `/api/paid`, `/api/twin-v8`, `/api/regional-profile` |
| `built_stats` | `built_transactions`, `built_scope_stats`, `region_codes` (복사본) | `/api/built` |
| `collective_stats` | `collective_transactions`, `collective_building_stats`, `market_stats`, `commercial_clusters`, `collective_commercial_transactions` | `/api/collective`, `/api/commercial` |

> **주의:** `region_codes`는 `land_stats`가 SSOT. `built_stats`·`collective_stats`는 land에서 복사.

---

## 4. 백엔드 구조

```
backend/
├── app/
│   ├── main.py            # FastAPI app, 라우터 마운트, /health
│   ├── db.py              # land_stats SessionLocal
│   ├── analysis_base_cache.py  # row_ids 캐시 (4h TTL)
│   ├── routers/
│   │   ├── free_v2.py     # GET /api/free/v2/stats/{code}  (무료)
│   │   ├── paid.py        # POST /api/paid/analyze  (유료 동적 집계)
│   │   ├── upper_stats.py # GET /api/paid/upper-stats/{level}/{code}
│   │   ├── twin_regions.py# GET /api/twin-regions/*  (MVP/Hybrid)
│   │   ├── twin_v8.py     # GET /api/twin-v8/*  (v8 신규)
│   │   └── free.py        # DEPRECATED: V1 라우터
│   ├── built/             # /api/built/* (복합부동산)
│   ├── collective/        # /api/collective/* (집합)
│   ├── collective_commercial/ # /api/commercial/*
│   └── regional_profile/  # /api/regional-profile/*
└── scripts/
    └── clear_analysis_cache.py
```

**조건부 활성:** `BUILT_DATABASE_URL` / `COLLECTIVE_DATABASE_URL` 환경변수가 있을 때만 해당 라우터 마운트.

---

## 5. 파이프라인 구조

```
pipeline/
├── collect.py             # 국토부 API/엑셀 → land_transactions_raw
├── clean.py               # raw → land_transactions (UPSERT, hash dedupe)
├── transaction_hash.py    # 거래 hash SSOT (순번 미포함 semantic hash)
├── dedupe_land_transactions.py  # 중복 행 제거 + rehash (--rehash-only)
├── build_stats_v2.py      # → land_basic_stats_v2
├── build_upper_stats_v2.py# → land_upper_stats_v2
├── build_annual_stats.py  # → land_annual_stats (장기 추세)
├── build_twin_v8.py       # → twin_neighbor_v8 (충청권 현재, 전국 예정)
├── build_regional_profile.py  # market_stats → regional_profile
├── run_pipeline.py        # collect→clean→build 오케스트레이터
├── rehearse_v2_update.py  # 읽기 전용 환경 점검
├── verify_monthly_integrity.py # L1/L2 정합성 게이트
├── twin_v8/               # Twin v8 모듈 (loaders, scoring)
├── built/                 # 복합부동산 수집·적재
└── collective/            # 집합 주거 수집·적재
```

---

## 6. 프론트엔드 구조

세 개의 독립 Vite 앱이 각각 다른 포트에서 실행:

| 앱 | 경로 | 기본 포트 | 주요 기능 |
|----|------|-----------|-----------|
| 토지 | `frontend/` | 5173 | 토지 통계, 유료 필터, 쌍둥이 찾기, Regional Profile |
| 복합부동산 | `frontend-built/` | 5174 | 상업·공장·단독 통계, 회귀 |
| 집합부동산 | `frontend-collective/` | 5175 | 아파트·상가·연립 통계, 코호트 회귀 |

모두 `proxy: { '/api': 'http://127.0.0.1:8000' }` 설정으로 동일 백엔드를 공유.

---

## 7. 배포 구조

```
로컬 PC
  └─ run_monthly_cycle.py (수집·정제·집계)
  └─ pg_dump -Fc land_stats.dump
       │
       │ SCP/rsync
       ▼
AWS Lightsail VPS (Ubuntu)
  ├─ PostgreSQL 18  (pg_restore)
  ├─ FastAPI (systemd: ch2macro.service)
  ├─ Nginx (HTTPS, /api → 8000, /land/ → 빌드 dist)
  └─ 3종 프론트 (npm build → /var/www/ch2macro/*)
```

**배포 절차:** `deploy/` 폴더 내 `00-*.md`~`09-*.md` 참조.  
**Promote:** 로컬에서 검증 완료 후 `pg_dump` → VPS `pg_restore` → 서비스 재시작.

---

## 8. 핵심 설계 결정 요약

| 결정 | 내용 | 문서 |
|------|------|------|
| D-001 | V2 `as_of_month` 단일화 (V1 폐기) | `DECISIONS.md` |
| D-002 | SLA: 월 1~5일 갱신, 「YYYY년 M월 말 기준」 표시 | `DECISIONS.md` |
| D-007 | `API_TOKEN` 옵트인 보호 | `DECISIONS.md` |
| D-012 | `transaction_hash` semantic hash (순번 미포함) | `TRANSACTION_HASH_DEDUPE.md` |
| D-016 | Regional Profile 5-Layer 통계 아키텍처 | `REGIONAL_PROFILE_ARCHITECTURE.md` |
| D-023b | Twin Hybrid v2 (토지·집합·Profile 가중치 블렌딩) | `PROFILE_TWIN_HYBRID.md` |

---

## 9. 관련 문서

| 문서 | 내용 |
|------|------|
| `README.md` | 빠른 시작, DB 구조 요약 |
| `DECISIONS.md` | 전체 설계 결정 이력 (D-001~D-024b) |
| `NEXT_STEPS.md` | 현재 진행 중·백로그 |
| `docs/DATA_FLOW.md` | 데이터 흐름 상세 |
| `docs/DATABASE_SCHEMA.md` | 테이블·컬럼 상세 |
| `docs/MONTHLY_UPDATE_PIPELINE.md` | 월간 갱신 단계별 가이드 |
| `docs/DATA_INTEGRITY_CHECKLIST.md` | 무결성 검증 체크리스트 |
| `docs/RISK_REGISTER.md` | 위험 요소 레지스터 |
| `docs/ARCHITECTURE_REVIEW_REPORT.md` | 아키텍처 비판적 검토 |
| `docs/MONTHLY_UPDATE_SOP.md` | 운영 SOP (상세 절차) |
| `docs/V2_STATS_DESIGN.md` | V2 통계 설계 |
| `docs/TWIN_V8_DESIGN.md` | Twin v8 알고리즘 설계 |
