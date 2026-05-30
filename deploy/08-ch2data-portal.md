# 8. CH2 DATA 포털 (ch2data.com 허브)

루트 도메인 **`ch2data.com`** 에 정적 허브 페이지를 두고, 각 제품은 **서브도메인**으로 분리합니다.

| URL | 역할 | 상태 |
|-----|------|------|
| `https://ch2data.com` | 포털 (3분기) | 이 문서 |
| `https://dev-macro.ch2data.com` | CH2 Macro (dev VPS) | 배포됨 → [04-deploy-checklist.md](./04-deploy-checklist.md) |
| `https://dev-viewer.ch2data.com` | CH2 Viewer | 예약 (개발중) |
| `https://dev-fieldnote.ch2data.com` | CH2 FieldNote | 예약 (개발중) |

프로덕션 서브도메인(`macro.`, `viewer.`, `fieldnote.`)은 dev 검증 후 분리합니다.

---

## 8.1 DNS (등록업체 또는 Route 53)

Static IP: **Lightsail dev VPS** (예: `13.209.203.178`)

| 호스트 | 타입 | 값 |
|--------|------|-----|
| `@` (`ch2data.com`) | A | VPS Static IP |
| `www` | A 또는 CNAME | VPS IP / `ch2data.com` |
| `dev-macro` | A | VPS Static IP |

Viewer·FieldNote는 앱 준비 전까지 DNS 생략 가능.

---

## 8.2 허브 파일 배치

소스: [`deploy/hub/`](../hub/) (`index.html`, `style.css`)

```bash
# VPS (repo가 /opt/ch2_Macro 일 때)
sudo bash /opt/ch2_Macro/deploy/scripts/deploy-hub.sh
```

수동:

```bash
sudo mkdir -p /var/www/ch2data-hub
sudo rsync -a --delete /opt/ch2_Macro/deploy/hub/ /var/www/ch2data-hub/
sudo cp /opt/ch2_Macro/deploy/templates/nginx-ch2data-hub.conf /etc/nginx/sites-available/ch2data-hub
sudo ln -sf /etc/nginx/sites-available/ch2data-hub /etc/nginx/sites-enabled/ch2data-hub
sudo nginx -t && sudo systemctl reload nginx
```

- [ ] `curl -sS http://ch2data.com/` → `CH2 DATA` HTML
- [ ] Macro 카드 링크 → `https://dev-macro.ch2data.com/`

---

## 8.3 HTTPS

DNS 전파 후:

```bash
# 허브
sudo certbot --nginx -d ch2data.com -d www.ch2data.com

# Macro (아직이면)
sudo certbot --nginx -d dev-macro.ch2data.com
```

- [ ] `https://ch2data.com` 자물쇠
- [ ] `http://` → `https://` 리다이렉트
- [ ] `sudo certbot renew --dry-run`

---

## 8.4 Macro 연동 (dev-macro)

1. [`templates/nginx-ch2-macro.conf`](./templates/nginx-ch2-macro.conf) — `server_name dev-macro.ch2data.com;`
2. `backend/.env` — `CORS_ORIGINS=https://dev-macro.ch2data.com`
3. `frontend/.env` — API base URL HTTPS (템플릿 참고)
4. `npm run build` + `systemctl restart ch2-macro-backend`

검증: [07-verification-checklist.md](./07-verification-checklist.md)

---

## 8.5 허브 내용 수정

1. 로컬에서 `deploy/hub/index.html` · `style.css` 수정
2. git push → VPS `git pull` (또는 tar sync)
3. `sudo bash deploy/scripts/deploy-hub.sh`

Viewer·FieldNote가 준비되면 카드를 `<a href="https://dev-viewer.ch2data.com">` 형태로 바꾸고 DNS·Nginx vhost를 추가합니다.

---

## 8.6 Nginx 사이트 요약 (한 VPS)

```
/etc/nginx/sites-enabled/
├── ch2data-hub      → /var/www/ch2data-hub          (ch2data.com, www)
└── ch2-macro        → /opt/ch2_Macro/frontend/dist  (dev-macro.ch2data.com)
```

각 `server_name` 이 다르므로 충돌 없음.
