# 7. 검증 체크리스트

dev VPS 이전·Promote·재배포 후 **전 항목** 확인.

**환경 변수:**

```bash
export BASE=https://dev-macro.YOURDOMAIN.com
export TOKEN=your_api_token
```

---

## 7.1 인프라

| # | 항목 | 확인 | OK |
|---|------|------|-----|
| 1 | HTTPS 자물쇠 | 브라우저 주소창 | [ ] |
| 2 | HTTP → HTTPS | `curl -I http://...` → 301 | [ ] |
| 3 | `/health` (토큰 불필요) | `curl $BASE/health` | [ ] |
| 4 | API 토큰 없음 → 401 | `curl -o /dev/null -w "%{http_code}" $BASE/api/free/regions?limit=1` → 401 | [ ] |
| 5 | PostgreSQL 외부 차단 | 외부 PC에서 `telnet IP 5432` 실패 | [ ] |
| 6 | Uvicorn 외부 차단 | `telnet IP 8000` 실패 | [ ] |
| 7 | 디스크 여유 | `df -h` < 70% | [ ] |

---

## 7.2 DB 연결

| # | 항목 | 기대 | OK |
|---|------|------|-----|
| 8 | DB 크기 | ~7 GB | [ ] |
| 9 | land_transactions | ~3,073,019 | [ ] |
| 10 | latest_as_of_month | 로컬과 동일 (예: 2025-12-01 또는 2026-04-01) | [ ] |

```bash
curl -sS $BASE/health | jq .
```

---

## 7.3 API 정상 동작

```bash
curl -sS -H "X-Api-Token: $TOKEN" "$BASE/api/free/regions?limit=5" | jq 'length'
```

| # | 엔드포인트 | OK |
|---|------------|-----|
| 11 | `GET /api/free/regions?limit=5` → 배열 | [ ] |
| 12 | `GET /api/free/v2/stats/{code}?window_years=3` | [ ] |
| 13 | `GET /health` → `status: ok` | [ ] |

샘플 법정동 코드: 로컬에서 쓰던 충북·서울 코드 1개.

---

## 7.4 CORS

| # | 항목 | OK |
|---|------|-----|
| 14 | 브라우저 DevTools → Network → API 요청 **CORS error 없음** | [ ] |
| 15 | `access-control-allow-origin` 헤더에 dev 도메인 | [ ] |

---

## 7.5 프론트 · UX (브라우저)

| # | 기능 | OK |
|---|------|-----|
| 16 | 메인 페이지 로드 | [ ] |
| 17 | 지역 검색·선택 | [ ] |
| 18 | **무료** V2 통계 표시 | [ ] |
| 19 | 우상단 「YYYY년 M월 말 기준」 | [ ] |
| 20 | **유료** 기본 통계 보기 | [ ] |
| 21 | **필터 분석 실행** (매트릭스) | [ ] |
| 22 | 연도별·매트릭스 모달 | [ ] |
| 23 | **쌍둥이 도시 찾기** (시군구/읍면동) | [ ] |
| 24 | 지도(있으면) 타일 로드 | [ ] |

---

## 7.6 다중 위치 접속

| # | 위치 | OK |
|---|------|-----|
| 25 | 집 PC 브라우저 | [ ] |
| 26 | 사무실 PC 브라우저 | [ ] |
| 27 | 노트북 (다른 네트워크) | [ ] |

동일 URL·동일 데이터 기준일.

---

## 7.7 성능 (체감)

| # | 항목 | OK |
|---|------|-----|
| 28 | 무료 통계 < 3s (대표 지역) | [ ] |
| 29 | 유료 필터 < 10s (복수 동·일반 필터) | [ ] |
| 30 | 4GB에서 OOM 없음 (필터 3회 연속) | [ ] |

느리거나 OOM → [06-recovery.md](./06-recovery.md) §6.6, 8GB 검토.

---

## 7.8 재배포 회귀

```bash
ssh ubuntu@DEV_IP '/opt/ch2_Macro/deploy/scripts/redeploy.sh'
```

| # | 항목 | OK |
|---|------|-----|
| 31 | redeploy 후 `/health` | [ ] |
| 32 | UI 정상 | [ ] |

---

## 7.9 서명

| | |
|---|---|
| 검증일 | |
| git commit | |
| dump 파일 | |
| latest_as_of_month | |
| 검증자 | |

---

## 7.10 자동 스모크

```bash
BASE=https://dev-macro.YOURDOMAIN.com TOKEN=xxx ./deploy/scripts/health-check.sh
```

로컬에서 repo clone 후 SSH로 VPS에서 실행해도 됨.
