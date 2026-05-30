# 0. 프로젝트 구조 분석 (배포 관점)

CH2 Macro dev VPS 배포에 필요한 코드·설정·데이터 경로를 정리합니다.

---

## 1. 레포 디렉터리 구조

```
ch2_Macro/
├── backend/              # FastAPI (배포 대상)
│   ├── app/
│   │   ├── main.py       # 진입점, CORS, API_TOKEN, /health
│   │   ├── config.py     # pydantic-settings → backend/.env
│   │   ├── db.py
│   │   └── routers/      # free, free_v2, paid, upper_stats, twin_regions
│   ├── requirements.txt
│   ├── Dockerfile        # 로컬 docker-compose용 (--reload). VPS는 systemd 권장
│   └── .env              # 배포 시 secrets (Git 제외)
├── frontend/             # React + Vite (빌드 산출물만 Nginx 서빙)
│   ├── src/api/client.ts # baseURL="/api", VITE_API_TOKEN
│   ├── vite.config.ts    # dev proxy → localhost:8000 (프로덕션은 Nginx가 대체)
│   └── .env              # VITE_* 빌드 시 주입 (Git 제외)
├── db/                   # SQL 마이그레이션 (신규 DB만 순서 적용; 이전은 dump로 대체)
├── pipeline/             # 로컬 전용 (VPS에 clone은 해도 실행은 로컬)
├── docker-compose.yml    # 로컬 개발용 3-tier. VPS 런타임에는 미사용
└── deploy/               # 본 배포 문서·템플릿
```

---

## 2. Backend 구조

| 구성 | 설명 |
|------|------|
| **프레임워크** | FastAPI + Uvicorn |
| **DB** | SQLAlchemy + psycopg2 → `DATABASE_URL` |
| **라우터** | `/api/free/v2/*`, `/api/paid/*`, `/api/upper/*`, `/api/twin/*` 등 |
| **헬스** | `GET /health` → `{ status, latest_as_of_month }` (API_TOKEN 불필요) |
| **인증** | `API_TOKEN` env → `X-Api-Token` 헤더 (D-007). 비어 있으면 비활성 |
| **CORS** | `CORS_ORIGINS` 쉼표 구분 (HTTPS origin 필수) |

**프로덕션 실행 명령 (VPS):**

```bash
cd /opt/ch2_Macro/backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

- `--reload` 사용 금지 (dev 전용)
- 4 GB RAM → **workers 1** 권장 (유료 쿼리 시 메모리 피크)

---

## 3. Frontend 구조

| 구성 | 설명 |
|------|------|
| **빌드** | `npm run build` → `frontend/dist/` |
| **API 호출** | axios `baseURL: "/api"` — **같은 도메인**에서 Nginx가 `/api` → 백엔드 프록시 |
| **토큰** | `VITE_API_TOKEN` → 빌드 시 번들에 포함 (`client.ts`) |
| **dev proxy** | `vite.config.ts`의 proxy는 **Vite dev 전용**. VPS에서는 Nginx 사용 |

**프로덕션 빌드:**

```bash
cd /opt/ch2_Macro/frontend
cp .env.production .env   # 또는 export VITE_API_TOKEN=...
npm ci
npm run build
# dist/ → Nginx root
```

---

## 4. 환경변수 정리

### 4.1 Backend (`backend/.env`)

| 변수 | 필수 | dev VPS 예시 | 비고 |
|------|------|--------------|------|
| `DATABASE_URL` | ✅ | `postgresql+psycopg2://ch2app:***@127.0.0.1:5432/land_stats` | localhost만 |
| `CORS_ORIGINS` | ✅ | `https://dev-macro.example.com` | 쉼표로 복수 가능 |
| `API_TOKEN` | ✅ (dev VPS) | `openssl rand -hex 32` | `/health` 제외 |
| `SECRET_KEY` | ✅ | 랜덤 문자열 | JWT 등 향후용 |
| `STATS_V2_DEFAULT_AS_OF_MONTH` | 권장 | `2025-12-01` | 로컬 DB 최신 스냅샷과 일치 |
| `STATS_V2_ASSUMED_TODAY` | ❌ | 비움 | 검증용만 |
| `paid_analyze_work_mem_mb` | 선택 | `128`~`192` | 4GB면 128부터 |

템플릿: [`templates/backend.env.production.example`](./templates/backend.env.production.example)

### 4.2 Frontend (`frontend/.env` — **빌드 시점**)

| 변수 | 필수 | dev VPS |
|------|------|---------|
| `VITE_API_TOKEN` | ✅ | backend `API_TOKEN`과 **동일** |
| `VITE_STATS_V2_ASSUMED_TODAY` | ❌ | 비움 (운영) |

템플릿: [`templates/frontend.env.production.example`](./templates/frontend.env.production.example)

### 4.3 Pipeline (로컬만, VPS 불필요)

| 변수 | 용도 |
|------|------|
| `DATABASE_URL` | 로컬 PostgreSQL (배치·Promote 전 검증) |
| `STATS_V2_*` | `build_stats_v2.py` |

월간 갱신 후 VPS 반영: [`03-data-migration.md`](./03-data-migration.md) Promote 절차.

---

## 5. DB 스키마·마이그레이션

**데이터 이전 방식:** 로컬 `pg_dump -Fc` → VPS `pg_restore` (**권장**).  
빈 DB에 SQL을 처음부터 돌릴 필요 없음.

신규 빈 DB만 수동 적용 시 순서 (`db/`):

```
001_init.sql
002_indexes.sql
002_paid_analyze_index.sql   # 유료 분석 속도
003_legacy_patch.sql         # (레거시 DB만)
004_add_basic_stats_std.sql
005_road_condition_labels.sql
006_land_tx_raw_id_index.sql
007_land_basic_stats_v2.sql
008_land_transactions_v2_batch_index.sql
009_land_transactions_mapping_review.sql
010_land_upper_stats_v2.sql
011_land_transactions_display_columns.sql
012_twin_region_neighbor_mvp.sql
013_twin_eupmyeondong_neighbor_mvp.sql
```

---

## 6. 배포 시 필요한 파일·디렉터리

### Git에서 가져오는 것

| 경로 | 용도 |
|------|------|
| `backend/` 전체 | FastAPI (`.env` 제외) |
| `frontend/` 전체 | `npm run build` (`node_modules`, `dist` 제외) |
| `db/` | 참고·신규 DB용 (dump 이전 시 선택) |
| `deploy/` | 본 문서·템플릿·스크립트 |

### Git에 없고 서버·로컬에만 두는 것

| 항목 | 위치 |
|------|------|
| `backend/.env` | VPS `/opt/ch2_Macro/backend/.env` |
| `frontend/.env` | VPS 빌드 전 1회 (또는 `.env.production`) |
| PostgreSQL 데이터 | VPS `/var/lib/postgresql/16/main/` |
| TLS 인증서 | `/etc/letsencrypt/` |
| DB 덤프 | 로컬 → SCP → VPS `/var/backups/ch2/` |

### VPS에 두지 않아도 되는 것

| 경로 | 이유 |
|------|------|
| `pipeline/` 실행 | Selenium·대용량 배치는 로컬 |
| `raw/`, `*.xlsx` | 수집 원본 |
| `docker-compose.yml` 런타임 | 4GB RAM — systemd가 단순 |

---

## 7. Docker 사용 여부 (판단)

| 옵션 | dev VPS 4GB | 결론 |
|------|-------------|------|
| **docker-compose 3-tier** | RAM·디스크 오버헤드 | ❌ 비권장 |
| **PostgreSQL만 Docker** | 가능하나 튜닝·백업 복잡 | △ |
| **systemd + apt PostgreSQL** | 단순, `pg_restore` 표준 | ✅ **권장** |

레포의 `docker-compose.yml`·`backend/Dockerfile`은 **로컬 개발**용으로 유지합니다.

---

## 8. API 엔드포인트 (검증용)

| 기능 | 예시 |
|------|------|
| 헬스 | `GET /health` |
| 지역 목록 | `GET /api/free/regions?limit=10` |
| 무료 V2 | `GET /api/free/v2/stats/{code}?window_years=3` |
| 유료 필터 | `POST /api/paid/analyze` |
| 상위 통계 | `GET /api/upper/v2/stats/...` |
| 쌍둥이 시군구 | `GET /api/twin/regions/sigungu/{code}/neighbors` |
| 쌍둥이 읍면동 | `GET /api/twin/regions/eupmyeondong/{code}/neighbors` |

OpenAPI: `https://<도메인>/docs` (API_TOKEN 없이 문서만 — 실제 API 호출은 토큰 필요)
