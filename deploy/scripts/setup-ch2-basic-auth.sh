#!/usr/bin/env bash
# CH2 DATA — 전체 서브도메인 Nginx HTTP Basic Auth (개인용)
# Usage (VPS):
#   sudo bash /opt/ch2_Macro/deploy/scripts/setup-ch2-basic-auth.sh
#   CH2_BASIC_AUTH_USER=ch2 CH2_BASIC_AUTH_PASS='your-secret' sudo -E bash ...
set -euo pipefail

SNIPPET="/etc/nginx/snippets/ch2-basic-auth.conf"
HTPASSWD="/etc/nginx/.htpasswd-ch2"
USER_NAME="${CH2_BASIC_AUTH_USER:-ch2admin}"

if ! command -v htpasswd >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y apache2-utils
fi

if [[ -z "${CH2_BASIC_AUTH_PASS:-}" ]]; then
  CH2_BASIC_AUTH_PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
  GENERATED=1
else
  GENERATED=0
fi

mkdir -p /etc/nginx/snippets
htpasswd -cb "$HTPASSWD" "$USER_NAME" "$CH2_BASIC_AUTH_PASS"
chmod 640 "$HTPASSWD"
chown root:www-data "$HTPASSWD" 2>/dev/null || chown root:nginx "$HTPASSWD" 2>/dev/null || true

cat > "$SNIPPET" <<'EOF'
# CH2 DATA private access — include inside each HTTPS server { } block
auth_basic "CH2 DATA";
auth_basic_user_file /etc/nginx/.htpasswd-ch2;
EOF

patch_site() {
  local file="$1"
  local marker="$2"
  if [[ ! -f "$file" ]]; then
    echo "SKIP: $file (missing)"
    return
  fi
  if grep -q 'ch2-basic-auth.conf' "$file"; then
    echo "OK: $file (already patched)"
    return
  fi
  sed -i "0,/server_name ${marker}/{
/server_name ${marker}/a\\
    include /etc/nginx/snippets/ch2-basic-auth.conf;
}" "$file"
  echo "PATCHED: $file"
}

patch_site /etc/nginx/sites-available/ch2-macro "macro.ch2data.com 13.209.203.178;"
patch_site /etc/nginx/sites-available/ch2data-hub "ch2data.com www.ch2data.com;"
patch_site /etc/nginx/sites-available/ch2-viewer "viewer.ch2data.com;"
patch_site /etc/nginx/sites-available/ch2-fieldnote "fieldnote.ch2data.com;"

nginx -t
systemctl reload nginx

echo ""
echo "=== CH2 Basic Auth enabled ==="
echo "User: ${USER_NAME}"
if [[ "$GENERATED" -eq 1 ]]; then
  echo "Password (save this — shown once): ${CH2_BASIC_AUTH_PASS}"
else
  echo "Password: (from CH2_BASIC_AUTH_PASS env)"
fi
echo "Sites: ch2data.com, macro, viewer, fieldnote (+ IP macro if configured)"
