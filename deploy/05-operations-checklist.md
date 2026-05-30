# 5. 운영 체크리스트

dev/test VPS 일상·월간 운영. 정식 SLA·24/7 온콜은 **범위 외**.

---

## 5.1 일상 (주 1회 또는 배포 후)

| # | 항목 | 명령/방법 |
|---|------|-----------|
| 1 | 서비스 생존 | `curl -sS https://dev-macro.../health` |
| 2 | 디스크 | `df -h /` — **70% 미만** |
| 3 | 메모리 | `free -h` — available 500MB+ |
| 4 | 백엔드 로그 | `journalctl -u ch2-macro-backend --since "24 hours ago" \| tail -50` |
| 5 | Nginx 로그 | `sudo tail -20 /var/log/nginx/error.log` |
| 6 | PostgreSQL | `sudo systemctl status postgresql` |

스크립트: [`scripts/health-check.sh`](./scripts/health-check.sh)

---

## 5.2 배포 후 (git pull)

- [ ] `redeploy.sh` 실행
- [ ] `/health` → `latest_as_of_month` 기대값
- [ ] 브라우저: 무료·유료·쌍둥이 스모크
- [ ] `journalctl` 에 traceback 없음

---

## 5.3 월간 데이터 갱신 (로컬 pipeline → VPS Promote)

**로컬 PC:**

1. [ ] `docs/V2_OPERATOR_CHECKLIST.md` §B0 리허설
2. [ ] `scripts/monthly/run_monthly_cycle.py --cycle-id YYYYMM`
3. [ ] 검증·샘플 API
4. [ ] `pg_dump -Fc` → 파일명에 cycle_id

**VPS:**

5. [ ] Promote 전 Lightsail **스냅샷** 또는 `/var/backups/ch2/` 덤프 보관
6. [ ] [03-data-migration.md](./03-data-migration.md) restore
7. [ ] `STATS_V2_DEFAULT_AS_OF_MONTH` 갱신
8. [ ] `systemctl restart ch2-macro-backend`
9. [ ] UI 「YYYY년 M월 말 기준」 확인

---

## 5.4 백업 정책 (dev)

| 대상 | 주기 | 보관 |
|------|------|------|
| `pg_dump` Promote 직전 | 월간 | 로컬 + VPS `/var/backups/ch2/` 최근 2개 |
| Lightsail snapshot | 월 1회 (선택) | 1개 |
| `backend/.env` | 변경 시 | 비밀번호 관리자에만 |

---

## 5.5 비용·리소스

| 신호 | 조치 |
|------|------|
| OOM / 유료 쿼리 kill | 8 GB 플랜 업그레이드 또는 `paid_analyze_work_mem_mb` ↓ |
| 디스크 80%+ | 옛 dump 삭제, V1 backup 테이블 정리 검토 |
| 장기 미사용 | 인스턴스 stop (Static IP 비용 주의) |

---

## 5.6 정식 서비스 전환 준비 (나중)

dev에서 **2회 이상** 성공해야 할 것:

- [ ] Promote (dump → restore) 무사히
- [ ] HTTPS + API_TOKEN + CORS
- [ ] 롤백 1회 연습 ([06-recovery.md](./06-recovery.md))
- [ ] redeploy.sh로 코드만 배포

정식: **새 VM** 또는 스펙 업, Managed DB는 그때 검토.

---

## 5.7 접속 정보 (팀 1인이어도 기록)

| 항목 | 값 |
|------|-----|
| Static IP | |
| 도메인 | |
| SSH 키 위치 | |
| API_TOKEN 보관 | |
| DB ch2app 비밀번호 | |

→ 비밀번호 관리자(1Password 등)에만 저장, Git 금지.
