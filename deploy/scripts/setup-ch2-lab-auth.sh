#!/usr/bin/env bash
# 관리자 /lab/ 전용 htpasswd. 기존 파일이 있으면 비밀번호를 바꾸지 않는다.
# Usage (VPS):
#   sudo bash /opt/ch2_Macro/deploy/scripts/setup-ch2-lab-auth.sh
#   CH2_LAB_AUTH_USER=ch2 CH2_LAB_AUTH_PASS='secret' sudo -E bash ...
set -euo pipefail

HTPASSWD="/etc/nginx/.htpasswd-ch2-lab"
USER_NAME="${CH2_LAB_AUTH_USER:-ch2}"

if ! command -v htpasswd >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y apache2-utils
fi

if [[ -f "$HTPASSWD" && -z "${CH2_LAB_AUTH_PASS:-}" ]]; then
  echo "OK: $HTPASSWD exists (password unchanged)"
  echo "LAB_AUTH_USER=${USER_NAME}"
  exit 0
fi

if [[ -z "${CH2_LAB_AUTH_PASS:-}" ]]; then
  CH2_LAB_AUTH_PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
  GENERATED=1
else
  GENERATED=0
fi

htpasswd -cb "$HTPASSWD" "$USER_NAME" "$CH2_LAB_AUTH_PASS"
chmod 640 "$HTPASSWD"
chown root:www-data "$HTPASSWD" 2>/dev/null || chown root:nginx "$HTPASSWD" 2>/dev/null || true

echo "OK: wrote $HTPASSWD"
echo "LAB_AUTH_USER=${USER_NAME}"
if [[ "$GENERATED" -eq 1 ]]; then
  echo "LAB_AUTH_PASS=${CH2_LAB_AUTH_PASS}"
  echo "Save LAB_AUTH_PASS — shown once unless you set CH2_LAB_AUTH_PASS."
else
  echo "LAB_AUTH_PASS=(from CH2_LAB_AUTH_PASS env)"
fi
