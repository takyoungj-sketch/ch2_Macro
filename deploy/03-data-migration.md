# 3. 데이터 이전 전략 (pg_dump / pg_restore)

로컬 PC(Windows) → Lightsail VPS. 배치는 로컬, **검증된 DB만 Promote**.

---

## 3.1 전략 요약

| 단계 | 위치 | 작업 |
|------|------|------|
| 1 | 로컬 | 월간/수시 pipeline 실행·검증 |
| 2 | 로컬 | `pg_dump -Fc` |
| 3 | 네트워크 | SCP / rsync → VPS `/var/backups/ch2/` |
| 4 | VPS | `pg_restore` → `land_stats` |
| 5 | VPS | 백엔드 재시작, `/health`·샘플 API 검증 |

**Managed DB·논리 복제 없음.** dev/test는 **전체 덤프 교체**가 단순합니다.

---

## 3.2 로컬 PC — 덤프 생성 (Windows)

### pg_dump 경로

PostgreSQL 설치 경로 예:

```
"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
```

또는 backend venv만 있고 CLI가 없으면 PostgreSQL **클라이언트 도구** 설치.

### 덤프 명령

```powershell
$env:PGPASSWORD = "로컬_postgres_비밀번호"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$out = "F:\ch2_Macro\backups\land_stats_$ts.dump"   # USB F: 가능

& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" `
  -h localhost -U postgres -d land_stats `
  -Fc --no-owner --no-acl `
  -f $out

Get-Item $out | Select-Object Name, @{N='GB';E={[math]::Round($_.Length/1GB,2)}}
```

| 옵션 | 이유 |
|------|------|
| `-Fc` | 압축 custom format (~2–4 GB 예상) |
| `--no-owner --no-acl` | VPS `ch2app` 사용자와 호환 |

- [ ] 덤프 파일 크기 기록
- [ ] Promote 직전 로컬 `/health` 또는 `MAX(as_of_month)` 기록

---

## 3.3 VPS로 전송

```powershell
scp -i $env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem `
  F:\ch2_Macro\backups\land_stats_20260529.dump `
  ubuntu@DEV_PUBLIC_IP:/var/backups/ch2/
```

대용량·불안정 �etwork: `rsync -P` (WSL/Git Bash).

---

## 3.4 VPS — 복원

### A. 기존 DB 덮어쓰기 (dev Promote 표준)

```bash
export PGPASSWORD='CHANGE_ME_STRONG_PASSWORD'
DUMP=/var/backups/ch2/land_stats_20260529.dump

# 연결 끊기
sudo systemctl stop ch2-macro-backend

# DB 재생성 (주의: 전체 삭제)
sudo -u postgres psql <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'land_stats';
DROP DATABASE IF EXISTS land_stats;
CREATE DATABASE land_stats OWNER ch2app;
SQL

pg_restore -h 127.0.0.1 -U ch2app -d land_stats \
  --no-owner --no-acl --role=ch2app \
  "$DUMP" 2>&1 | tee /var/backups/ch2/restore.log
# pg_restore는 경고(warning)가 있어도 완료되는 경우 많음 — exit code 확인

sudo systemctl start ch2-macro-backend
```

### B. 최초 1회 (빈 DB)

[02-server-build-checklist.md](./02-server-build-checklist.md)에서 DB 생성 후 동일 `pg_restore`.

---

## 3.5 복구 검증

### 5.1 행 수·용량

```bash
psql "postgresql://ch2app:***@127.0.0.1/land_stats" <<'SQL'
SELECT pg_size_pretty(pg_database_size('land_stats'));
SELECT 'land_transactions' t, COUNT(*) FROM land_transactions
UNION ALL SELECT 'land_transactions_raw', COUNT(*) FROM land_transactions_raw
UNION ALL SELECT 'land_basic_stats_v2', COUNT(*) FROM land_basic_stats_v2
UNION ALL SELECT 'land_upper_stats_v2', COUNT(*) FROM land_upper_stats_v2;
SELECT MAX(as_of_month) FROM land_basic_stats_v2;
SQL
```

**기대 (2026-05 로컬 기준 참고):**

| 항목 | 대략 |
|------|------|
| DB 크기 | ~7 GB |
| land_transactions | ~307만 |
| land_basic_stats_v2 | ~271만 |

- [ ] 로컬과 `COUNT(*)`·`MAX(as_of_month)` 일치

### 5.2 API

```bash
curl -sS http://127.0.0.1:8000/health | jq .
curl -sS -H "X-Api-Token: YOUR_TOKEN" \
  "http://127.0.0.1:8000/api/free/regions?limit=3"
```

### 5.3 프론트

브라우저 → `https://dev-macro...` → 지역 선택·통계·필터·쌍둥이

→ 상세: [07-verification-checklist.md](./07-verification-checklist.md)

---

## 3.6 월간 Promote (로컬 → VPS)

`docs/MONTHLY_UPDATE_SOP.md` §9 **안 A** 와 동일:

1. 로컬: `run_monthly_cycle.py` + 검증
2. 로컬: `pg_dump -Fc` → 백업 보관
3. VPS: §3.4 restore
4. VPS: `backend/.env`의 `STATS_V2_DEFAULT_AS_OF_MONTH` 갱신
5. `sudo systemctl restart ch2-macro-backend`
6. 프론트 재빌드는 env 변경 시만

---

## 3.7 디스크 여유 확인

80 GB SSD 기준:

```
DB ~7 GB + 덤프 ~3 GB + WAL/로그 ~5 GB + OS ~10 GB ≈ 25 GB
```

- [ ] `df -h` 사용률 **70% 미만** 유지
- [ ] 오래된 �ump는 `/var/backups/ch2/`에서 주기 삭제

---

## 3.8 실패 시

→ [06-recovery.md](./06-recovery.md)
