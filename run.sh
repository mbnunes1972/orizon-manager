#!/usr/bin/env bash
# Launcher do Orizon Manager — SEMPRE sobe no PostgreSQL (o fallback SQLite foi APOSENTADO no runtime).
# A URL do banco vem de um arquivo .env (NAO versionado) na raiz do projeto, no formato:
#   DATABASE_URL=postgresql+psycopg2://orizon:SUA_SENHA@localhost/orizon
# Uso:  ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

# Carrega variaveis do .env (git-ignored), se existir.
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERRO: DATABASE_URL nao configurada."
  echo "Crie um arquivo .env na raiz do projeto com, por exemplo:"
  echo "  DATABASE_URL=postgresql+psycopg2://orizon:SUA_SENHA@localhost/orizon"
  exit 1
fi

echo "Orizon Manager -> PostgreSQL (${DATABASE_URL##*@})"
exec python3 main.py
