#!/usr/bin/env bash
# ============================================================
# check-design-tokens.sh
# Falha (exit 1) se encontrar COR em hex literal (#rgb..#rrggbbaa) ou
# rgb()/rgba() COLORIDA fora do orizon-tokens.css. O orizon-tokens.css é a
# ÚNICA fonte de valores de cor da UI; todo o resto usa var(--token).
#
# Ignora: entidades HTML numéricas (&#9660;), rgb/rgba neutros (0,0,0 / 255,255,255,
# usados só em scrims/sombras), arquivos .svg de marca (design-system/marca/) e o
# próprio orizon-tokens.css.
#
# Uso:   bash scripts/check-design-tokens.sh
# Hook:  chamado por .git/hooks/pre-commit
# ============================================================
set -uo pipefail
cd "$(dirname "$0")/.."

# Código de UI varrido (o orizon-tokens.css NÃO entra — é onde o hex é permitido)
# UI enviada + camada de componentes. O orizon-styleguide.html NÃO entra: é doc/demo de
# referência (mostra swatches e o glifo de marca com cores literais, legítimo). O orizon-tokens.css
# também não — é a fonte única onde o hex é permitido.
FILES=(
  static/index.html
  static/login.html
  design-system/orizon-components.css
)

# Só varre os que existem
EXISTING=()
for f in "${FILES[@]}"; do [ -f "$f" ] && EXISTING+=("$f"); done

status=0

# 1) Hex de cor, ignorando entidades HTML (&#1234;) e sufixos de palavra
hex=$(grep -nP '(?<![&\w])#[0-9a-fA-F]{3,8}\b' "${EXISTING[@]}" 2>/dev/null || true)
if [ -n "$hex" ]; then
  echo "✖ Hex literal de cor encontrado (use var(--token) do orizon-tokens.css):"
  echo "$hex"
  status=1
fi

# 2) rgb()/rgba() colorida (exclui preto/branco puros — scrims e sombras)
rgb=$(grep -nP 'rgba?\(\s*(?!0\s*,\s*0\s*,\s*0)(?!255\s*,\s*255\s*,\s*255)\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}' "${EXISTING[@]}" 2>/dev/null || true)
if [ -n "$rgb" ]; then
  echo "✖ rgb()/rgba() colorida encontrada (use var(--token) do orizon-tokens.css):"
  echo "$rgb"
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "✔ Design tokens OK — nenhuma cor literal fora do orizon-tokens.css."
fi
exit "$status"
