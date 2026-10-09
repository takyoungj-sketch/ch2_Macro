#!/usr/bin/env bash
# Usage: merge_toss_keys_remote.sh /tmp/ch2-toss-keys.xxx.env
set -eo pipefail
REMOTE_TMP="${1:?tmp env file}"
ENV_FILE="/opt/ch2_Macro/backend/.env"
TOSS_CLIENT_KEY="$(grep -m1 '^TOSS_CLIENT_KEY=' "$REMOTE_TMP" | cut -d= -f2- | tr -d '\r')"
TOSS_SECRET_KEY="$(grep -m1 '^TOSS_SECRET_KEY=' "$REMOTE_TMP" | cut -d= -f2- | tr -d '\r')"
test -n "$TOSS_CLIENT_KEY" && test -n "$TOSS_SECRET_KEY"
grep -v -E '^TOSS_CLIENT_KEY=|^TOSS_SECRET_KEY=|^TOSS_WEBHOOK_SECRET=' "$ENV_FILE" > "${ENV_FILE}.new"
printf '%s\n' "TOSS_CLIENT_KEY=$TOSS_CLIENT_KEY" "TOSS_SECRET_KEY=$TOSS_SECRET_KEY" >> "${ENV_FILE}.new"
mv "${ENV_FILE}.new" "$ENV_FILE"
chmod 600 "$ENV_FILE"
rm -f "$REMOTE_TMP"
sudo systemctl restart ch2-macro-backend
sleep 2
bash /opt/ch2_Macro/deploy/scripts/verify_toss_billing_ready.sh
