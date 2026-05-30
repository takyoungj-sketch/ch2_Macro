# 4. 배포 체크리스트 (앱 · HTTPS · 보안 · 재배포)

---

## 4.1 배포 전 체크

- [ ] [02-server-build-checklist.md](./02-server-build-checklist.md) 완료
- [ ] [03-data-migration.md](./03-data-migration.md) restore·행 수 검증 완료
- [ ] dev 도메인 DNS → Static IP
- [ ] `backend/.env`·`frontend/.env` 작성 (토큰 일치)

---

## 4.2 Backend 기동

```bash
sudo systemctl start ch2-macro-backend
sudo systemctl status ch2-macro-backend
journalctl -u ch2-macro-backend -n 50 --no-pager
curl -sS http://127.0.0.1:8000/health
```

- [ ] `status: ok`
- [ ] `latest_as_of_month` 로컬과 동일
- [ ] 로그에 `API_TOKEN 보호 활성` 표시

---

## 4.3 Frontend 빌드·배치

```bash
cd /opt/ch2_Macro/frontend
npm ci
npm run build
sudo nginx -t && sudo systemctl reload nginx
```

Nginx `root` → `/opt/ch2_Macro/frontend/dist`

- [ ] `https://dev-macro.YOURDOMAIN.com/` HTML 로드
- [ ] 정적 asset 200 (개발자 도구 Network)

---

## 4.4 HTTPS (Let's Encrypt)

**전제:** `server_name` 도메인이 이 서버 IP를 가리킴.

```bash
sudo certbot --nginx -d dev-macro.YOURDOMAIN.com
# 이메일 입력, Terms 동의, HTTP→HTTPS redirect 권장
```

자동 갱신:

```bash
sudo certbot renew --dry-run
```

- [ ] 브라우저 자물쇠 정상
- [ ] HTTP → HTTPS 리다이렉트

---

## 4.5 Nginx Reverse Proxy

[`templates/nginx-ch2-macro.conf`](./templates/nginx-ch2-macro.conf) 핵심:

| 경로 | 대상 |
|------|------|
| `/` | `frontend/dist` (SPA: `try_files`) |
| `/api/` | `http://127.0.0.1:8000/api/` |
| `/health` | (선택) `http://127.0.0.1:8000/health` — 모니터용 |

- [ ] Uvicorn **127.0.0.1:8000** 만 리슨 (0.0.0.0 불필요)
- [ ] Lightsail·UFW에서 8000 미개방

---

## 4.6 보안 최소 설정

### API_TOKEN (D-007)

| 위치 | 값 |
|------|-----|
| `backend/.env` → `API_TOKEN` | `openssl rand -hex 32` |
| `frontend/.env` → `VITE_API_TOKEN` | **동일** → `npm run build` |

검증:

```bash
# 토큰 없음 → 401
curl -sS -o /dev/null -w "%{http_code}" https://dev-macro.YOURDOMAIN.com/api/free/regions?limit=1
# 401

# 토큰 있음 → 200
curl -sS -H "X-Api-Token: TOKEN" "https://dev-macro.YOURDOMAIN.com/api/free/regions?limit=1"
```

- [ ] `/health` 는 토큰 없이 200
- [ ] `/docs` 는 토큰 없이 접근 가능 (dev). **정식 서비스 전 IP 제한 검토**

### PostgreSQL

- [ ] `listen_addresses = 'localhost'`
- [ ] `pg_hba.conf` 로컬만
- [ ] Lightsail 5432 미개방

### UFW

- [ ] `22`, `80`, `443` 만 allow

### SSH

- [ ] 키 인증만, root 로그인 금지
- [ ] (선택) `AllowUsers ubuntu`

### Secrets

- [ ] `.env` chmod 600
- [ ] Git에 `.env` 미커밋

---

## 4.7 CORS

`backend/.env`:

```env
CORS_ORIGINS=https://dev-macro.YOURDOMAIN.com
```

여러 origin: 쉼표 구분, **끝 슬래시 없음**.

- [ ] 브라우저에서 API 호출 시 CORS 오류 없음
- [ ] `OPTIONS` preflight 성공

---

## 4.8 GitHub 기반 재배포

### 최초 clone (이미 했다면 skip)

```bash
cd /opt/ch2_Macro && git remote -v
```

### 일상 redeploy

```bash
/opt/ch2_Macro/deploy/scripts/redeploy.sh
```

또는 수동:

```bash
cd /opt/ch2_Macro
git fetch origin && git checkout main && git pull origin main

cd backend
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm ci
npm run build   # .env 변경 시 VITE_* 반영

sudo systemctl restart ch2-macro-backend
sudo nginx -t && sudo systemctl reload nginx
```

**DB 스키마 변경** (`db/0xx_*.sql` 새 파일):

- dev: 로컬에서 migration 적용 → dump Promote **또는** VPS에서 `psql -f` 수동 적용
- 앱만 변경: redeploy만

- [ ] `git pull` 후 `/health` 정상
- [ ] UI 새 기능 반영 (캐시: Ctrl+Shift+R)

---

## 4.9 배포 완료 체크

- [ ] [07-verification-checklist.md](./07-verification-checklist.md) 전 항목

---

## 4.10 Docker 미사용 확인

- [ ] `docker ps` 비어 있음 (선택 사항)
- [ ] PostgreSQL: `systemctl status postgresql`
- [ ] Backend: `systemctl status ch2-macro-backend`
