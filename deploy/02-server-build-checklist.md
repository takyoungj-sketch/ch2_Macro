# 2. 서버 구축 체크리스트

Ubuntu 22.04 Lightsail (4 GB) 기준. 항목마다 `[ ]` 체크.

---

## 2.1 사전 준비

- [ ] Static IP 부여·기록
- [ ] SSH 접속 확인
- [ ] (권장) dev 서브도메인 A 레코드 → Static IP

---

## 2.2 시스템 패키지

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  git curl wget ufw fail2ban \
  nginx certbot python3-certbot-nginx \
  postgresql postgresql-contrib \
  python3.11 python3.11-venv python3-pip \
  build-essential libpq-dev \
  nodejs npm
```

Node 20이 필요하면 (Vite 5 권장):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v   # v20.x
```

- [ ] `python3.11 --version`
- [ ] `node -v` (18+ 또는 20+)
- [ ] `psql --version` (PostgreSQL 14+; Ubuntu 22.04는 14, 16 PPA 선택 가능)

### PostgreSQL 16 (선택, 로컬과 버전 맞추기)

```bash
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo tee /etc/apt/trusted.gpg.d/pgdg.asc
sudo apt update && sudo apt install -y postgresql-16 postgresql-client-16
```

---

## 2.3 PostgreSQL 설치·DB·역할

```bash
sudo -u postgres psql <<'SQL'
CREATE USER ch2app WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE land_stats OWNER ch2app;
GRANT ALL PRIVILEGES ON DATABASE land_stats TO ch2app;
SQL
```

**외부 접속 차단** (`/etc/postgresql/*/main/postgresql.conf`):

```ini
listen_addresses = 'localhost'
```

**`/etc/postgresql/*/main/pg_hba.conf`** — 로컬만:

```
local   all   all                 peer
host    all   all   127.0.0.1/32  scram-sha-256
host    all   all   ::1/128       scram-sha-256
```

4 GB RAM 튜닝 (`/etc/postgresql/*/main/postgresql.conf`에 추가 — [`templates/postgresql-4gb.conf.snippet`](./templates/postgresql-4gb.conf.snippet)):

```ini
shared_buffers = 512MB
effective_cache_size = 1536MB
maintenance_work_mem = 256MB
work_mem = 32MB
max_connections = 50
```

```bash
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

- [ ] `sudo -u postgres psql -c "\l"` 에 `land_stats` 표시
- [ ] `psql "postgresql://ch2app:***@127.0.0.1/land_stats" -c "SELECT 1"`

---

## 2.4 애플리케이션 디렉터리

```bash
sudo mkdir -p /opt/ch2_Macro
sudo chown ubuntu:ubuntu /opt/ch2_Macro
cd /opt/ch2_Macro
git clone https://github.com/takyoungj-sketch/ch2_Macro.git .
# 또는 private repo: deploy key / PAT
```

- [ ] `git log -1` 확인

---

## 2.5 Backend (Python venv)

```bash
cd /opt/ch2_Macro/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

`backend/.env` 작성 (템플릿 복사 후 수정):

```bash
cp /opt/ch2_Macro/deploy/templates/backend.env.production.example \
   /opt/ch2_Macro/backend/.env
chmod 600 /opt/ch2_Macro/backend/.env
nano /opt/ch2_Macro/backend/.env
```

- [ ] `DATABASE_URL` → `ch2app@127.0.0.1`
- [ ] `CORS_ORIGINS` → `https://dev-macro.YOURDOMAIN.com`
- [ ] `API_TOKEN` → 랜덤 32+ byte
- [ ] `STATS_V2_DEFAULT_AS_OF_MONTH` → 로컬 DB와 동일

**systemd** ([`templates/ch2-macro-backend.service`](./templates/ch2-macro-backend.service)):

```bash
sudo cp /opt/ch2_Macro/deploy/templates/ch2-macro-backend.service \
  /etc/systemd/system/ch2-macro-backend.service
sudo systemctl daemon-reload
sudo systemctl enable ch2-macro-backend
# DB restore 후 start
```

- [ ] `systemctl status ch2-macro-backend` (데이터 없으면 health만 나중에)

---

## 2.6 Frontend (빌드)

```bash
cd /opt/ch2_Macro/frontend
cp /opt/ch2_Macro/deploy/templates/frontend.env.production.example .env
# VITE_API_TOKEN = backend API_TOKEN 과 동일
nano .env
npm ci
npm run build
```

- [ ] `frontend/dist/index.html` 존재

---

## 2.7 Nginx

```bash
sudo cp /opt/ch2_Macro/deploy/templates/nginx-ch2-macro.conf \
  /etc/nginx/sites-available/ch2-macro
sudo ln -sf /etc/nginx/sites-available/ch2-macro /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
# server_name 수정
sudo nano /etc/nginx/sites-available/ch2-macro
sudo nginx -t && sudo systemctl reload nginx
```

- [ ] HTTP(80)에서 `dist` 또는 certbot 준비 완료

HTTPS는 [04-deploy-checklist.md](./04-deploy-checklist.md) §4.

---

## 2.8 방화벽 (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

- [ ] 8000, 5432 **UFW에 없음**
- [ ] Lightsail 방화벽과 이중 확인

---

## 2.9 SSH 보안 (권장)

`/etc/ssh/sshd_config`:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl reload sshd
```

- [ ] (선택) `fail2ban` 기본 enable: `sudo systemctl enable --now fail2ban`

---

## 2.10 백업 디렉터리

```bash
sudo mkdir -p /var/backups/ch2
sudo chown ubuntu:ubuntu /var/backups/ch2
```

- [ ] Promote 덤프 저장 경로 준비

---

## 2.11 다음 단계

→ [03-data-migration.md](./03-data-migration.md) DB 이전  
→ [04-deploy-checklist.md](./04-deploy-checklist.md) HTTPS·최종 기동
