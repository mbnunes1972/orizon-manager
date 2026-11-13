#!/bin/bash
# backup_externo.sh — sincroniza os dumps que já existem localmente (produzidos pelo cron de
# `/root/backup_orizon.sh`, ver DEV_RULES.md) para um bucket privado no Backblaze B2, fora da
# VPS que guarda o banco. Não faz dump nenhum sozinho — copia o que já está em disco; a
# frequência/retenção do dump em si continua sendo governada pelo script existente.
#
# Por que Backblaze B2, não S3: armazenamento ~4x mais barato que o S3 padrão pro mesmo dado, e
# egress gratuito via a Cloudflare Bandwidth Alliance (importa numa restauração de verdade, não
# num backup do dia a dia). A API é compatível com S3 — o mesmo `rclone` migra pra AWS um dia só
# trocando backend/credenciais, sem reescrever nada aqui.
#
# `set -e`, diferente de scripts/deploy_ab.sh (que só usa `set -u`): aqui a falha tem que PARAR
# e AVISAR, nunca seguir como se o backup tivesse ido — um backup externo que falha em silêncio
# é pior do que não ter backup externo nenhum (ninguém sabe que precisa de outro plano).
set -euo pipefail

ENV_FILE="${ORIZON_BACKUP_ENV_FILE:-/root/orizon-backup.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "[backup_externo] $ENV_FILE não existe — nada a fazer. Ver o modelo no fim deste arquivo." >&2
    exit 1
fi
set -a; . "$ENV_FILE"; set +a

: "${ORIZON_BACKUP_B2_KEY_ID:?defina ORIZON_BACKUP_B2_KEY_ID em $ENV_FILE}"
: "${ORIZON_BACKUP_B2_APP_KEY:?defina ORIZON_BACKUP_B2_APP_KEY em $ENV_FILE}"
: "${ORIZON_BACKUP_B2_BUCKET:?defina ORIZON_BACKUP_B2_BUCKET em $ENV_FILE}"
DIR_LOCAL="${ORIZON_BACKUP_DIR_LOCAL:-/root/backups}"
PADRAO="${ORIZON_BACKUP_PADRAO:-*.sql.gz}"
RETENCAO_DIAS="${ORIZON_BACKUP_RETENCAO_DIAS:-30}"

command -v rclone >/dev/null 2>&1 || {
    echo "[backup_externo] rclone não instalado. apt install -y rclone" >&2
    exit 1
}
[ -d "$DIR_LOCAL" ] || {
    echo "[backup_externo] $DIR_LOCAL não existe — nada pra enviar." >&2
    exit 1
}

# Config do remote inteiramente por env var — nenhum arquivo de credencial extra no disco além
# do $ENV_FILE (que já precisa estar em modo 600, mesma disciplina de orizon-A.env/orizon.env).
export RCLONE_CONFIG_ORIZONB2_TYPE=b2
export RCLONE_CONFIG_ORIZONB2_ACCOUNT="$ORIZON_BACKUP_B2_KEY_ID"
export RCLONE_CONFIG_ORIZONB2_KEY="$ORIZON_BACKUP_B2_APP_KEY"
REMOTO="orizonb2:${ORIZON_BACKUP_B2_BUCKET}"

echo "[backup_externo] $(date -Iseconds) sincronizando ${DIR_LOCAL}/${PADRAO} -> ${REMOTO}"
rclone copy "$DIR_LOCAL" "$REMOTO" --include "$PADRAO" --checksum

# Confere de verdade que cada dump local está no bucket — nunca confiar só no exit code do
# copy (a mesma lição do ACHADO-69, item 7 do deploy: um checkout que aborta e o resto do
# script segue como se nada tivesse acontecido).
ESPERADOS=$(find "$DIR_LOCAL" -maxdepth 1 -name "$PADRAO" -printf '%f\n' | sort)
PRESENTES=$(rclone lsf "$REMOTO" --include "$PADRAO" | sort)
FALTANDO=$(comm -23 <(echo "$ESPERADOS") <(echo "$PRESENTES") || true)
if [ -n "$FALTANDO" ]; then
    echo "[backup_externo] ERRO: não confirmados no bucket depois do copy:" >&2
    echo "$FALTANDO" >&2
    exit 1
fi
TOTAL=$(echo "$ESPERADOS" | grep -c . || true)
echo "[backup_externo] confirmado: os $TOTAL dumps locais existem no bucket."

# Retenção remota própria (independente da retenção local de 14 dias do backup_orizon.sh) —
# só apaga o que corresponde ao padrão desta sincronização, nunca o bucket inteiro.
rclone delete "$REMOTO" --min-age "${RETENCAO_DIAS}d" --include "$PADRAO"
echo "[backup_externo] $(date -Iseconds) concluído."

# ── Configuração (fazer uma vez) ─────────────────────────────────────────────────────────────
#
# 1. No painel do Backblaze B2: criar um bucket PRIVADO (ex.: orizon-backups-producao) e uma
#    Application Key restrita a ESSE bucket só (nunca a chave mestra da conta).
#
# 2. apt install -y rclone   (binário único — sem a fricção de pip/PEP668 do resto da VPS)
#
# 3. Criar /root/orizon-backup.env, modo 600, mesma disciplina de /root/orizon-A.env:
#      ORIZON_BACKUP_B2_KEY_ID=<id da application key>
#      ORIZON_BACKUP_B2_APP_KEY=<a application key>
#      ORIZON_BACKUP_B2_BUCKET=orizon-backups-producao
#      # opcionais, com default sensato se omitidos:
#      # ORIZON_BACKUP_DIR_LOCAL=/root/backups
#      # ORIZON_BACKUP_PADRAO=*.sql.gz
#      # ORIZON_BACKUP_RETENCAO_DIAS=30
#    chmod 600 /root/orizon-backup.env
#
# 4. Cron, alguns minutos depois do backup local existente (que roda às 3h, DEV_RULES.md):
#      15 3 * * * bash /root/orizon-manager/scripts/backup_externo.sh >> /root/backups/externo.log 2>&1
#
# 5. Teste manual antes de confiar no cron:
#      bash /root/orizon-manager/scripts/backup_externo.sh
#    Depois confira no painel do B2 que o(s) arquivo(s) apareceram, e rode de novo — a segunda
#    vez não deve reenviar nada (rclone copy só manda o que é novo/mudou).
