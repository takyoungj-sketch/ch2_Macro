#!/usr/bin/env bash
# CH2 Macro dev VPS — PostgreSQL 16, Nginx, UFW, fail2ban, backup dir
set -euo pipefail
# Run on VPS: bash deploy/scripts/server-setup-phase2.sh (LF line endings)

echo "==> PostgreSQL 16 PGDG"
if ! command -v psql >/dev/null || ! psql --version | grep -q " 16"; then
  echo "deb http://apt.postgresql.org/pub/repos/apt jammy-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
  wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo tee /etc/apt/trusted.gpg.d/pgdg.asc > /dev/null
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql-16 postgresql-client-16 postgresql-contrib-16
fi
psql --version
sudo systemctl enable postgresql
sudo systemctl start postgresql

echo "==> DB user/database"
PW_FILE="/home/ubuntu/.ch2_db_password"
if [[ ! -f "$PW_FILE" ]]; then
  openssl rand -hex 24 | tee "$PW_FILE" > /dev/null
  chmod 600 "$PW_FILE"
fi
CH2_DB_PW="$(cat "$PW_FILE")"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='ch2app'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER ch2app WITH PASSWORD '${CH2_DB_PW}';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='land_stats'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE land_stats OWNER ch2app;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE land_stats TO ch2app;"

echo "==> PostgreSQL localhost + 8GB tuning"
PG_CONF="$(sudo -u postgres psql -tAc 'SHOW config_file;')"
PG_HBA="$(sudo -u postgres psql -tAc 'SHOW hba_file;')"
sudo sed -i "s/^#*listen_addresses.*/listen_addresses = 'localhost'/" "$PG_CONF"
MARKER="# CH2 Macro dev VPS 8GB"
if ! grep -q "$MARKER" "$PG_CONF"; then
  sudo tee -a "$PG_CONF" > /dev/null <<EOF

$MARKER
shared_buffers = 1GB
effective_cache_size = 4GB
maintenance_work_mem = 512MB
work_mem = 64MB
max_connections = 80
random_page_cost = 1.1
effective_io_concurrency = 200
wal_buffers = 16MB
checkpoint_completion_target = 0.9
default_statistics_target = 100
log_min_duration_statement = 5000
log_line_prefix = '%t [%p] '
EOF
fi
# Remove non-local host rules if any (keep local peer + localhost scram)
sudo cp "$PG_HBA" "${PG_HBA}.bak.ch2"
sudo awk '
  /^host/ && $4 !~ /^127\.0\.0\.1\/32$/ && $4 !~ /^::1\/128$/ { next }
  { print }
' "${PG_HBA}.bak.ch2" | sudo tee "$PG_HBA" > /dev/null
sudo systemctl restart postgresql

echo "==> Nginx + Certbot"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
sudo systemctl start nginx

echo "==> UFW"
if sudo ufw status | grep -q inactive; then
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow OpenSSH
  sudo ufw allow "Nginx Full"
  echo "y" | sudo ufw enable
fi

echo "==> SSH hardening + fail2ban"
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl reload sshd
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

echo "==> Backup directory"
sudo mkdir -p /var/backups/ch2
sudo chown ubuntu:ubuntu /var/backups/ch2

echo "==> Verification"
export PGPASSWORD="$CH2_DB_PW"
psql "postgresql://ch2app@127.0.0.1:5432/land_stats" -c "SELECT 1 AS ok;"
sudo -u postgres psql -c "SHOW listen_addresses;"
ss -lntp | grep -E ':5432|:80|:22' || true
curl -sS -o /dev/null -w "nginx_local_http=%{http_code}\n" http://127.0.0.1/
sudo ufw status verbose | head -15
systemctl is-active postgresql nginx fail2ban
echo "DB password stored in: $PW_FILE"
echo "PHASE2_OK"
