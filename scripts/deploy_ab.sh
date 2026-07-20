#!/bin/bash
# Deploy A (integração :8765, main) + B (pré-homolog :8766, tag fixada) no 167.88.33.121
# Rodar como: bash deploy_ab.sh v2026.07.20-homolog
set -u
TAG="${1:?uso: bash deploy_ab.sh <TAG_DE_HOMOLOG>}"

# Mata só o main.py de um diretório específico (não derruba a outra instância)
kill_instance() {
  local dir="$1"
  for pid in $(pgrep -f 'python3 main.py'); do
    if [ "$(readlink -f /proc/$pid/cwd 2>/dev/null)" = "$dir" ]; then
      kill "$pid" 2>/dev/null
    fi
  done
}

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
screen -S orizon-manager -X quit 2>/dev/null
kill_instance /root/orizon-manager
sleep 1
screen -wipe >/dev/null 2>&1
cd /root/orizon-manager || exit 1
git fetch origin --tags && git reset --hard origin/main
apt-get install -y -qq python3-docx python3-openpyxl python3-requests python3-sqlalchemy python3-psycopg2 >/dev/null
ufw allow 8765/tcp >/dev/null 2>&1
screen -S orizon-manager -dm bash -c 'cd /root/orizon-manager && . /root/orizon-A.env && python3 main.py > app.log 2>&1'
wait_http 8765
tail -5 /root/orizon-manager/app.log

echo "=== INSTÂNCIA B (pré-homolog, :8766, tag $TAG) ==="
screen -S orizon-homolog -X quit 2>/dev/null
kill_instance /root/orizon-homolog
sleep 1
screen -wipe >/dev/null 2>&1
cd /root/orizon-homolog || exit 1
git fetch --tags origin && git checkout -f "$TAG"
ufw allow 8766/tcp >/dev/null 2>&1
screen -S orizon-homolog -dm bash -c 'cd /root/orizon-homolog && . /root/orizon-B.env && python3 main.py > app.log 2>&1'
wait_http 8766
tail -5 /root/orizon-homolog/app.log

echo "=== RESUMO ==="
echo "A: $(cd /root/orizon-manager && git log --oneline -1)"
echo "B: $(cd /root/orizon-homolog && git describe --tags 2>/dev/null) — $(cd /root/orizon-homolog && git log --oneline -1)"
ss -ltnp | grep -E '8765|8766'
