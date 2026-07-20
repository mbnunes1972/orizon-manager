#!/bin/bash
# Deploy A (integração :8765, main) + B (pré-homolog :8766, tag fixada) no 167.88.33.121
# Rodar como: bash deploy_ab.sh v2026.07.20-homolog
# As instâncias rodam como serviços systemd (orizon-a / orizon-b), habilitados no boot —
# units em /etc/systemd/system/, com Restart=always e log em app.log de cada diretório.
set -u
TAG="${1:?uso: bash deploy_ab.sh <TAG_DE_HOMOLOG>}"

wait_http() {
  local port="$1" code=000
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$port" || true)
    [ "$code" = "302" ] && break
    sleep 1
  done
  echo "porta $port → HTTP $code (esperado 302)"
}

echo "=== INSTÂNCIA A (integração, :8765, main) ==="
systemctl stop orizon-a
cd /root/orizon-manager || exit 1
git fetch origin --tags && git reset --hard origin/main
apt-get install -y -qq python3-docx python3-openpyxl python3-requests python3-sqlalchemy python3-psycopg2 >/dev/null
ufw allow 8765/tcp >/dev/null 2>&1
systemctl start orizon-a
wait_http 8765
tail -5 /root/orizon-manager/app.log

echo "=== INSTÂNCIA B (pré-homolog, :8766, tag $TAG) ==="
systemctl stop orizon-b
cd /root/orizon-homolog || exit 1
git fetch --tags origin && git checkout -f "$TAG"
ufw allow 8766/tcp >/dev/null 2>&1
systemctl start orizon-b
wait_http 8766
tail -5 /root/orizon-homolog/app.log

echo "=== RESUMO ==="
echo "A: $(cd /root/orizon-manager && git log --oneline -1)"
echo "B: $(cd /root/orizon-homolog && git describe --tags 2>/dev/null) — $(cd /root/orizon-homolog && git log --oneline -1)"
ss -ltnp | grep -E '8765|8766'
