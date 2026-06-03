# 8. CH2 DATA 포털 (ch2data.com 허브)

루트 도메인 **`ch2data.com`** 에 정적 허브 페이지를 두고, 각 제품은 **서브도메인**으로 분리합니다.

| URL | 역할 | 상태 |
|-----|------|------|
| `https://ch2data.com` | 포털 (3분기) | ✅ HTTPS (2026-05-30) |
| `https://macro.ch2data.com` | CH2 Macro | ✅ HTTPS (2026-05-30) → [04-deploy-checklist.md](./04-deploy-checklist.md) |
| `https://viewer.ch2data.com` | CH2 Viewer | ✅ 다운로드 포털 (Windows ZIP) |
| `https://fieldnote.ch2data.com` | CH2 FieldNote | 예약 (개발중) |

---

## 8.1 DNS (가비아 등)

Static IP: **Lightsail VPS** `13.209.203.178`

| 호스트 | 타입 | 값 |
|--------|------|-----|
| `@` (`ch2data.com`) | A | `13.209.203.178` |
| `www` | A | `13.209.203.178` |
| `macro` | A | `13.209.203.178` |

전파 확인:

```bash
dig +short ch2data.com A
dig +short www.ch2data.com A
dig +short macro.ch2data.com A
# 모두 13.209.203.178
```

Viewer·FieldNote는 앱 준비 전까지 DNS 생략 가능.

---

## 8.2 Lightsail 방화벽 (HTTPS 필수)

**UFW만으로는 부족합니다.** Lightsail 콘솔 → 인스턴스 → **Networking** → Firewall:

| 포트 | 프로토콜 | 허용 |
|------|----------|------|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (certbot·리다이렉트) |
| **443** | **TCP** | **HTTPS** ← 없으면 브라우저 타임아웃 |

외부에서 `curl -I https://ch2data.com/` 이 200/301 이어야 합니다.

---

## 8.3 허브 파일 배치

소스: [`deploy/hub/`](../hub/) (`index.html`, `style.css`)

```bash
sudo bash /opt/ch2_Macro/deploy/scripts/deploy-hub.sh
```

- [ ] `https://ch2data.com/` → CH2 DATA 허브
- [ ] Macro 카드 → `https://macro.ch2data.com/`

---

## 8.4 HTTPS (certbot)

DNS 전파 + **Lightsail 443 개방** 후:

```bash
sudo certbot --nginx -d ch2data.com -d www.ch2data.com \
  --non-interactive --agree-tos --register-unsafely-without-email --redirect

sudo certbot --nginx -d macro.ch2data.com \
  --non-interactive --agree-tos --register-unsafely-without-email --redirect

sudo certbot renew --dry-run
```

- [ ] `https://ch2data.com` · `https://macro.ch2data.com` 자물쇠
- [ ] HTTP → HTTPS 리다이렉트

인증서 경로:

- `/etc/letsencrypt/live/ch2data.com/`
- `/etc/letsencrypt/live/macro.ch2data.com/`

---

## 8.5 Macro 연동

1. [`templates/nginx-ch2-macro.conf`](./templates/nginx-ch2-macro.conf) — `/` 게이트웨이, `/land/`, `/built/`, `/api/`
2. `backend/.env` — `CORS_ORIGINS=https://macro.ch2data.com`, `BUILT_DATABASE_URL=...built_stats`
3. `redeploy.sh` — land + built 프론트 빌드
4. 복합 DB Promote: [`09-macro-built-vps.md`](./09-macro-built-vps.md)

검증: [07-verification-checklist.md](./07-verification-checklist.md) · [09-macro-built-vps.md](./09-macro-built-vps.md) §9.8

---

## 8.6 Nginx 사이트 요약 (한 VPS)

| site file | server_name | root / backend |
|-----------|-------------|----------------|
| `ch2data-hub` | `ch2data.com`, `www` | `/var/www/ch2data-hub` |
| `ch2-macro` | `macro.ch2data.com` | `/` gateway · `/land/` · `/built/` SPA + `/api` |
| `ch2-viewer` | `viewer.ch2data.com` | `/var/www/ch2-viewer` |
| `ch2-fieldnote` | `fieldnote.ch2data.com` | proxy `:5174` |

certbot 이 각 server 블록에 SSL listen 443 을 추가합니다. `/api/` 프록시가 사라졌으면 템플릿의 `location` 블록을 merge 하세요.

### 8.7 개인용 Basic Auth (전체 잠금)

전 서브도메인에 HTTP Basic Auth:

```bash
sudo bash /opt/ch2_Macro/deploy/scripts/setup-ch2-basic-auth.sh
# 또는 비밀번호 직접 지정:
CH2_BASIC_AUTH_USER=ch2admin CH2_BASIC_AUTH_PASS='...' sudo -E bash ...
```

- 스니펫: `/etc/nginx/snippets/ch2-basic-auth.conf`
- 계정 파일: `/etc/nginx/.htpasswd-ch2`
- 비밀번호 변경: `sudo htpasswd /etc/nginx/.htpasswd-ch2 ch2admin`

---

## 8.8 허브 수정

1. `deploy/hub/index.html` · `style.css` 수정
2. VPS sync → `sudo bash deploy/scripts/deploy-hub.sh`

Viewer·FieldNote 준비 시 DNS·Nginx vhost·허브 카드 링크를 추가합니다.
