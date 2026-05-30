# 6. 장애 발생 시 복구 절차

dev/test VPS. **RTO 목표 없음** — 단순·재현 가능 우선.

---

## 6.1 증상별 빠른 진단

| 증상 | 1차 확인 |
|------|----------|
| 사이트 전체 502/504 | `systemctl status ch2-macro-backend nginx postgresql` |
| API 401 | `VITE_API_TOKEN` 빌드 vs `API_TOKEN` 불일치 → frontend rebuild |
| API 500 | `journalctl -u ch2-macro-backend -n 100` |
| CORS 오류 | `CORS_ORIGINS` HTTPS origin 정확히 |
| 느림/OOM | `free -h`, `dmesg \| grep -i kill` |
| DB 연결 실패 | `psql` 로컬, `DATABASE_URL` 비밀번호 |
| HTTPS 만료 | `sudo certbot renew` |

---

## 6.2 서비스 재시작 (무중단 실패 시)

```bash
sudo systemctl restart postgresql
sudo systemctl restart ch2-macro-backend
sudo systemctl reload nginx
curl -sS http://127.0.0.1:8000/health
```

---

## 6.3 앱만 롤백 (코드)

```bash
cd /opt/ch2_Macro
git log -5 --oneline
git checkout <이전_커밋>
/opt/ch2_Macro/deploy/scripts/redeploy.sh
```

또는 `git revert` 후 pull.

- [ ] `/health` 복구

---

## 6.4 DB 롤백 (Promote 실패·데이터 깨짐)

**전제:** Promote **직전** `pg_dump` 또는 Lightsail snapshot 존재.

### A. pg_dump 복원

```bash
sudo systemctl stop ch2-macro-backend
# 03-data-migration.md §3.4 와 동일 — 이전 dump 파일 사용
sudo systemctl start ch2-macro-backend
```

### B. Lightsail snapshot

1. Lightsail → Snapshots → 문제 인스턴스 스냅샷 선택
2. **Create new instance from snapshot** (또는 디스크 복원 절차)
3. Static IP 재연결
4. DNS TTL 확인

- [ ] `COUNT(*)`·`latest_as_of_month` Promote 전과 일치

---

## 6.5 디스크 full

```bash
df -h
du -sh /var/backups/ch2/* | sort -h
du -sh /var/log/*
sudo journalctl --vacuum-time=7d
# 오래된 dump 삭제
rm /var/backups/ch2/land_stats_OLD.dump
```

PostgreSQL 긴급 (주의):

```bash
sudo -u postgres vacuumdb --analyze land_stats
```

---

## 6.6 OOM (4 GB RAM)

증상: 백엔드 sudden death, `Out of memory` in dmesg.

**즉시:**

```bash
# backend service: workers 1 확인
sudo systemctl restart ch2-macro-backend
```

**완화:**

- `paid_analyze_work_mem_mb=128` in `.env`
- PostgreSQL `shared_buffers` 512MB 유지
- **근본:** Lightsail **8 GB** 업그레이드

---

## 6.7 SSL 인증서

```bash
sudo certbot certificates
sudo certbot renew
sudo systemctl reload nginx
```

실패 시: DNS A 레코드, 80 포트 개방 확인.

---

## 6.8 SSH 잠금 (fail2ban)

```bash
sudo fail2ban-client status sshd
# 본인 IP unblock 필요 시 fail2ban 설정 조정
```

---

## 6.9 완전 재구축 (최후)

1. 새 Lightsail 인스턴스 (또는 OS reinstall)
2. [02-server-build-checklist.md](./02-server-build-checklist.md) 처음부터
3. **최신 known-good dump** restore
4. `.env` 백업에서 복원
5. [07-verification-checklist.md](./07-verification-checklist.md)

---

## 6.10 에스컬레이션 메모 (1인 개발)

| 단계 | 기록 |
|------|------|
| 발생 시각 | |
| 마지막 변경 (git / Promote) | |
| 증상 | |
| 시도한 조치 | |
| 복구 dump/snapshot ID | |

→ `logs/incidents/` (로컬)에 짧게 남기기.
